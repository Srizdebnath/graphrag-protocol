"""Abstract GraphRAG backend adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from mcp_server.protocol import (
    GraphSchema,
    Provenance,
    SubgraphContext,
)


class BaseGraphRAGAdapter(ABC):
    """Abstract adapter every GraphRAG backend must implement.

    Extends the retrieval contract with schema discovery, provenance
    extraction, and health reporting. Concrete adapters (TigerGraph,
    Neo4j, LightRAG, vector stores, ...) translate these standard
    operations onto their native query APIs.
    """

    @abstractmethod
    def local_search(
        self,
        query: str,
        entity_hints: list[str] | None = None,
        depth: int = 2,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> SubgraphContext:
        """Precise, entity-centric retrieval around matched entities.

        Seeds from ``entity_hints`` (or entities matched from ``query``),
        expands up to ``depth`` hops, and returns the most relevant
        entities, relationships, and supporting text chunks.
        """
        ...

    @abstractmethod
    def global_search(
        self,
        query: str,
        community_level: int = 2,
        top_communities: int = 10,
    ) -> SubgraphContext:
        """Broad, corpus-level retrieval via community summaries."""
        ...

    @abstractmethod
    def hybrid_search(
        self,
        query: str,
        vector_weight: float = 0.5,
        graph_weight: float = 0.5,
        top_k: int = 10,
        depth: int = 2,
    ) -> SubgraphContext:
        """Combined vector-similarity + graph-structure retrieval."""
        ...

    @abstractmethod
    def entity_lookup(
        self,
        entity_id: str | None = None,
        entity_name: str | None = None,
        entity_type: str | None = None,
        depth: int = 1,
    ) -> SubgraphContext:
        """Fetch a specific entity and its immediate context."""
        ...

    @abstractmethod
    def path_search(
        self,
        source: str,
        target: str,
        max_hops: int = 4,
    ) -> SubgraphContext:
        """Find paths between two entities."""
        ...

    @abstractmethod
    def neighborhood(
        self,
        entity_id: str,
        depth: int = 2,
        edge_types: list[str] | None = None,
    ) -> SubgraphContext:
        """Expand outward from an entity within ``depth`` hops."""
        ...

    @abstractmethod
    def community_members(
        self,
        community_id: str,
        include_summary: bool = True,
    ) -> SubgraphContext:
        """List member entities of a community (optionally with summary)."""
        ...

    @abstractmethod
    def get_schema(self, graph_id: str | None = None) -> GraphSchema:
        """Introspect the graph schema.

        Returns vertex/edge types, attributes, cardinalities, and
        graph-level statistics in the standard GraphSchema form.
        """
        ...

    @abstractmethod
    def get_provenance(self, context: SubgraphContext) -> Provenance:
        """Extract the citation and audit trail for a retrieval context.

        Reconstructs source documents, traversal steps, and visited-but-
        not-cited entities from the adapter's internal execution state.
        """
        ...

    @abstractmethod
    def health_check(self) -> dict:
        """Report backend connectivity and health.

        Returns a dict with at least ``status`` ("ok"/"error"), and
        typically ``backend`` and ``version`` keys.
        """
        ...

    def embed_text(self, text: str) -> list[float] | None:
        """Optional vector embedding for semantic similarity (Contract 11)."""
        return None