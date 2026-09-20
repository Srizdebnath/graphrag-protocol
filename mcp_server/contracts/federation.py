"""Contract 6: Federation — real multi-graph fan-out and merge.

Fans a query out to several TigerGraph graphs in the same workspace (each a
:class:`BackendRef`) and merges the returned subgraphs under an explicit,
transparent policy:

- ``rrf``: reciprocal rank fusion, ``sum(weight / (rrf_k + rank))``.
- ``weighted_score``: ``sum(weight * relevance) / sum(weight)``.

Every merged entity carries its originating backend in ``properties`` so the
merge is auditable, and the merged context reports per-backend timings in its
query echo. No backend is simulated: each fan-out target is a live adapter.
"""

from __future__ import annotations

import concurrent.futures
import re
import time
from typing import Any

from mcp_server.adapters.base import BaseGraphRAGAdapter
from mcp_server.protocol import Provenance, RetrievalMetrics, SubgraphContext
from mcp_server.protocol_extensions import (
    BackendRef,
    EntityLink,
    FederationConfig,
    MergeStrategy,
)

_MAX_WORKERS = 4
_MAX_REGISTERED_BACKENDS = 20
_GRAPH_ID_RE = re.compile(r"^[a-zA-Z0-9_]{1,64}$")


class FederationContract:
    """Contract 6: fan-out retrieval over multiple graphs, then merge.

    Args:
        primary: The default (usually already-connected) adapter, used when a
            config lists no backends.
        adapter_factory: Optional ``graph_id -> adapter`` hook. When omitted,
            extra graphs are reached by cloning the primary adapter's
            connection parameters with a different graph name.
    """

    def __init__(
        self,
        primary: BaseGraphRAGAdapter,
        adapter_factory: Any | None = None,
    ) -> None:
        if primary is None:
            raise ValueError("FederationContract requires a primary adapter")
        self._primary = primary
        self._factory = adapter_factory
        self._registered: dict[str, BaseGraphRAGAdapter] = {}

    # -- registration -----------------------------------------------------------

    def register_backend(
        self,
        name: str,
        adapter: BaseGraphRAGAdapter | None = None,
        weight: float = 1.0,
    ) -> BackendRef:
        """Register a named backend (live adapter) and return its reference.

        Args:
            name: Logical backend name.
            adapter: Live adapter; when omitted the primary adapter is used.
            weight: Positive merge weight.

        Returns:
            The :class:`BackendRef` describing the registration.
        """
        if not name:
            raise ValueError("register_backend requires a non-empty name")
        if weight <= 0:
            raise ValueError("register_backend requires weight > 0")
        self._registered[name] = adapter or self._primary
        return BackendRef(name=name, graph_id=getattr(adapter or self._primary, "_graphname", name), weight=weight)

    def _resolve(self, ref: BackendRef) -> BaseGraphRAGAdapter:
        """Adapter for a backend reference (registered, primary, else cloned)."""
        if not ref.graph_id or not _GRAPH_ID_RE.match(ref.graph_id):
            raise ValueError(f"Invalid graph identifier: {ref.graph_id!r}")

        if ref.name in self._registered:
            return self._registered[ref.name]
        # Reuse the primary adapter when the reference points at the same graph:
        # cloning would re-open a connection and re-install the GSQL queries.
        if ref.graph_id == getattr(self._primary, "_graphname", None):
            self._registered[ref.name] = self._primary
            return self._primary

        # Bound cache size to prevent socket / memory exhaustion
        if len(self._registered) >= _MAX_REGISTERED_BACKENDS:
            for k in list(self._registered.keys()):
                if self._registered[k] is not self._primary:
                    del self._registered[k]
                    break

        if self._factory is not None:
            adapter = self._factory(ref.graph_id)
            self._registered[ref.name] = adapter
            return adapter
        primary = self._primary
        parallel_cls = type(primary)
        try:
            adapter = parallel_cls(
                host=getattr(primary, "_host", None),
                graphname=ref.graph_id,
                gsql_secret=getattr(primary, "_gsql_secret", None),
                username=getattr(primary, "_username", None),
                port=getattr(primary, "_port", None),
            )
        except TypeError as exc:
            raise RuntimeError(
                f"Cannot reach backend {ref.name!r} (graph {ref.graph_id!r}): the active "
                f"adapter ({parallel_cls.__name__}) does not support multi-graph fan-out. "
                "Register the backend explicitly via register_backend()."
            ) from exc
        self._registered[ref.name] = adapter
        return adapter

    # -- federated retrieval ----------------------------------------------------

    def federated_search(
        self,
        query: str,
        config: FederationConfig | None = None,
        mode: str = "auto",
        **kwargs: Any,
    ) -> SubgraphContext:
        """Fan a query out to every configured backend and merge the results.

        Args:
            query: Natural-language query.
            config: Federation policy; when it lists no backends the primary
                backend answers alone.
            mode: Retrieval mode forwarded to each backend's contract
                (``auto``/``local``/``global``/``hybrid``/``entity``).
            **kwargs: Extra arguments forwarded to the retrieval contract.

        Returns:
            A merged, protocol-standard :class:`SubgraphContext`.
        """
        if not query or not query.strip():
            raise ValueError("federated_search requires a non-empty query")
        cfg = config or FederationConfig()
        refs = cfg.backends or [
            BackendRef(name="primary", graph_id=getattr(self._primary, "_graphname", "primary"), weight=1.0)
        ]
        t0 = time.perf_counter()
        per_backend = self._fan_out(query, refs, mode, kwargs)
        latency_ms = (time.perf_counter() - t0) * 1000
        return self._merge(query, cfg, refs, per_backend, latency_ms)

    def _fan_out(
        self,
        query: str,
        refs: list[BackendRef],
        mode: str,
        kwargs: dict[str, Any],
    ) -> list[tuple[BackendRef, SubgraphContext | None, str | None, float]]:
        """Run every backend concurrently; never let one failure abort the fan-out.

        Returns:
            One ``(ref, context, error, duration_ms)`` tuple per backend, where
            ``duration_ms`` is that backend's own measured wall time.
        """
        from mcp_server.contracts.retrieval import RetrievalContract

        def run(ref: BackendRef) -> tuple[BackendRef, SubgraphContext | None, str | None, float]:
            started = time.perf_counter()
            try:
                adapter = self._resolve(ref)
                result = RetrievalContract(adapter).search(query, mode=mode, **kwargs)
                return ref, result.context, None, round((time.perf_counter() - started) * 1000, 2)
            except Exception as exc:  # noqa: BLE001 - partial results are valid
                return (
                    ref,
                    None,
                    f"{type(exc).__name__}: {exc}",
                    round((time.perf_counter() - started) * 1000, 2),
                )

        if len(refs) == 1:
            return [run(refs[0])]
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, len(refs))) as pool:
            return list(pool.map(run, refs))

    @staticmethod
    def _relevance(entity: dict[str, Any], default: float = 0.5) -> float:
        """Relevance score of an entity, treating 0.0 as a real score.

        ``entity.get(...) or default`` would wrongly promote a legitimate 0.0
        (lowest rank) to the default, so the None case is handled explicitly.
        """
        raw = entity.get("relevance_score")
        if raw is None:
            return default
        try:
            return float(raw)
        except (TypeError, ValueError):
            return default

    def _merge(
        self,
        query: str,
        cfg: FederationConfig,
        refs: list[BackendRef],
        per_backend: list[tuple[BackendRef, SubgraphContext | None, str | None, float]],
        latency_ms: float,
    ) -> SubgraphContext:
        """Apply the configured merge policy and build the unified context."""
        total_weight = sum(r.weight for r in refs) or 1.0
        entity_scores: dict[tuple[str, str], float] = {}
        entities: dict[tuple[str, str], dict[str, Any]] = {}
        relationships: dict[str, dict[str, Any]] = {}
        paths: dict[str, dict[str, Any]] = {}
        communities: dict[str, dict[str, Any]] = {}
        chunks: dict[str, dict[str, Any]] = {}
        sources: list[str] = []
        visited: list[str] = []
        docs_used: list[str] = []
        errors: list[str] = []
        timings: dict[str, float] = {}

        for ref, ctx, error, duration_ms in per_backend:
            timings[ref.name] = duration_ms
            if error or ctx is None:
                errors.append(f"{ref.name} ({ref.graph_id}): {error}")
                continue
            ranked = sorted(
                ctx.results.get("entities", []),
                key=lambda e: -self._relevance(e),
            )
            for rank, ent in enumerate(ranked, start=1):
                key = (str(ent.get("type")), str(ent.get("id")))
                relevance = self._relevance(ent)
                if cfg.merge_strategy is MergeStrategy.RECIPROCAL_RANK_FUSION:
                    entity_scores[key] = entity_scores.get(key, 0.0) + ref.weight / (cfg.rrf_k + rank)
                else:
                    entity_scores[key] = entity_scores.get(key, 0.0) + ref.weight * relevance
                if key not in entities:
                    merged = dict(ent)
                    merged["properties"] = {**(ent.get("properties") or {}), "backends": []}
                    entities[key] = merged
                tags = entities[key]["properties"]["backends"]
                if ref.name not in tags:
                    tags.append(ref.name)
            self._collect(ctx, ref, relationships, paths, communities, chunks)
            sources.extend(ctx.provenance.source_documents)
            visited.extend(getattr(step, "entity", None) for step in ctx.provenance.traversal_log)
            docs_used.append(f"{ref.name}:{ref.graph_id}")

        divisor = total_weight if cfg.merge_strategy is MergeStrategy.WEIGHTED_SCORE else 1.0
        merged_entities: list[dict[str, Any]] = []
        for key, ent in entities.items():
            ent["relevance_score"] = round(entity_scores.get(key, 0.0) / divisor, 6)
            merged_entities.append(ent)
        merged_entities.sort(key=lambda e: -self._relevance(e, default=0.0))
        merged_entities = merged_entities[: cfg.top_k]

        query_echo: dict[str, Any] = {
            "text": query,
            "mode": "federated",
            "merge_strategy": cfg.merge_strategy.value,
            "backends": docs_used,
            "backend_timings_ms": timings,
            "top_k": cfg.top_k,
        }
        if errors:
            query_echo["errors"] = errors
        return SubgraphContext(
            protocol="graphrag/1.0",
            operation="federated_search",
            query=query_echo,
            results={
                "entities": merged_entities,
                "relationships": list(relationships.values())[: cfg.top_k],
                "paths": list(paths.values())[: cfg.top_k],
                "communities": list(communities.values())[: cfg.top_k],
                "text_chunks": list(chunks.values())[: cfg.top_k],
            },
            provenance=Provenance(
                source_documents=list(dict.fromkeys(sources))[:50],
                traversal_log=[],
                visited_not_cited=list(dict.fromkeys(v for v in visited if v))[:100],
                total_entities_examined=len(entities),
                total_chunks_returned=len(chunks),
                backend="federation",
                backend_version=f"{len(refs)} backends",
            ),
            metrics=RetrievalMetrics(
                input_tokens=len(str(query_echo)),
                entities_returned=len(merged_entities),
                relationships_returned=len(relationships),
                paths_found=len(paths),
                communities_matched=len(communities),
                graph_hops_traversed=max(
                    (int(c.metrics.graph_hops_traversed) for _, c, _, _ in per_backend if c is not None),
                    default=0,
                ),
                latency_ms=round(latency_ms, 2),
            ),
        )

    @staticmethod
    def _collect(
        ctx: SubgraphContext,
        ref: BackendRef,
        relationships: dict[str, dict[str, Any]],
        paths: dict[str, dict[str, Any]],
        communities: dict[str, dict[str, Any]],
        chunks: dict[str, dict[str, Any]],
    ) -> None:
        """Merge non-entity result categories, de-duplicated by id."""
        for bucket, items in (
            (relationships, ctx.results.get("relationships", [])),
            (paths, ctx.results.get("paths", [])),
            (communities, ctx.results.get("communities", [])),
            (chunks, ctx.results.get("text_chunks", [])),
        ):
            for item in items:
                key = str(item.get("id") or f"{item.get('source')}->{item.get('target')}")
                if key and key not in bucket:
                    merged = dict(item)
                    merged["backends"] = [ref.name]
                    bucket[key] = merged

    # -- cross-graph entity linking ---------------------------------------------

    def cross_graph_entity_link(
        self,
        entity_name: str,
        config: FederationConfig | None = None,
        entity_type: str | None = None,
        limit: int = 5,
    ) -> list[EntityLink]:
        """Find the same real-world entity across federated graphs.

        Each backend is probed with a live ``entity_lookup``; matches are
        scored by id/name agreement (exact name or id match 1.0, substring
        containment 0.6).

        Args:
            entity_name: Entity name (or id) to resolve everywhere.
            config: Federation policy (backends list).
            entity_type: Optional vertex-type restriction.
            limit: Maximum links returned, best score first.

        Returns:
            Sorted :class:`EntityLink` candidates.
        """
        if not entity_name or not entity_name.strip():
            raise ValueError("cross_graph_entity_link requires a non-empty entity_name")
        cfg = config or FederationConfig()
        refs = cfg.backends or [
            BackendRef(name="primary", graph_id=getattr(self._primary, "_graphname", "primary"), weight=1.0)
        ]
        target = entity_name.strip().lower()
        links: list[EntityLink] = []
        for ref in refs:
            try:
                adapter = self._resolve(ref)
                ctx = adapter.entity_lookup(entity_name=entity_name, entity_type=entity_type, depth=0)
            except Exception as exc:  # noqa: BLE001 - a missing backend is not a link
                print(f"[federation] link probe failed on {ref.name} ({ref.graph_id}): {type(exc).__name__}")
                continue
            for ent in ctx.results.get("entities", []) or []:
                name = str(ent.get("name") or "").strip().lower()
                eid = str(ent.get("id") or "").strip().lower()
                if name == target or eid == target:
                    score = 1.0
                elif target in name or (name and name in target):
                    score = 0.6
                else:
                    continue
                links.append(
                    EntityLink(
                        entity_name=str(ent.get("name") or entity_name),
                        graph_id=ref.graph_id,
                        entity_id=str(ent.get("id") or ""),
                        entity_type=str(ent.get("type") or entity_type or "unknown"),
                        score=score * ref.weight,
                    )
                )
        links.sort(key=lambda link: -link.score)
        return links[:limit]
