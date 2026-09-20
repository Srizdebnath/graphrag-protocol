"""Contract 14: Diff — deterministic delta between two SubgraphContexts.

Compares entities, relationships, communities, and text chunks between two
retrieval results. Used to detect knowledge-graph evolution between ingestion
runs or to compare different query results. No mocks, no synthesis — only
actual structural comparison of the two contexts.
"""
from __future__ import annotations

from typing import Any

from mcp_server.adapters.base import BaseGraphRAGAdapter
from mcp_server.protocol import SubgraphContext


class DiffContract:
    """Contract 14: structural diff between two SubgraphContexts.

    Compares by entity id, relationship id, community id, and text chunk id.
    All counts in the result are measured — nothing is estimated.

    Args:
        adapter: The backend adapter (used for live queries when query IDs are given).
    """

    def __init__(self, adapter: BaseGraphRAGAdapter) -> None:
        if adapter is None:
            raise ValueError("DiffContract requires a non-None adapter")
        self._adapter = adapter

    def diff_contexts(
        self,
        context_a: SubgraphContext,
        context_b: SubgraphContext,
        label_a: str = "a",
        label_b: str = "b",
    ) -> dict[str, Any]:
        """Compare two SubgraphContexts and return the structural delta.

        Args:
            context_a: First context (baseline).
            context_b: Second context (comparison).
            label_a: Human-readable label for context_a.
            label_b: Human-readable label for context_b.

        Returns:
            Dict with `entities`, `relationships`, `communities`, `text_chunks`,
            each having `added`, `removed`, `common` sub-lists, plus summary counts.
        """
        if context_a is None or context_b is None:
            raise ValueError("diff_contexts requires two non-None SubgraphContext instances")

        entity_diff = self._diff_list(
            context_a.results.get("entities") or [],
            context_b.results.get("entities") or [],
            key="id",
        )
        rel_diff = self._diff_list(
            context_a.results.get("relationships") or [],
            context_b.results.get("relationships") or [],
            key="id",
        )
        community_diff = self._diff_list(
            context_a.results.get("communities") or [],
            context_b.results.get("communities") or [],
            key="id",
        )
        chunk_diff = self._diff_list(
            context_a.results.get("text_chunks") or [],
            context_b.results.get("text_chunks") or [],
            key="id",
        )

        prov_diff = self._diff_provenance(context_a, context_b)

        return {
            "label_a": label_a,
            "label_b": label_b,
            "entities": entity_diff,
            "relationships": rel_diff,
            "communities": community_diff,
            "text_chunks": chunk_diff,
            "provenance": prov_diff,
            "summary": {
                "entities_added": len(entity_diff["added"]),
                "entities_removed": len(entity_diff["removed"]),
                "entities_common": len(entity_diff["common"]),
                "relationships_added": len(rel_diff["added"]),
                "relationships_removed": len(rel_diff["removed"]),
                "total_changes": (
                    len(entity_diff["added"]) + len(entity_diff["removed"]) +
                    len(rel_diff["added"]) + len(rel_diff["removed"])
                ),
            },
        }

    def diff_queries(
        self,
        query_a: str,
        query_b: str,
        mode: str = "auto",
        top_k: int = 10,
        depth: int = 2,
    ) -> dict[str, Any]:
        """Run two queries and return the diff of their results.

        Args:
            query_a: First query text.
            query_b: Second query text.
            mode: Retrieval mode for both queries.
            top_k: Max results per query.
            depth: Graph depth per query.

        Returns:
            Same diff structure as diff_contexts.
        """
        from mcp_server.contracts.retrieval import RetrievalContract
        retrieval = RetrievalContract(self._adapter)
        result_a = retrieval.search(query=query_a, mode=mode, top_k=top_k, depth=depth)
        result_b = retrieval.search(query=query_b, mode=mode, top_k=top_k, depth=depth)
        return self.diff_contexts(
            result_a.context, result_b.context,
            label_a=query_a[:50], label_b=query_b[:50]
        )

    @staticmethod
    def _diff_list(
        items_a: list[dict[str, Any]],
        items_b: list[dict[str, Any]],
        key: str = "id",
    ) -> dict[str, Any]:
        """Diff two item lists by a key field."""
        map_a = {str(item.get(key, i)): item for i, item in enumerate(items_a)}
        map_b = {str(item.get(key, i)): item for i, item in enumerate(items_b)}
        keys_a = set(map_a)
        keys_b = set(map_b)
        added_keys = keys_b - keys_a
        removed_keys = keys_a - keys_b
        common_keys = keys_a & keys_b
        return {
            "added": [map_b[k] for k in sorted(added_keys)],
            "removed": [map_a[k] for k in sorted(removed_keys)],
            "common": [map_a[k] for k in sorted(common_keys)],
        }

    @staticmethod
    def _diff_provenance(ctx_a: SubgraphContext, ctx_b: SubgraphContext) -> dict[str, Any]:
        """Diff the provenance trails of two contexts."""
        docs_a = set(ctx_a.provenance.source_documents)
        docs_b = set(ctx_b.provenance.source_documents)
        return {
            "source_docs_added": sorted(docs_b - docs_a),
            "source_docs_removed": sorted(docs_a - docs_b),
            "source_docs_common": sorted(docs_a & docs_b),
            "latency_ms_a": ctx_a.metrics.latency_ms,
            "latency_ms_b": ctx_b.metrics.latency_ms,
            "entities_examined_a": ctx_a.provenance.total_entities_examined,
            "entities_examined_b": ctx_b.provenance.total_entities_examined,
        }
