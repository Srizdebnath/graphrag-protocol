"""Contract 1: Retrieval.

Concrete implementation of :class:`BaseRetrievalContract`. Wraps a backend
adapter and layers protocol-smart logic on top of its raw operations:
parameter validation, sensible defaults, query auto-routing, and response
normalization into protocol models via a ``build_response`` helper.
"""

from __future__ import annotations

from typing import Any

from mcp_server.adapters.base import BaseGraphRAGAdapter
from mcp_server.contracts.base import BaseRetrievalContract
from mcp_server.protocol import (
    Provenance,
    RetrievalMetrics,
    RetrievalResult,
    SubgraphContext,
)


class RetrievalContract(BaseRetrievalContract):
    """Contract 1: the seven retrieval operations against a backend adapter.

    Each operation validates its inputs, delegates to the adapter, and
    normalizes the adapter's (possibly raw/dict) output into a fully
    populated :class:`SubgraphContext` through :meth:`build_response`.
    """

    def __init__(self, adapter: BaseGraphRAGAdapter) -> None:
        """Wrap a backend adapter.

        Args:
            adapter: A :class:`BaseGraphRAGAdapter` instance. If ``None`` is
                passed, operations raise a clear error.

        Raises:
            ValueError: If ``adapter`` is ``None``.
        """
        if adapter is None:
            raise ValueError("RetrievalContract requires a non-None adapter")
        self._adapter: BaseGraphRAGAdapter = adapter

    # -- response normalization -------------------------------------------------

    def build_response(
        self,
        operation: str,
        query_echo: dict[str, Any],
        raw: SubgraphContext | None = None,
        provenance: Provenance | None = None,
        metrics: RetrievalMetrics | None = None,
    ) -> SubgraphContext:
        """Assemble a complete :class:`SubgraphContext` from adapter output.

        When ``raw`` is a proper :class:`SubgraphContext`, its ``results``
        are re-used; otherwise a default, empty result envelope is used.
        Provenance and metrics are supplied either explicitly or derived
        from the raw context.

        Args:
            operation: The operation name echoed on the context.
            query_echo: The original request, echoed back for auditability.
            raw: Raw adapter output (e.g., a dict or a context).
            provenance: Optional provenance to attach (else derived from raw).
            metrics: Optional metrics to attach (else derived from raw).

        Returns:
            A fully populated :class:`SubgraphContext`.
        """
        results: dict[str, Any] = {
            "entities": [],
            "relationships": [],
            "paths": [],
            "communities": [],
            "text_chunks": [],
        }
        if isinstance(raw, SubgraphContext):
            results = raw.results
            if provenance is None:
                provenance = raw.provenance
            raw_metrics = raw.metrics
        elif isinstance(raw, dict):
            results = {**results, **raw.get("results", {})}
            if provenance is None and "provenance" in raw:
                provenance = Provenance(**raw["provenance"])
            raw_metrics = RetrievalMetrics(**raw["metrics"]) if "metrics" in raw else None
        else:
            raw_metrics = None

        if provenance is None:
            provenance = self._derive_provenance(results)
        if metrics is None:
            hops = int(query_echo.get("depth", 0)) if isinstance(query_echo, dict) else 0
            metrics = self._derive_metrics(
                results=results,
                input_tokens=len(str(query_echo)),
                hops=hops,
            )
            if raw_metrics is not None:
                metrics = metrics.model_copy(
                    update={
                        "latency_ms": raw_metrics.latency_ms,
                        "graph_hops_traversed": raw_metrics.graph_hops_traversed,
                        "input_tokens": raw_metrics.input_tokens or metrics.input_tokens,
                    }
                )

        return SubgraphContext(
            operation=operation,
            query=query_echo,
            results=results,
            provenance=provenance,
            metrics=metrics,
        )

    def _derive_provenance(self, results: dict[str, Any]) -> Provenance:
        """Derive minimal provenance when the backend produces none."""
        entities = results.get("entities", []) or []
        chunks = results.get("text_chunks", []) or []
        source_docs: set[str] = set()
        for c in chunks:
            if isinstance(c, dict) and c.get("source_doc"):
                source_docs.add(str(c["source_doc"]))
        return Provenance(
            source_documents=sorted(source_docs),
            total_entities_examined=len(entities),
            total_chunks_examined=len(chunks),
            total_chunks_returned=len(chunks),
        )

    def _derive_metrics(
        self,
        results: dict[str, Any],
        input_tokens: int,
        latency_ms: float = 0.0,
        hops: int = 0,
    ) -> RetrievalMetrics:
        """Compute standard metrics from the result envelope.

        Args:
            results: The result sub-dict of a context.
            input_tokens: Tokens consumed by the request text.
            latency_ms: End-to-end latency in milliseconds.
            hops: Graph hops traversed (from depth or path).

        Returns:
            A populated :class:`RetrievalMetrics`.
        """
        return RetrievalMetrics(
            input_tokens=input_tokens,
            entities_returned=len(results.get("entities", []) or []),
            relationships_returned=len(results.get("relationships", []) or []),
            paths_found=len(results.get("paths", []) or []),
            communities_matched=len(results.get("communities", []) or []),
            graph_hops_traversed=hops,
            latency_ms=latency_ms,
        )

    # -- the seven operations ---------------------------------------------------

    def local_search(
        self,
        query: str,
        entity_hints: list[str] | None = None,
        depth: int = 2,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> SubgraphContext:
        """Precise, entity-centric retrieval around matched entities.

        Delegate to ``adapter.local_search`` after validating that ``query``
        is non-empty and clamping ``depth``/``top_k`` into the protocol
        range [1, 10] / [1, 100].

        Args:
            query: The question or search text.
            entity_hints: Entity names/IDs to seed traversal.
            depth: Maximum hops to traverse.
            top_k: Maximum results per category.
            filters: Optional attribute filters.

        Returns:
            The normalized subgraph context.
        """
        query = self._require_query(query)
        entity_hints = entity_hints or []
        depth = self._clamp(depth, 1, 10)
        top_k = self._clamp(top_k, 1, 100)
        raw = self._adapter.local_search(
            query=query,
            entity_hints=entity_hints,
            depth=depth,
            top_k=top_k,
            filters=filters,
        )
        return self.build_response(
            operation="local_search",
            query_echo=self._echo(query=query, entity_hints=entity_hints, depth=depth, top_k=top_k),
            raw=raw,
        )

    def global_search(
        self,
        query: str,
        community_level: int = 2,
        top_communities: int = 10,
    ) -> SubgraphContext:
        """Broad, corpus-level retrieval via community summaries.

        Args:
            query: The broad question or search text.
            community_level: Hierarchical community level to query.
            top_communities: Maximum number of communities to return.

        Returns:
            The normalized subgraph context.
        """
        query = self._require_query(query)
        community_level = self._clamp(community_level, 0, 20)
        top_communities = self._clamp(top_communities, 1, 100)
        raw = self._adapter.global_search(
            query=query,
            community_level=community_level,
            top_communities=top_communities,
        )
        return self.build_response(
            operation="global_search",
            query_echo=self._echo(query=query, community_level=community_level, top_communities=top_communities),
            raw=raw,
        )

    def hybrid_search(
        self,
        query: str,
        vector_weight: float = 0.5,
        graph_weight: float = 0.5,
        top_k: int = 10,
        depth: int = 2,
    ) -> SubgraphContext:
        """Combined vector-similarity + graph-structure retrieval.

        Weights are normalized so ``vector_weight + graph_weight`` sums to
        one; depth/top_k are clamped to protocol bounds.

        Args:
            query: The question or search text.
            vector_weight: Weight given to vector similarity scores.
            graph_weight: Weight given to graph-structure scores.
            top_k: Maximum results per category.
            depth: Maximum hops to traverse.

        Returns:
            The normalized subgraph context.
        """
        query = self._require_query(query)
        total = vector_weight + graph_weight
        if total > 0:
            vector_weight /= total
            graph_weight /= total
        top_k = self._clamp(top_k, 1, 100)
        depth = self._clamp(depth, 1, 10)
        raw = self._adapter.hybrid_search(
            query=query,
            vector_weight=vector_weight,
            graph_weight=graph_weight,
            top_k=top_k,
            depth=depth,
        )
        return self.build_response(
            operation="hybrid_search",
            query_echo=self._echo(
                query=query,
                vector_weight=vector_weight,
                graph_weight=graph_weight,
                top_k=top_k,
                depth=depth,
            ),
            raw=raw,
        )

    def entity_lookup(
        self,
        entity_id: str | None = None,
        entity_name: str | None = None,
        entity_type: str | None = None,
        depth: int = 1,
    ) -> SubgraphContext:
        """Fetch a specific entity and its immediate context.

        Requires exactly one of ``entity_id`` or ``entity_name``.

        Args:
            entity_id: Backend-agnostic entity ID.
            entity_name: Entity name to resolve.
            entity_type: Type filter for name resolution.
            depth: Maximum hops to traverse around the matched entity.

        Returns:
            The normalized subgraph context.

        Raises:
            ValueError: If neither ``entity_id`` nor ``entity_name`` is given.
        """
        if entity_id is None and entity_name is None:
            raise ValueError(
                "entity_lookup requires exactly one of entity_id or entity_name"
            )
        depth = self._clamp(depth, 1, 10)
        raw = self._adapter.entity_lookup(
            entity_id=entity_id,
            entity_name=entity_name,
            entity_type=entity_type,
            depth=depth,
        )
        return self.build_response(
            operation="entity_lookup",
            query_echo=self._echo(
                entity_id=entity_id,
                entity_name=entity_name,
                entity_type=entity_type,
                depth=depth,
            ),
            raw=raw,
        )

    def path_search(
        self,
        source: str,
        target: str,
        max_hops: int = 4,
    ) -> SubgraphContext:
        """Find paths between two entities.

        Args:
            source: Source entity name or ID.
            target: Target entity name or ID.
            max_hops: Maximum allowed path length.

        Returns:
            The normalized subgraph context.
        """
        if not source or not target:
            raise ValueError("path_search requires non-empty source and target")
        if source == target:
            raise ValueError("path_search source and target must differ")
        max_hops = self._clamp(max_hops, 1, 10)
        raw = self._adapter.path_search(
            source=source,
            target=target,
            max_hops=max_hops,
        )
        return self.build_response(
            operation="path_search",
            query_echo=self._echo(source=source, target=target, max_hops=max_hops),
            raw=raw,
        )

    def neighborhood(
        self,
        entity_id: str,
        depth: int = 2,
        edge_types: list[str] | None = None,
    ) -> SubgraphContext:
        """Expand outward from an entity within ``depth`` hops.

        Args:
            entity_id: Seed entity ID.
            depth: Maximum hops to traverse.
            edge_types: Optional edge types to restrict traversal.

        Returns:
            The normalized subgraph context.
        """
        if not entity_id:
            raise ValueError("neighborhood requires a non-empty entity_id")
        depth = self._clamp(depth, 1, 10)
        edge_types = edge_types or None
        raw = self._adapter.neighborhood(
            entity_id=entity_id,
            depth=depth,
            edge_types=edge_types,
        )
        return self.build_response(
            operation="neighborhood",
            query_echo=self._echo(entity_id=entity_id, depth=depth, edge_types=edge_types),
            raw=raw,
        )

    def community_members(
        self,
        community_id: str,
        include_summary: bool = True,
    ) -> SubgraphContext:
        """List member entities of a community (optionally with summary).

        Args:
            community_id: Community identifier.
            include_summary: Whether to include the community summary text.

        Returns:
            The normalized subgraph context.
        """
        if not community_id:
            raise ValueError("community_members requires a non-empty community_id")
        raw = self._adapter.community_members(
            community_id=community_id,
            include_summary=include_summary,
        )
        return self.build_response(
            operation="community_members",
            query_echo=self._echo(community_id=community_id, include_summary=include_summary),
            raw=raw,
        )

    # -- auto-routing -----------------------------------------------------------

    def search(self, query: str, mode: str = "auto", **kwargs: Any) -> RetrievalResult:
        """Auto-routing dispatcher over the seven retrieval operations.

        When ``mode`` is ``'auto'``, the query text is classified by
        heuristic and dispatched to the most appropriate operation:
        global summarisation queries -> ``global_search``; queries that
        mention a known entity-like token -> ``entity_lookup``; everything
        else -> ``hybrid_search``.

        Args:
            query: The natural-language query or search text.
            mode: Exactly ``'auto'``, ``'local'``, ``'global'``,
                ``'hybrid'``, or ``'entity'``. Unknown modes raise.
            **kwargs: Extra parameters forwarded to the chosen operation.

        Returns:
            A :class:`RetrievalResult` wrapping the subgraph context.

        Raises:
            ValueError: If ``mode`` is not one of the supported values.
        """
        query = self._require_query(query)
        mode = mode.lower()
        supported = {"auto", "local", "global", "hybrid", "entity"}
        if mode not in supported:
            raise ValueError(
                f"Unknown search mode {mode!r}; expected one of {sorted(supported)}"
            )

        if mode == "auto":
            mode = self.classify_query(query)

        if mode == "global":
            context = self.global_search(query, **kwargs)
        elif mode == "local":
            context = self.local_search(query, **kwargs)
        elif mode == "entity":
            entity_name = kwargs.pop("entity_name", query)
            # entity_lookup only accepts entity_id/name/type/depth; drop any
            # retrieval params (e.g. top_k) that other operations accept.
            allowed = {"entity_id", "entity_type", "depth"}
            context = self.entity_lookup(
                entity_name=entity_name,
                **{k: v for k, v in kwargs.items() if k in allowed},
            )
        else:  # hybrid fallback default
            context = self.hybrid_search(query, **kwargs)

        return RetrievalResult(context=context, formatted=None)

    def classify_query(self, query: str) -> str:
        """Classify a query into a retrieval mode by lightweight heuristics.

        Lowercased text is matched against phrase patterns:

        - Global summarisation phrases -> ``'global'``.
        - Bare, short entity-like tokens -> ``'entity'``.
        - Otherwise -> ``'hybrid'``.

        Args:
            query: The query text to classify.

        Returns:
            One of ``'global'``, ``'entity'``, or ``'hybrid'``.
        """
        text = query.strip().lower()

        global_patterns = (
            "what are the main themes",
            "overall",
            "main themes",
            "summarize",
            "trends",
            "summarise",
            "what's the big picture",
            "overview of the field",
            "key developments",
        )
        if any(p in text for p in global_patterns):
            return "global"

        if len(text.split()) <= 4 and not text.endswith("?"):
            return "entity"

        return "hybrid"

    # -- helpers ----------------------------------------------------------------

    @staticmethod
    def _require_query(query: str) -> str:
        """Validate that a query string is non-empty.

        Args:
            query: The query text.

        Returns:
            The stripped query.

        Raises:
            ValueError: If the query is empty/whitespace-only.
        """
        query = (query or "").strip()
        if not query:
            raise ValueError("query must be a non-empty string")
        return query

    @staticmethod
    def _clamp(value: int, lo: int, hi: int) -> int:
        """Clamp an integer into the inclusive range ``[lo, hi]``.

        Args:
            value: The value to clamp.
            lo: Inclusive lower bound.
            hi: Inclusive upper bound.

        Returns:
            The clamped value.
        """
        return max(lo, min(hi, int(value)))

    @staticmethod
    def _echo(**kwargs: Any) -> dict[str, Any]:
        """Build a request-echo dict, dropping ``None`` values.

        Args:
            **kwargs: The request fields.

        Returns:
            A dict safe for use as ``SubgraphContext.query``.
        """
        return {k: v for k, v in kwargs.items() if v is not None}
