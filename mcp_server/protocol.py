"""Core protocol contract definitions.

Pydantic v2 models for the GraphRAG Protocol. These are the canonical,
backend-agnostic types exchanged between agents, the MCP server, and any
GraphRAG adapter. See SPEC.md for the full specification.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RetrievalMode(str, Enum):
    """The seven retrieval operations supported by the protocol."""

    LOCAL_SEARCH = "local_search"
    GLOBAL_SEARCH = "global_search"
    HYBRID_SEARCH = "hybrid_search"
    ENTITY_LOOKUP = "entity_lookup"
    PATH_SEARCH = "path_search"
    NEIGHBORHOOD = "neighborhood"
    COMMUNITY_MEMBERS = "community_members"


class RetrievalRequest(BaseModel):
    """Contract 1: The standard, backend-agnostic retrieval request.

    Every retrieval operation across every GraphRAG backend is expressed
    with these fields, so agents never need a backend-specific query
    language to interrogate a knowledge graph.
    """

    protocol: str = Field(
        default="graphrag/1.0",
        description="Protocol version identifier.",
    )
    operation: RetrievalMode = Field(
        description="The retrieval operation to execute.",
    )
    query: str = Field(
        description="The natural-language query or search text.",
    )
    entity_hints: list[str] = Field(
        default_factory=list,
        description="Entity names/IDs to seed graph traversal.",
    )
    depth: int = Field(
        default=2,
        ge=1,
        le=10,
        description="Max graph hops to traverse from seed entities.",
    )
    top_k: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Max results to return per result category.",
    )
    filters: dict[str, Any] | None = Field(
        default=None,
        description="Optional attribute filters applied during retrieval.",
    )
    backend: str | None = Field(
        default=None,
        description="Backend/graph identifier for federated or multi-backend environments.",
    )


class Entity(BaseModel):
    """A knowledge-graph entity (vertex)."""

    id: str = Field(description="Backend-agnostic entity identifier.")
    type: str = Field(description="Entity type / vertex label.")
    name: str = Field(description="Human-readable entity name.")
    properties: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary entity attributes.",
    )
    relevance_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Relevance of the entity to the query in [0, 1].",
    )
    source_chunks: list[str] = Field(
        default_factory=list,
        description="IDs of source text chunks supporting this entity.",
    )


class Relationship(BaseModel):
    """A directed edge (relationship) between two entities."""

    id: str = Field(description="Edge identifier.")
    source: str = Field(description="Source entity id.")
    target: str = Field(description="Target entity id.")
    type: str = Field(description="Relationship / edge label.")
    weight: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Edge weight in [0, 1].",
    )
    properties: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary edge attributes.",
    )
    evidence: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Evidence items (e.g., source chunk + snippet) supporting the edge.",
    )


class PathResult(BaseModel):
    """A multi-hop path discovered between entities."""

    entities: list[str] = Field(
        description="Ordered entity ids along the path.",
    )
    relationships: list[str] = Field(
        description="Ordered relationship ids connecting the path entities.",
    )
    path_summary: str = Field(
        description="Human/machine-readable summary of the path.",
    )


class CommunitySummary(BaseModel):
    """A community-detection cluster summary."""

    id: str = Field(description="Community identifier.")
    level: int = Field(description="Hierarchical community level.")
    summary: str = Field(description="Synthesized summary of the community.")
    member_count: int = Field(
        ge=0,
        description="Number of member entities.",
    )
    centroid_entity: str | None = Field(
        default=None,
        description="Optional representative entity id.",
    )


class TextChunk(BaseModel):
    """A source text chunk underlying the retrieved content."""

    id: str = Field(description="Chunk identifier.")
    text: str = Field(description="The chunk text.")
    source_doc: str = Field(description="Source document identifier.")
    token_count: int = Field(
        ge=0,
        description="Approximate token count of the chunk.",
    )
    relevance_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Relevance of the chunk in [0, 1].",
    )


class TraversalStep(BaseModel):
    """A single step in the graph traversal audit log (Contract 5)."""

    step: int = Field(ge=1, description="Step ordinal (1-based).")
    entity: str = Field(description="Entity id visited at this step.")
    action: str = Field(
        description="Action taken (e.g., 'seed', 'expand', 'match', 'prune').",
    )
    edge: str | None = Field(
        default=None,
        description="Edge id traversed to reach this entity.",
    )


class ExtractionRecord(BaseModel):
    """Maps a graph element back to the text span it was extracted from."""

    element_id: str = Field(
        description="The entity or relationship id this record describes.",
    )
    source_doc: str = Field(
        description="The source document from which the element was extracted.",
    )
    chunk_id: str = Field(
        description="The text chunk id containing the extracted span.",
    )
    extracted_text: str = Field(
        description="The verbatim text span that justified extraction.",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Extraction confidence in [0, 1].",
    )


class Provenance(BaseModel):
    """Contract 5: The citation and audit trail for a retrieval.

    Tracks which documents were cited, the exact traversal path taken,
    and which entities were examined but not cited, enabling trajectory
    completeness auditing.
    """

    source_documents: list[str] = Field(
        default_factory=list,
        description="Source document ids cited by the results.",
    )
    traversal_log: list[TraversalStep] = Field(
        default_factory=list,
        description="Ordered step-by-step log of entities visited during traversal.",
    )
    visited_not_cited: list[str] = Field(
        default_factory=list,
        description="Entities examined during traversal but not cited.",
    )
    extraction_provenance: list[ExtractionRecord] = Field(
        default_factory=list,
        description="Mapping of graph elements to the text spans and source documents from which they were extracted.",
    )
    total_entities_examined: int = Field(
        default=0,
        ge=0,
        description="Total number of entities visited during traversal.",
    )
    total_chunks_examined: int = Field(
        default=0,
        ge=0,
        description="Total number of text chunks examined during retrieval.",
    )
    total_chunks_returned: int = Field(
        default=0,
        ge=0,
        description="Total number of text chunks returned in the final context.",
    )
    backend: str = Field(
        description="Identifier of the backend that produced these results.",
    )
    backend_version: str | None = Field(
        default=None,
        description="Optional backend software version string.",
    )


class RetrievalMetrics(BaseModel):
    """Retrieval performance and coverage metrics."""

    input_tokens: int = Field(
        default=0,
        ge=0,
        description="Tokens consumed by the query/context.",
    )
    entities_returned: int = Field(
        default=0,
        ge=0,
        description="Entities returned in the context.",
    )
    relationships_returned: int = Field(
        default=0,
        ge=0,
        description="Relationships returned in the context.",
    )
    paths_found: int = Field(
        default=0,
        ge=0,
        description="Paths discovered.",
    )
    communities_matched: int = Field(
        default=0,
        ge=0,
        description="Communities matched.",
    )
    graph_hops_traversed: int = Field(
        default=0,
        ge=0,
        description="Total graph hops traversed during retrieval.",
    )
    latency_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Retrieval latency in milliseconds.",
    )


class SubgraphContext(BaseModel):
    """Contract 2: The standard response for all retrieval operations.

    Encapsulates the retrieved subgraph, its provenance, and retrieval
    metrics in a uniform structure regardless of the backend.
    """

    protocol: str = Field(
        default="graphrag/1.0",
        description="Protocol version identifier.",
    )
    operation: str = Field(
        description="Echo of the retrieval operation that produced this context.",
    )
    query: dict[str, Any] = Field(
        description="Echo of the original retrieval request.",
    )
    results: dict[str, Any] = Field(
        default_factory=lambda: {
            "entities": [],
            "relationships": [],
            "paths": [],
            "communities": [],
            "text_chunks": [],
        },
        description="Retrieved subgraph: entities/relationships/paths/communities/text_chunks.",
    )
    provenance: Provenance = Field(
        description="Contract 5 citation and audit trail.",
    )
    metrics: RetrievalMetrics = Field(
        description="Retrieval performance and coverage metrics.",
    )


class EntityType(BaseModel):
    """A vertex type with its attributes and instance count."""

    type: str = Field(description="Vertex type / label name.")
    count: int = Field(ge=0, description="Number of instances.")
    primary_key: str = Field(description="Attribute that serves as the primary key.")
    attributes: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Attribute definitions (name/type/nullable).",
    )
    sample: dict[str, Any] | None = Field(
        default=None,
        description="Optional example instance for LLM context.",
    )


class RelationshipType(BaseModel):
    """An edge type with its source/target vertex types."""

    type: str = Field(description="Edge type / label name.")
    source: str = Field(description="Source vertex type.")
    target: str = Field(description="Target vertex type.")
    count: int = Field(ge=0, description="Number of instances.")
    attributes: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Attribute definitions.",
    )


class GraphStatistics(BaseModel):
    """Graph-level statistics."""

    total_vertices: int = Field(ge=0, description="Total number of vertices.")
    total_edges: int = Field(ge=0, description="Total number of edges.")
    avg_degree: float = Field(ge=0.0, description="Average vertex degree.")
    connected_components: int = Field(ge=0, description="Number of connected components.")


class GraphSchema(BaseModel):
    """Contract 3: The schema-introspection response.

    Describes all vertex/edge types, attributes, and graph statistics in a
    backend-agnostic form so agents and LLMs can reason about the graph
    without learning a backend-specific query language.
    """

    protocol: str = Field(
        default="graphrag/1.0",
        description="Protocol version identifier.",
    )
    graph_id: str = Field(description="Identifier of the graph this schema describes.")
    vertex_types: list[EntityType] = Field(
        default_factory=list,
        description="Vertex types with attributes and counts.",
    )
    edge_types: list[RelationshipType] = Field(
        default_factory=list,
        description="Edge types with source/target and counts.",
    )
    statistics: GraphStatistics = Field(
        description="Graph-level statistics.",
    )


class RetrievalResult(BaseModel):
    """A retrieval operation result: the subgraph context plus an optional
    pre-formatted text representation."""

    context: SubgraphContext = Field(
        description="The retrieved subgraph context.",
    )
    formatted: str | None = Field(
        default=None,
        description="Optional pre-formatted text representation.",
    )


class PromptFormat(str, Enum):
    """Supported text serialization formats for Contract 8."""

    MARKDOWN = "markdown"
    STRUCTURED = "structured"
    NONE = "none"


class PromptFormatConfig(BaseModel):
    """Contract 8: Configuration for formatting SubgraphContext for LLM consumption.

    Enables token budgeting, citation styles, and section filtering.
    """

    format: PromptFormat = Field(
        default=PromptFormat.MARKDOWN,
        description="Target format: markdown, structured, or none.",
    )
    max_tokens: int = Field(
        default=4096,
        ge=64,
        le=32768,
        description="Maximum token budget for the formatted text.",
    )
    include_citations: bool = Field(
        default=True,
        description="Whether to include inline citations and provenance footers.",
    )
    include_metrics: bool = Field(
        default=True,
        description="Whether to append execution metrics to the output.",
    )
    include_provenance: bool = Field(
        default=True,
        description="Whether to include source documents and traversal trajectories.",
    )