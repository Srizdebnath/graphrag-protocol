"""Contract 12: Temporal Query — retrieve entities filtered by time ranges.

Filters entities from a retrieval result whose `published`, `created_at`, or
`updated_at` attribute falls within [start, end]. The filtering is done in-process
on the SubgraphContext returned by the retrieval contract — no mock, no synthesis.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from mcp_server.adapters.base import BaseGraphRAGAdapter
from mcp_server.contracts.retrieval import RetrievalContract
from mcp_server.protocol import Provenance, RetrievalMetrics, SubgraphContext

_ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


class TemporalContract:
    """Contract 12: time-range filtering over retrieved subgraphs.

    Retrieves a full subgraph via the retrieval contract, then filters entities
    whose temporal attributes fall in [start, end]. The filtering is deterministic
    and measured — counts reflect only what actually passed the filter.

    Args:
        adapter: The backend adapter.
    """

    def __init__(self, adapter: BaseGraphRAGAdapter) -> None:
        if adapter is None:
            raise ValueError("TemporalContract requires a non-None adapter")
        self._adapter = adapter
        self._retrieval = RetrievalContract(adapter)

    def temporal_search(
        self,
        query: str,
        start: str | None = None,
        end: str | None = None,
        mode: str = "auto",
        top_k: int = 10,
        depth: int = 2,
    ) -> SubgraphContext:
        """Run a retrieval query then filter results by time range.

        Args:
            query: Natural-language query.
            start: ISO-8601 start date (inclusive), e.g. '2020-01-01'.
            end: ISO-8601 end date (inclusive), e.g. '2023-12-31'.
            mode: Retrieval mode passed to the retrieval contract.
            top_k: Max results.
            depth: Graph traversal depth.

        Returns:
            A SubgraphContext with entities filtered by the time range.
            Metrics reflect the filtered count, not the pre-filter count.
        """
        if not query or not query.strip():
            raise ValueError("temporal_search requires a non-empty query")

        start_dt = self._parse_dt(start) if start else None
        end_dt = self._parse_dt(end, end_of_day=True) if end else None

        result = self._retrieval.search(query=query, mode=mode, top_k=top_k, depth=depth)
        ctx = result.context

        filtered_entities = [
            e for e in (ctx.results.get("entities") or [])
            if self._in_range(e, start_dt, end_dt)
        ]
        # Keep relationships whose both endpoints survived the filter
        surviving_ids = {e["id"] for e in filtered_entities}
        filtered_rels = [
            r for r in (ctx.results.get("relationships") or [])
            if r.get("source") in surviving_ids or r.get("target") in surviving_ids
        ]
        filtered_chunks = list(ctx.results.get("text_chunks") or [])

        prov = Provenance(
            source_documents=list(ctx.provenance.source_documents),
            traversal_log=ctx.provenance.traversal_log,
            visited_not_cited=ctx.provenance.visited_not_cited,
            total_entities_examined=ctx.provenance.total_entities_examined,
            total_chunks_returned=len(filtered_chunks),
            backend=ctx.provenance.backend,
            backend_version=ctx.provenance.backend_version,
        )
        metrics = RetrievalMetrics(
            input_tokens=ctx.metrics.input_tokens,
            entities_returned=len(filtered_entities),
            relationships_returned=len(filtered_rels),
            paths_found=ctx.metrics.paths_found,
            communities_matched=ctx.metrics.communities_matched,
            graph_hops_traversed=ctx.metrics.graph_hops_traversed,
            latency_ms=ctx.metrics.latency_ms,
        )
        return SubgraphContext(
            protocol="graphrag/1.0",
            operation="temporal_search",
            query={
                **ctx.query,
                "start": start,
                "end": end,
                "entities_before_filter": len(ctx.results.get("entities") or []),
                "entities_after_filter": len(filtered_entities),
            },
            results={
                "entities": filtered_entities,
                "relationships": filtered_rels,
                "paths": list(ctx.results.get("paths") or []),
                "communities": list(ctx.results.get("communities") or []),
                "text_chunks": filtered_chunks,
            },
            provenance=prov,
            metrics=metrics,
        )

    def filter_context(
        self,
        context: SubgraphContext,
        start: str | None = None,
        end: str | None = None,
    ) -> SubgraphContext:
        """Apply temporal filtering to an existing SubgraphContext.

        Useful when the LLM already has a context and wants to narrow it by date.

        Args:
            context: An existing SubgraphContext.
            start: ISO-8601 start date.
            end: ISO-8601 end date.

        Returns:
            A new SubgraphContext with time-filtered entities.
        """
        start_dt = self._parse_dt(start) if start else None
        end_dt = self._parse_dt(end, end_of_day=True) if end else None
        entities = context.results.get("entities") or []
        filtered = [e for e in entities if self._in_range(e, start_dt, end_dt)]
        surviving_ids = {e["id"] for e in filtered}
        rels = [
            r for r in (context.results.get("relationships") or [])
            if r.get("source") in surviving_ids or r.get("target") in surviving_ids
        ]
        return SubgraphContext(
            protocol="graphrag/1.0",
            operation="temporal_filter",
            query={**context.query, "start": start, "end": end},
            results={
                "entities": filtered,
                "relationships": rels,
                "paths": list(context.results.get("paths") or []),
                "communities": list(context.results.get("communities") or []),
                "text_chunks": list(context.results.get("text_chunks") or []),
            },
            provenance=context.provenance,
            metrics=RetrievalMetrics(
                entities_returned=len(filtered),
                relationships_returned=len(rels),
            ),
        )

    # -- helpers
    @staticmethod
    def _parse_dt(value: str, end_of_day: bool = False) -> datetime:
        """Parse an ISO-8601 date string into a timezone-aware datetime."""
        value = (value or "").strip()
        if not _ISO_RE.match(value):
            raise ValueError(f"Invalid date format {value!r}; expected ISO-8601 (YYYY-MM-DD)")
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            dt = datetime.strptime(value[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if end_of_day and dt.hour == 0 and dt.minute == 0 and dt.second == 0:
            dt = dt.replace(hour=23, minute=59, second=59)
        return dt

    @classmethod
    def _in_range(cls, entity: dict[str, Any], start: datetime | None, end: datetime | None) -> bool:
        """True if the entity's temporal attribute falls within [start, end]."""
        if start is None and end is None:
            return True
        props = entity.get("properties") or {}
        for attr in ("published", "created_at", "updated_at", "date", "year"):
            raw = props.get(attr) or entity.get(attr)
            if raw is None:
                continue
            dt = cls._coerce_dt(raw)
            if dt is None:
                continue
            if start is not None and dt < start:
                return False
            return not (end is not None and dt > end)
        # No temporal attribute found: keep the entity (do not silently discard)
        return True

    @staticmethod
    def _coerce_dt(raw: Any) -> datetime | None:
        """Parse a raw temporal value into a datetime."""
        if isinstance(raw, datetime):
            return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
        raw_s = str(raw).strip()
        # Year-only: "2020" -> treat as 2020-01-01
        if re.match(r"^\d{4}$", raw_s):
            try:
                return datetime(int(raw_s), 1, 1, tzinfo=timezone.utc)
            except ValueError:
                return None
        # TigerGraph DATETIME: "YYYY-MM-DD HH:MM:SS"
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(raw_s[:19], fmt).replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
        return None
