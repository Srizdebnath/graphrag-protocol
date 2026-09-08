"""Abstract retrieval contract interface.

Defines the seven standard retrieval operations every GraphRAG backend
must support. Concrete implementations wrap a backend adapter and know
how to map request semantics onto the adapter's primitives.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from mcp_server.protocol import SubgraphContext


class BaseRetrievalContract(ABC):
    """Contract 1: Abstract interface for the seven retrieval operations.

    Every operation accepts the same conceptual arguments and returns a
    :class:`SubgraphContext`, so callers (agents, the MCP server, other
    contracts) get a uniform response regardless of backend.
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
        """Contract 1 local_search: answer a question using a precise
        subgraph around matched entities.

        Seeds from ``entity_hints`` (or entities matched from ``query``),
        expands up to ``depth`` hops, and returns the most relevant
        entities, relationships, and supporting text chunks. Intended for
        precise, entity-centric questions.

        Args:
            query: The question or search text.
            entity_hints: Entity names/IDs to seed traversal.
            depth: Maximum hops to traverse (bounded by protocol [1, 10]).
            top_k: Maximum results per category.
            filters: Optional attribute filters.

        Returns:
            The retrieved subgraph context with provenance and metrics.
        """
        ...

    @abstractmethod
    def global_search(
        self,
        query: str,
        community_level: int = 2,
        top_communities: int = 10,
    ) -> SubgraphContext:
        """Contract 1 global_search: answer via community summaries.

        Routes the question against synthesized community summaries at a
        given hierarchical level, returning the most relevant communities.
        Intended for broad, corpus-level questions where no single entity
        is the answer.

        Args:
            query: The broad question or search text.
            community_level: Hierarchical community level to query.
            top_communities: Maximum number of communities to return.

        Returns:
            Subgraph context containing matched community summaries and
            representative supporting entities/chunks.
        """
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
        """Contract 1 hybrid_search: combine vector similarity and graph
        traversal scores.

        Runs a vector (semantic) search and a graph (structural) search,
        fuses the ranked results using ``vector_weight``/``graph_weight``,
        and expands the fused seeds through the graph.

        Args:
            query: The question or search text.
            vector_weight: Weight given to vector similarity scores.
            graph_weight: Weight given to graph-structure scores.
            top_k: Maximum results per category.
            depth: Maximum hops to traverse.

        Returns:
            The fused subgraph context with provenance and metrics.
        """
        ...

    @abstractmethod
    def entity_lookup(
        self,
        entity_id: str | None = None,
        entity_name: str | None = None,
        entity_type: str | None = None,
        depth: int = 1,
    ) -> SubgraphContext:
        """Contract 1 entity_lookup: fetch a specific entity and its
        immediate context.

        Exactly one of ``entity_id`` or ``entity_name`` (optionally scoped
        by ``entity_type``) is expected. Returns the matched entity plus a
        small neighborhood to provide context.

        Args:
            entity_id: Backend-agnostic entity ID.
            entity_name: Entity name to resolve.
            entity_type: Type filter for name resolution.
            depth: Maximum hops to traverse around the matched entity.

        Returns:
            Subgraph context centered on the matched entity.
        """
        ...

    @abstractmethod
    def path_search(
        self,
        source: str,
        target: str,
        max_hops: int = 4,
    ) -> SubgraphContext:
        """Contract 1 path_search: find paths between two entities.

        Returns the most relevant (shortest/highest-scored) paths between
        ``source`` and ``target`` within ``max_hops``, used for explaining
        connections, e.g., 'How are X and Y related?'.

        Args:
            source: Source entity name or ID.
            target: Target entity name or ID.
            max_hops: Maximum allowed path length.

        Returns:
            Subgraph context whose results include the discovered paths.
        """
        ...

    @abstractmethod
    def neighborhood(
        self,
        entity_id: str,
        depth: int = 2,
        edge_types: list[str] | None = None,
    ) -> SubgraphContext:
        """Contract 1 neighborhood: expand outward from an entity.

        Returns all entities reachable from ``entity_id`` within ``depth``
        hops, optionally restricted to ``edge_types``. Used for exploration
        and answer-reranking context.

        Args:
            entity_id: Seed entity ID.
            depth: Maximum hops to traverse.
            edge_types: Optional list of edge types to restrict traversal.

        Returns:
            Subgraph context containing the expanded neighborhood.
        """
        ...

    @abstractmethod
    def community_members(
        self,
        community_id: str,
        include_summary: bool = True,
    ) -> SubgraphContext:
        """Contract 1 community_members: list members of a community.

        Returns the entities belonging to ``community_id`` and, when
        ``include_summary`` is true, the community summary.

        Args:
            community_id: Community identifier.
            include_summary: Whether to include the community summary text.

        Returns:
            Subgraph context containing community members and (optionally)
            the community summary.
        """
        ...