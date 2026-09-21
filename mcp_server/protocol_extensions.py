"""Protocol models for Contracts 4, 6, 7, 9, 10 (see SPEC.md §10)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Contract 4 — Construction (IngestionConfig / IngestionReport / Triple)
# ---------------------------------------------------------------------------

class ExtractionStrategy(str, Enum):
    """How entities/concepts are extracted from document text."""

    FREQUENCY = "frequency"          # stopword-filtered top-K tokens (real, deterministic)
    LLM = "llm"                      # Gemini-based extraction (real API call)


class ResolveStrategy(str, Enum):
    """How extracted entities are matched against the existing graph.

    - ``EXACT_ID``: existing vertices keep their id and their attributes are
      refreshed by the upsert (the ingestion default).
    - ``NEW_ONLY``: insert-only — a document/entity that already exists is left
      untouched (its attributes are never overwritten).
    """

    EXACT_ID = "exact_id"            # normalized id match (author name, concept token)
    NEW_ONLY = "new_only"            # insert-only: existing vertices are never written


class Triple(BaseModel):
    """A (subject, predicate, object) assertion extracted from a document."""

    subject_id: str = Field(description="Subject vertex id (e.g. 'paper:2609.05415').")
    subject_type: str = Field(default="Paper")
    predicate: str = Field(description="Edge type, e.g. MENTIONS, AUTHORED_BY, CITES.")
    object_id: str = Field(description="Object vertex id (e.g. 'concept:attention').")
    object_type: str = Field(default="Concept")
    properties: dict[str, Any] = Field(default_factory=dict)
    source_doc: str | None = Field(default=None, description="Originating document id.")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class IngestionConfig(BaseModel):
    """Contract 4: configuration for document -> knowledge-graph ingestion."""

    protocol: str = Field(default="graphrag/1.0")
    graph_id: str = Field(default="default", description="Target graph identifier (TigerGraph graph name).")
    document_type: str = Field(
        default="paper",
        description="Document type driving the mapping (paper -> Paper/Author/Concept).",
    )
    extraction: ExtractionStrategy = Field(default=ExtractionStrategy.FREQUENCY)
    resolve: ResolveStrategy = Field(default=ResolveStrategy.EXACT_ID)
    max_concepts_per_doc: int = Field(default=5, ge=1, le=50)
    embed_documents: bool = Field(
        default=False,
        description="Also upsert into the PaperEmb vector vertex when embeddings are available.",
    )
    dry_run: bool = Field(
        default=False,
        description="Extract and resolve but do not write; the report reflects what WOULD happen.",
    )


class IngestionReport(BaseModel):
    """Contract 4: outcome of an ingest/update/delete operation (real counters).

    Counter semantics (all measured against the backend, never estimated):

    - ``documents_written`` / ``documents_created``: the ids actually written
      this call, and the subset that did not exist before it.
    - ``documents_ingested``: number of documents written (``len(documents_written)``);
      a document skipped by ``NEW_ONLY`` is counted in ``documents_skipped``
      instead, never as ingested.
    - ``entities_created``: vertices created by this call.
    - ``entities_resolved``: vertices matched to pre-existing ones (under
      ``EXACT_ID`` the match is overwritten; under ``NEW_ONLY`` it is skipped).
    """

    protocol: str = Field(default="graphrag/1.0")
    graph_id: str
    document_ids: list[str] = Field(default_factory=list, description="Ids requested by the caller.")
    documents_written: list[str] = Field(default_factory=list, description="Ids actually written.")
    documents_created: list[str] = Field(
        default_factory=list, description="Written ids that did not exist before this call."
    )
    documents_deleted: list[str] = Field(default_factory=list, description="Ids actually removed.")
    documents_ingested: int = 0
    documents_skipped: int = Field(
        default=0, description="Documents left untouched (NEW_ONLY and already present)."
    )
    triples_extracted: int = 0
    entities_created: int = 0
    entities_resolved: int = 0
    edges_created: int = 0
    vertices_before: dict[str, int] = Field(default_factory=dict)
    vertices_after: dict[str, int] = Field(default_factory=dict)
    dry_run: bool = False
    errors: list[str] = Field(default_factory=list)
    duration_ms: float = 0.0


# ---------------------------------------------------------------------------
# Contract 6 — Federation (FederationConfig)
# ---------------------------------------------------------------------------

class MergeStrategy(str, Enum):
    """How results from multiple backends/graphs are merged."""

    RECIPROCAL_RANK_FUSION = "rrf"
    WEIGHTED_SCORE = "weighted_score"


class BackendRef(BaseModel):
    """One participant in a federated query (same workspace, another graph)."""

    name: str = Field(description="Logical backend name, e.g. 'primary' or 'arxiv_graph'.")
    graph_id: str = Field(description="TigerGraph graph name to fan the query out to.")
    weight: float = Field(default=1.0, gt=0.0)


class FederationConfig(BaseModel):
    """Contract 6: multi-graph fan-out + merge policy (TigerGraph workspace)."""

    protocol: str = Field(default="graphrag/1.0")
    backends: list[BackendRef] = Field(default_factory=list)
    merge_strategy: MergeStrategy = Field(default=MergeStrategy.RECIPROCAL_RANK_FUSION)
    top_k: int = Field(default=10, ge=1, le=100)
    rrf_k: int = Field(default=60, ge=1, description="RRF constant (standard: 60).")


class EntityLink(BaseModel):
    """Contract 6: a cross-graph entity resolution candidate."""

    entity_name: str
    graph_id: str
    entity_id: str
    entity_type: str
    score: float


# ---------------------------------------------------------------------------
# Contract 7 — Streaming (StreamEvent)
# ---------------------------------------------------------------------------

class StreamEventType(str, Enum):
    """Graph mutation event types (SPEC §10.3)."""

    ENTITY_CREATED = "entity_created"
    ENTITY_UPDATED = "entity_updated"
    ENTITY_DELETED = "entity_deleted"
    EDGE_CREATED = "edge_created"
    EDGE_UPDATED = "edge_updated"
    COMMUNITY_RECOMPUTED = "community_recomputed"
    INGESTION_COMPLETED = "ingestion_completed"


class StreamEvent(BaseModel):
    """Contract 7: a graph mutation notification."""

    protocol: str = Field(default="graphrag/1.0")
    event_id: str = Field(description="Unique event id (monotonic counter + kind).")
    event_type: StreamEventType
    graph_id: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    entity_id: str | None = None
    entity_type: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Contract 9 — Evaluation (EvaluationReport)
# ---------------------------------------------------------------------------

class RetrievalEval(BaseModel):
    """Per-query retrieval quality against a reference answer."""

    query_id: str
    precision_at_k: float = Field(description="Fraction of top-K entities matching the reference.")
    recall_at_k: float = Field(ge=0.0, le=1.0, description="Fraction of reference terms covered by retrieved entities.")
    entities_retrieved: int
    graph_hops: int
    latency_ms: float


class AnswerEval(BaseModel):
    """Per-query answer quality: LLM-as-judge + optional BERTScore."""

    query_id: str
    judge_pass: bool | None = Field(description="LLM-as-judge verdict; None when no judge ran.")
    judge_reason: str | None = None
    judge_model: str | None = None
    bertscore_f1: float | None = Field(description="BERTScore F1 vs reference; None when unavailable.")
    faithfulness: str | None = Field(
        default=None,
        description="'grounded' | 'ungrounded' — whether the answer is backed by retrieved evidence.",
    )


class EvaluationReport(BaseModel):
    """Contract 9: aggregate evaluation over a query set (real measurements)."""

    protocol: str = Field(default="graphrag/1.0")
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    backend: str = "tigergraph"
    model: str | None = Field(description="Answer model used (if any).")
    num_queries: int = 0
    retrieval: list[RetrievalEval] = Field(default_factory=list)
    answers: list[AnswerEval] = Field(default_factory=list)
    avg_precision_at_k: float | None = None
    avg_recall_at_k: float | None = None
    judge_pass_rate: float | None = None
    avg_bertscore_f1: float | None = None
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Contract 10 — Authorization (AccessPolicy)
# ---------------------------------------------------------------------------

class PermissionDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


class AccessPolicy(BaseModel):
    """Contract 10: per-role, per-operation permission model.

    The anonymous role gets the default read-only allowlist; the admin role
    (granted via ``GRAPHRAG_ADMIN_TOKEN``) additionally allows write/admin
    operations. Every check returns an auditable :class:`PermissionResult`.
    """

    protocol: str = Field(default="graphrag/1.0")
    default_role: str = Field(default="anonymous")
    admin_role: str = Field(default="admin")
    allow_anonymous: list[str] = Field(
        default_factory=lambda: [
            "local_search", "global_search", "hybrid_search", "entity_lookup",
            "path_search", "neighborhood", "community_members", "search",
            "get_schema", "get_entity_types", "get_relationship_types",
            "get_sample_entities", "get_statistics", "trace_citation",
            "get_traversal_trajectory", "get_source_documents",
            "audit_provenance_completeness", "format_context",
            "subscribe", "evaluate", "federated_search",
            "cross_graph_entity_link", "health",
        ],
    )
    allow_admin: list[str] = Field(
        default_factory=lambda: [
            "ingest", "update_document", "delete_document", "admin_status",
        ],
    )


class PermissionResult(BaseModel):
    """Contract 10: outcome of a permission check (auditable)."""

    allowed: bool
    decision: PermissionDecision
    role: str
    operation: str
    graph_id: str | None = None
    reason: str
