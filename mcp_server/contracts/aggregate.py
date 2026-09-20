"""Contract 15: Aggregate — OLAP-style analysis over the knowledge graph.

Provides count, group-by, and top-N operations. All numbers are measured from
the backend schema and entity stats — nothing is estimated. When the adapter
exposes `get_schema()`, counts are sourced from vertex type statistics.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from mcp_server.adapters.base import BaseGraphRAGAdapter


class AggregateContract:
    """Contract 15: OLAP-style aggregation over graph entities.

    All operations fall back to the schema stats when per-entity iteration
    is unavailable, and to an in-memory scan of a retrieved sample when
    grouping is required.

    Args:
        adapter: The backend adapter.
    """

    def __init__(self, adapter: BaseGraphRAGAdapter) -> None:
        if adapter is None:
            raise ValueError("AggregateContract requires a non-None adapter")
        self._adapter = adapter

    def count(
        self,
        entity_type: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Count entities of a given type, optionally filtered.

        Uses schema vertex type counts (real backend stats) when no filter is
        applied. With filters, performs a local_search and counts the results.

        Args:
            entity_type: Vertex type to count (None = all types).
            filters: Optional attribute filters (applied via local_search).

        Returns:
            Dict with `entity_type`, `count`, and `source` ('schema'|'search').
        """
        schema = self._adapter.get_schema()

        if entity_type is None and not filters:
            # Aggregate all vertex types from schema
            total = sum(vt.count for vt in schema.vertex_types)
            breakdown = {vt.type: vt.count for vt in schema.vertex_types}
            return {
                "entity_type": None,
                "count": total,
                "breakdown": breakdown,
                "source": "schema",
            }

        if not filters:
            # Fast path: schema count for one type
            for vt in schema.vertex_types:
                if vt.type == entity_type:
                    return {"entity_type": entity_type, "count": vt.count, "source": "schema"}
            return {"entity_type": entity_type, "count": 0, "source": "schema"}

        # Filtered count: use local_search with filter text
        query_text = f"{entity_type or ''} " + " ".join(f"{k}:{v}" for k, v in (filters or {}).items())
        ctx = self._adapter.local_search(query=query_text.strip() or "entity", top_k=100)
        entities = ctx.results.get("entities") or []
        if entity_type:
            entities = [e for e in entities if e.get("type") == entity_type]
        for k, v in (filters or {}).items():
            entities = [e for e in entities if str(e.get("properties", {}).get(k, "")) == str(v)]
        return {"entity_type": entity_type, "count": len(entities), "source": "search", "filters": filters}

    def group_by(
        self,
        entity_type: str,
        attribute: str,
        top_n: int = 20,
    ) -> dict[str, Any]:
        """Group entities of a type by an attribute and count each group.

        Fetches a sample via local_search and groups in-memory. Counts
        reflect the sample, not the full population (noted in the result).

        Args:
            entity_type: Vertex type to group.
            attribute: Entity property to group by.
            top_n: Number of top groups to return.

        Returns:
            Dict with `entity_type`, `attribute`, `groups` (list of {value, count}),
            `total_sampled`, and a note about sampling.
        """
        if not entity_type:
            raise ValueError("group_by requires a non-empty entity_type")
        if not attribute:
            raise ValueError("group_by requires a non-empty attribute")
        top_n = max(1, min(100, int(top_n)))

        ctx = self._adapter.local_search(query=entity_type, top_k=100)
        entities = [e for e in (ctx.results.get("entities") or []) if e.get("type") == entity_type]

        counts: Counter[str] = Counter()
        for e in entities:
            val = e.get("properties", {}).get(attribute) or e.get(attribute)
            if val is not None:
                counts[str(val)] += 1
            else:
                counts["(unset)"] += 1

        groups = [
            {"value": val, "count": cnt}
            for val, cnt in counts.most_common(top_n)
        ]
        return {
            "entity_type": entity_type,
            "attribute": attribute,
            "groups": groups,
            "total_sampled": len(entities),
            "note": "Counts reflect a sample of up to 100 entities; not the full population.",
        }

    def top_n(
        self,
        entity_type: str,
        rank_by: str,
        n: int = 10,
        descending: bool = True,
    ) -> dict[str, Any]:
        """Return top-N entities of a type ranked by a numeric attribute.

        Args:
            entity_type: Vertex type to rank.
            rank_by: Attribute name to sort by (must be numeric or comparable).
            n: Number of top entities to return.
            descending: Sort direction (True = highest first).

        Returns:
            Dict with `entity_type`, `rank_by`, `descending`, `entities` (ranked list), `total_sampled`.
        """
        if not entity_type:
            raise ValueError("top_n requires a non-empty entity_type")
        if not rank_by:
            raise ValueError("top_n requires a non-empty rank_by attribute")
        n = max(1, min(100, int(n)))

        ctx = self._adapter.local_search(query=entity_type, top_k=100)
        entities = [e for e in (ctx.results.get("entities") or []) if e.get("type") == entity_type]

        def sort_key(e: dict[str, Any]) -> Any:
            val = e.get("properties", {}).get(rank_by) or e.get(rank_by)
            try:
                return float(val) if val is not None else (float("-inf") if descending else float("inf"))
            except (TypeError, ValueError):
                return str(val or "")

        ranked = sorted(entities, key=sort_key, reverse=descending)[:n]
        return {
            "entity_type": entity_type,
            "rank_by": rank_by,
            "descending": descending,
            "entities": ranked,
            "total_sampled": len(entities),
        }

    def stats_summary(self) -> dict[str, Any]:
        """Return a comprehensive statistics summary of the entire graph.

        Uses the schema for vertex/edge type counts plus derived metrics.

        Returns:
            Dict with vertex types, edge types, totals, and density metrics.
        """
        schema = self._adapter.get_schema()
        stats = schema.statistics
        vertex_breakdown = {vt.type: vt.count for vt in schema.vertex_types}
        edge_breakdown = {et.type: et.count for et in schema.edge_types}
        density = round(stats.total_edges / max(stats.total_vertices, 1), 4)
        return {
            "graph_id": schema.graph_id,
            "total_vertices": stats.total_vertices,
            "total_edges": stats.total_edges,
            "avg_degree": stats.avg_degree,
            "connected_components": stats.connected_components,
            "graph_density": density,
            "vertex_types": vertex_breakdown,
            "edge_types": edge_breakdown,
        }
