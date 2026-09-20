"""GraphRAG Protocol — real MCP server (mcp SDK v2, stdio transport).

Exposes the protocol contracts (retrieval, schema discovery, provenance,
formatting) as MCP tools so ANY MCP client — Claude Desktop, Claude Code,
LangGraph, CrewAI — can query ANY GraphRAG backend uniformly.

Run:
    python -m mcp_server.mcp_server          # or the `graphrag-mcp` script

Design notes:
- One shared adapter (TigerGraph when configured + healthy, else demo).
- One shared `RetrievalContract`/`SchemaDiscoveryContract`/`ProvenanceContract`
  layer over that adapter; every tool goes through the contracts, so parameter
  validation and response normalization are enforced uniformly.
- Tools return compact JSON: the structured contract of the protocol, plus
  ``formatted`` text from Contract 8 formatters when asked.
- The adapter is lazy: creating the server never opens a connection. First
  tool call instantiates it; TigerGraph failures at first use degrade to the
  demo adapter (logged to stderr; stdout stays MCP-framing-clean).
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

from mcp_server.adapters import DemoGraphRAGAdapter, TigerGraphAdapter
from mcp_server.contracts.authorization import AuthorizationContract
from mcp_server.contracts.construction import ConstructionContract
from mcp_server.contracts.evaluation import EvaluationContract
from mcp_server.contracts.federation import FederationContract
from mcp_server.contracts.provenance import ProvenanceContract
from mcp_server.contracts.retrieval import RetrievalContract
from mcp_server.contracts.schema_discovery import SchemaDiscoveryContract
from mcp_server.contracts.streaming import STREAM_BUS
from mcp_server.formatters import MarkdownFormatter, StructuredFormatter
from mcp_server.protocol import SubgraphContext
from mcp_server.protocol_extensions import (
    BackendRef,
    FederationConfig,
    IngestionConfig,
    MergeStrategy,
    StreamEventType,
)

_DEFAULT_MAX_TOKENS = 4096
_DEFAULT_EXTRACTION_STRATEGY = os.environ.get('GRAPHRAG_EXTRACTION', 'frequency')


def _adapter() -> Any:
    """Pick the best available adapter without crashing at import time.

    TigerGraph wins when credentials are present and the workspace answers a
    health check; otherwise the in-memory demo adapter is used. Mirrors the
    HTTP server's selection logic so both entrypoints behave identically.
    """
    try:
        adapter = TigerGraphAdapter()
        if adapter.health_check().get("status") == "ok":
            return adapter
    except Exception as exc:  # noqa: BLE001 - degrade, never crash the server
        print(f"[mcp_server] TigerGraph adapter unavailable ({exc}); using demo adapter", file=sys.stderr)
        return DemoGraphRAGAdapter()
    print("[mcp_server] TigerGraph unhealthy; using demo adapter", file=sys.stderr)
    return DemoGraphRAGAdapter()


class GraphRAGState:
    """Lazily-initialized shared contracts over one shared adapter."""

    def __init__(self) -> None:
        self._adapter: Any | None = None
        self._retrieval: RetrievalContract | None = None
        self._schema: SchemaDiscoveryContract | None = None
        self._provenance: ProvenanceContract | None = None
        self._construction: ConstructionContract | None = None
        self._federation: FederationContract | None = None
        self._evaluation: EvaluationContract | None = None
        self._authorization: AuthorizationContract | None = None
        self._markdown = MarkdownFormatter()
        self._structured = StructuredFormatter()

    @property
    def adapter(self) -> Any:
        if self._adapter is None:
            self._adapter = _adapter()
        return self._adapter

    @property
    def retrieval(self) -> RetrievalContract:
        if self._retrieval is None:
            self._retrieval = RetrievalContract(self.adapter)
        return self._retrieval

    @property
    def schema(self) -> SchemaDiscoveryContract:
        if self._schema is None:
            self._schema = SchemaDiscoveryContract(self.adapter)
        return self._schema

    @property
    def provenance(self) -> ProvenanceContract:
        if self._provenance is None:
            self._provenance = ProvenanceContract(self.adapter)
        return self._provenance

    @property
    def construction(self) -> ConstructionContract:
        if self._construction is None:
            self._construction = ConstructionContract(self.adapter)
        return self._construction

    @property
    def federation(self) -> FederationContract:
        if self._federation is None:
            self._federation = FederationContract(self.adapter)
        return self._federation

    @property
    def evaluation(self) -> EvaluationContract:
        if self._evaluation is None:
            self._evaluation = EvaluationContract(self.adapter)
        return self._evaluation

    @property
    def authorization(self) -> AuthorizationContract:
        if self._authorization is None:
            self._authorization = AuthorizationContract()
        return self._authorization


STATE = GraphRAGState()


def _context_payload(ctx: SubgraphContext, *, format_text: str, max_tokens: int) -> dict[str, Any]:
    """Structured protocol envelope + optional formatted text (Contract 8)."""
    payload: dict[str, Any] = {
        "protocol": ctx.protocol,
        "operation": ctx.operation,
        "query": ctx.query,
        "results": ctx.results,
        "provenance": ctx.provenance.model_dump(),
        "metrics": ctx.metrics.model_dump(),
    }
    fmt = (format_text or "none").lower()
    if fmt in ("markdown", "md"):
        payload["formatted"] = STATE._markdown.format_context(ctx, max_tokens=max_tokens)
    elif fmt in ("structured", "json"):
        payload["formatted"] = STATE._structured.format_context(ctx, max_tokens=max_tokens)
    return payload


def _json(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=False)


def build_server() -> MCPServer:
    """Construct the MCP server with all 42 tools registered."""
    mcp = MCPServer(
        name="grip",
        version="0.2.0",
        instructions=(
            "GraphRAG Interoperability Protocol (GRIP): uniform access to any GraphRAG backend. "
            "Use graphrag_search for natural-language queries (auto-routes to "
            "local/global/hybrid/entity), graphrag_schema to plan against the "
            "backend's structure, and graphrag_provenance for citation audits."
        ),
    )

    # ------------------------------------------------------------------
    # Retrieval tools (7)
    # ------------------------------------------------------------------

    @mcp.tool(
        name="graphrag_search",
        title="GraphRAG unified search",
        description=(
            "Auto-routing retrieval over any GraphRAG backend. Mode 'auto' "
            "classifies the query (global overview / entity / hybrid). "
            "Returns the protocol SubgraphContext envelope."
        ),
    )
    def graphrag_search(
        query: str,
        mode: str = "auto",
        top_k: int = 10,
        depth: int = 2,
        format_text: str = "none",
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> str:
        result = STATE.retrieval.search(query=query, mode=mode, top_k=top_k, depth=depth)
        return _json(_context_payload(result.context, format_text=format_text, max_tokens=max_tokens))

    @mcp.tool(
        name="graphrag_local_search",
        title="Local search",
        description="Keyword/entity-anchored local retrieval around matched entities.",
    )
    def graphrag_local_search(
        query: str,
        entity_hints: list[str] | None = None,
        depth: int = 2,
        top_k: int = 10,
        format_text: str = "none",
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> str:
        ctx = STATE.retrieval.local_search(query=query, entity_hints=entity_hints, depth=depth, top_k=top_k)
        return _json(_context_payload(ctx, format_text=format_text, max_tokens=max_tokens))

    @mcp.tool(
        name="graphrag_global_search",
        title="Global search",
        description="Corpus-level summarization from community summaries at a given level.",
    )
    def graphrag_global_search(
        query: str,
        community_level: int = 2,
        format_text: str = "none",
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> str:
        ctx = STATE.retrieval.global_search(query=query, community_level=community_level)
        return _json(_context_payload(ctx, format_text=format_text, max_tokens=max_tokens))

    @mcp.tool(
        name="graphrag_hybrid_search",
        title="Hybrid search",
        description="Semantic + keyword + graph-structure fused retrieval.",
    )
    def graphrag_hybrid_search(
        query: str,
        top_k: int = 10,
        depth: int = 2,
        format_text: str = "none",
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> str:
        ctx = STATE.retrieval.hybrid_search(query=query, top_k=top_k, depth=depth)
        return _json(_context_payload(ctx, format_text=format_text, max_tokens=max_tokens))

    @mcp.tool(
        name="graphrag_entity",
        title="Entity lookup",
        description="Look up an entity by id and/or name; optionally expand its neighborhood.",
    )
    def graphrag_entity(
        entity_id: str | None = None,
        entity_name: str | None = None,
        entity_type: str | None = None,
        depth: int = 1,
        format_text: str = "none",
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> str:
        ctx = STATE.retrieval.entity_lookup(
            entity_id=entity_id, entity_name=entity_name, entity_type=entity_type, depth=depth
        )
        return _json(_context_payload(ctx, format_text=format_text, max_tokens=max_tokens))

    @mcp.tool(
        name="graphrag_path",
        title="Path search",
        description="Find paths (up to max_hops) between two entities in the graph.",
    )
    def graphrag_path(
        source: str,
        target: str,
        max_hops: int = 4,
        format_text: str = "none",
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> str:
        ctx = STATE.retrieval.path_search(source=source, target=target, max_hops=max_hops)
        return _json(_context_payload(ctx, format_text=format_text, max_tokens=max_tokens))

    @mcp.tool(
        name="graphrag_neighborhood",
        title="Neighborhood expansion",
        description="Expand the graph neighborhood around an entity to a given depth.",
    )
    def graphrag_neighborhood(
        entity_id: str,
        depth: int = 2,
        edge_types: list[str] | None = None,
        format_text: str = "none",
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> str:
        ctx = STATE.retrieval.neighborhood(entity_id=entity_id, depth=depth, edge_types=edge_types)
        return _json(_context_payload(ctx, format_text=format_text, max_tokens=max_tokens))

    @mcp.tool(
        name="graphrag_community",
        title="Community members",
        description="List member entities of a community, optionally with its summary.",
    )
    def graphrag_community(
        community_id: str,
        include_summary: bool = True,
        format_text: str = "none",
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> str:
        ctx = STATE.retrieval.community_members(community_id=community_id, include_summary=include_summary)
        return _json(_context_payload(ctx, format_text=format_text, max_tokens=max_tokens))

    @mcp.tool(
        name="graphrag_schema",
        title="Schema discovery",
        description="Introspect the backend's vertex/edge types, statistics, and sample entities.",
    )
    def graphrag_schema(graph_id: str | None = None) -> str:
        return _json(STATE.schema.get_schema(graph_id=graph_id).model_dump())

    @mcp.tool(
        name="graphrag_entity_types",
        title="Entity types",
        description="List the backend's vertex types with counts and sample attributes.",
    )
    def graphrag_entity_types(graph_id: str | None = None) -> str:
        return _json([t.model_dump() for t in STATE.schema.get_entity_types(graph_id=graph_id)])

    @mcp.tool(
        name="graphrag_relationship_types",
        title="Relationship types",
        description="List the backend's edge types with endpoints, counts, and attributes.",
    )
    def graphrag_relationship_types(graph_id: str | None = None) -> str:
        return _json([t.model_dump() for t in STATE.schema.get_relationship_types(graph_id=graph_id)])

    @mcp.tool(
        name="graphrag_sample",
        title="Sample entities",
        description="Fetch sample entities of a vertex type (useful for grounding before querying).",
    )
    def graphrag_sample(
        entity_type: str,
        limit: int = 5,
        format_text: str = "none",
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> str:
        ctx = STATE.schema.get_sample_entities(entity_type=entity_type, limit=limit)
        return _json(_context_payload(ctx, format_text=format_text, max_tokens=max_tokens))

    # ------------------------------------------------------------------
    # Provenance + formatting tools
    # ------------------------------------------------------------------

    @mcp.tool(
        name="graphrag_provenance",
        title="Provenance trace",
        description="Trace the full citation/audit chain for an entity or fact id.",
    )
    def graphrag_provenance(fact_id: str) -> str:
        return _json(STATE.provenance.trace_citation(fact_id).model_dump())

    @mcp.tool(
        name="graphrag_trajectory",
        title="Traversal trajectory",
        description="Replay the traversal trajectory (steps, actions, edges) behind a result.",
    )
    def graphrag_trajectory(query_id: str) -> str:
        return _json(STATE.provenance.get_traversal_trajectory(query_id=query_id).model_dump())

    @mcp.tool(
        name="graphrag_sources",
        title="Source documents",
        description="List the source documents an entity was extracted from.",
    )
    def graphrag_sources(entity_id: str) -> str:
        return _json(STATE.provenance.get_source_documents(entity_id=entity_id))

    @mcp.tool(
        name="graphrag_audit",
        title="Provenance audit",
        description="Score trajectory completeness: cited vs examined entities, with a recommendation.",
    )
    def graphrag_audit(query_id: str) -> str:
        return _json(STATE.provenance.audit_provenance_completeness(query_id=query_id).model_dump())

    @mcp.tool(
        name="graphrag_format",
        title="Format context",
        description=(
            "Re-format a previously returned SubgraphContext (JSON envelope) "
            "into token-bounded Markdown or structured text for an LLM prompt."
        ),
    )
    def graphrag_format(
        context: dict[str, Any],
        format_text: str = "markdown",
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> str:
        try:
            ctx = SubgraphContext(**context)
        except ValueError as exc:
            return _json({"error": f"Invalid context: {exc}"})
        if format_text.lower() in ("structured", "json"):
            return STATE._structured.format_context(ctx, max_tokens=max_tokens)
        return STATE._markdown.format_context(ctx, max_tokens=max_tokens)

    # ------------------------------------------------------------------
    # Admin tools (3)
    # ------------------------------------------------------------------

    @mcp.tool(
        name="graphrag_status",
        title="Backend status",
        description="Health, identity, and graph statistics of the active backend.",
    )
    def graphrag_status() -> str:
        health = STATE.adapter.health_check()
        try:
            stats = STATE.schema.get_statistics().model_dump()
        except Exception as exc:  # noqa: BLE001 - stats are best-effort
            stats = {"error": str(exc)}
        return _json({"backend": health, "statistics": stats})

    @mcp.tool(
        name="graphrag_config",
        title="Get configuration",
        description="Show the effective (non-secret) configuration of this server.",
    )
    def graphrag_config() -> str:
        return _json(
            {
                "protocol": "graphrag/1.0",
                "backend_requested": "tigergraph" if os.environ.get("TIGERGRAPH_HOST") else "demo",
                "llm_model": os.environ.get("LLM_MODEL", "gemini-3.8-flash"),
                "max_tokens_default": _DEFAULT_MAX_TOKENS,
            }
        )

    @mcp.tool(
        name="graphrag_list_backends",
        title="List backends",
        description="List backends this protocol build can talk to, and which is active.",
    )
    def graphrag_list_backends() -> str:
        active = STATE.adapter.health_check().get("backend", "unknown")
        return _json(
            {
                "available": ["tigergraph", "demo"],
                "active": active,
                "note": "Add more adapters by implementing BaseGraphRAGAdapter.",
            }
        )

    # ------------------------------------------------------------------
    # Construction (Contract 4) — admin gated
    # ------------------------------------------------------------------

    @mcp.tool(
        name="graphrag_ingest",
        title="Ingest documents",
        description=(
            "Real document -> knowledge-graph ingestion (Contract 4). Requires "
            "the admin token; counters in the report are measured from the backend."
        ),
    )
    def graphrag_ingest(
        documents: list[dict[str, Any]],
        dry_run: bool = False,
        extraction: str = "frequency",
        max_concepts_per_doc: int = 5,
        admin_token: str | None = None,
    ) -> str:
        decision = STATE.authorization.check_permission("ingest", token=admin_token)
        if not decision.allowed:
            return _json({"error": "permission denied", **decision.model_dump()})
        config = IngestionConfig(
            graph_id=getattr(STATE.adapter, "_graphname", "default"),
            extraction=extraction,
            max_concepts_per_doc=max_concepts_per_doc,
            dry_run=dry_run,
        )
        try:
            report = STATE.construction.ingest(documents, config)
        except RuntimeError as exc:
            return _json({"error": str(exc)})
        return _json(report.model_dump())

    @mcp.tool(
        name="graphrag_delete_document",
        title="Delete document",
        description="Delete a Paper vertex and its edges from the graph (Contract 4, admin only).",
    )
    def graphrag_delete_document(document_id: str, admin_token: str | None = None) -> str:
        decision = STATE.authorization.check_permission("delete_document", token=admin_token)
        if not decision.allowed:
            return _json({"error": "permission denied", **decision.model_dump()})
        return _json(STATE.construction.delete_document(document_id).model_dump())

    # ------------------------------------------------------------------
    # Federation (Contract 6)
    # ------------------------------------------------------------------

    @mcp.tool(
        name="graphrag_federated_search",
        title="Federated search",
        description=(
            "Fan a query out to multiple graphs in the workspace and merge the "
            "results with reciprocal rank fusion or weighted score (Contract 6)."
        ),
    )
    def graphrag_federated_search(
        query: str,
        mode: str = "auto",
        top_k: int = 10,
        merge_strategy: str = "rrf",
        extra_graphs: list[str] | None = None,
        format_text: str = "none",
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> str:
        graph = getattr(STATE.adapter, "_graphname", None)
        backends = [BackendRef(name="primary", graph_id=graph)] if graph else []
        for name in extra_graphs or []:
            backends.append(BackendRef(name=name, graph_id=name))
        config = FederationConfig(
            backends=backends, merge_strategy=MergeStrategy(merge_strategy), top_k=top_k
        )
        ctx = STATE.federation.federated_search(query, config=config, mode=mode)
        return _json(_context_payload(ctx, format_text=format_text, max_tokens=max_tokens))

    @mcp.tool(
        name="graphrag_entity_link",
        title="Cross-graph entity link",
        description="Find the same entity across federated graphs (Contract 6).",
    )
    def graphrag_entity_link(entity_name: str, entity_type: str | None = None) -> str:
        graph = getattr(STATE.adapter, "_graphname", None)
        config = FederationConfig(backends=[BackendRef(name="primary", graph_id=graph)] if graph else [])
        links = STATE.federation.cross_graph_entity_link(entity_name, config=config, entity_type=entity_type)
        return _json([link.model_dump() for link in links])

    # ------------------------------------------------------------------
    # Streaming (Contract 7)
    # ------------------------------------------------------------------

    @mcp.tool(
        name="graphrag_events",
        title="Recent graph events",
        description=(
            "Recent graph-mutation events from the streaming bus (Contract 7). "
            "Ingestion publishes real events here; the HTTP server exposes a live "
            "SSE feed at /stream/events."
        ),
    )
    def graphrag_events(limit: int = 20, event_type: str | None = None) -> str:
        events = STREAM_BUS.recent(max(1, min(limit, 200)))
        if event_type:
            events = [e for e in events if e.event_type.value == event_type]
        return _json(
            {
                "subscribers": STREAM_BUS.subscriber_count,
                "events": [e.model_dump(mode="json") for e in events],
                "known_types": [t.value for t in StreamEventType],
            }
        )

    # ------------------------------------------------------------------
    # Evaluation (Contract 9) + Authorization (Contract 10)
    # ------------------------------------------------------------------

    @mcp.tool(
        name="graphrag_evaluate",
        title="Evaluate pipelines",
        description=(
            "Run real retrieval/answer evaluation over the benchmark query set "
            "(Contract 9): precision@k, recall@k, LLM-as-judge and grounding."
        ),
    )
    def graphrag_evaluate(limit: int = 5, mode: str = "auto", pipeline: str = "graphrag", references_path: str | None = None) -> str:
        from mcp_server.pipelines import load_query_set

        references: dict[str, str] = {}
        if references_path:
            try:
                with open(references_path) as handle:
                    references = json.load(handle)
            except FileNotFoundError:
                pass
            except Exception as exc:  # noqa: BLE001 - references are optional
                print(f"[mcp_server] references unavailable ({type(exc).__name__})", file=sys.stderr)
        try:
            query_set = [
                {**item, "reference": references.get(item["id"], "")}
                for item in load_query_set(limit=max(1, min(limit, 25)))
            ]
        except (OSError, ValueError) as exc:
            # Never invent queries: report the real problem instead.
            return _json({"error": f"benchmark query set unavailable: {exc}"})
        report = STATE.evaluation.evaluate_report(query_set, mode=mode, pipeline=pipeline)
        return _json(report.model_dump())

    @mcp.tool(
        name="graphrag_authorize",
        title="Check permission",
        description="Check whether an operation is permitted for a role/token (Contract 10).",
    )
    def graphrag_authorize(operation: str, admin_token: str | None = None) -> str:
        result = STATE.authorization.check_permission(operation, token=admin_token)
        return _json(
            {
                **result.model_dump(),
                "allowed_operations": STATE.authorization.get_allowed_operations(token=admin_token),
            }
        )

    # ------------------------------------------------------------------
    # Contract 11 — Semantic Similarity
    # ------------------------------------------------------------------

    @mcp.tool(
        name="graphrag_similarity",
        title="Semantic similarity",
        description="Compute cosine (vector) or Jaccard (lexical) similarity between two text blobs or entity IDs.",
    )
    def graphrag_similarity(text_a: str, text_b: str) -> str:
        from mcp_server.contracts.similarity import SimilarityContract
        return _json(SimilarityContract(STATE.adapter).similarity(text_a, text_b))

    @mcp.tool(
        name="graphrag_entity_similarity",
        title="Entity semantic similarity",
        description="Compare two entities by id using their names and properties text.",
    )
    def graphrag_entity_similarity(entity_id_a: str, entity_id_b: str) -> str:
        from mcp_server.contracts.similarity import SimilarityContract
        return _json(SimilarityContract(STATE.adapter).entity_similarity(entity_id_a, entity_id_b))

    @mcp.tool(
        name="graphrag_batch_similarity",
        title="Batch similarity ranking",
        description="Rank a list of candidate texts by similarity to an anchor text, highest first.",
    )
    def graphrag_batch_similarity(anchor: str, candidates: list[str]) -> str:
        from mcp_server.contracts.similarity import SimilarityContract
        return _json(SimilarityContract(STATE.adapter).batch_similarity(anchor, candidates))

    # ------------------------------------------------------------------
    # Contract 12 — Temporal Query
    # ------------------------------------------------------------------

    @mcp.tool(
        name="graphrag_temporal_search",
        title="Temporal search",
        description="Retrieve entities filtered by a date range (start/end ISO-8601). Filters on published, created_at, updated_at attributes.",
    )
    def graphrag_temporal_search(
        query: str,
        start: str | None = None,
        end: str | None = None,
        mode: str = "auto",
        top_k: int = 10,
        depth: int = 2,
        format_text: str = "none",
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> str:
        from mcp_server.contracts.temporal import TemporalContract
        ctx = TemporalContract(STATE.adapter).temporal_search(
            query=query, start=start, end=end, mode=mode, top_k=top_k, depth=depth
        )
        return _json(_context_payload(ctx, format_text=format_text, max_tokens=max_tokens))

    # ------------------------------------------------------------------
    # Contract 13 — Explanation
    # ------------------------------------------------------------------

    @mcp.tool(
        name="graphrag_explain",
        title="Explain retrieval",
        description="Generate natural-language explanations for why each entity was retrieved in a SubgraphContext.",
    )
    def graphrag_explain(
        context: dict[str, Any],
        max_entities: int = 10,
    ) -> str:
        from mcp_server.contracts.explanation import ExplanationContract
        try:
            ctx = SubgraphContext(**context)
        except Exception as exc:  # noqa: BLE001
            return _json({"error": f"Invalid context: {exc}"})
        return _json(ExplanationContract(STATE.adapter).explain(ctx, max_entities=max_entities))

    @mcp.tool(
        name="graphrag_explain_path",
        title="Explain path",
        description="Explain the reasoning behind each path found in a path_search SubgraphContext.",
    )
    def graphrag_explain_path(context: dict[str, Any]) -> str:
        from mcp_server.contracts.explanation import ExplanationContract
        try:
            ctx = SubgraphContext(**context)
        except Exception as exc:  # noqa: BLE001
            return _json({"error": f"Invalid context: {exc}"})
        return _json(ExplanationContract(STATE.adapter).explain_path(ctx))

    # ------------------------------------------------------------------
    # Contract 14 — Diff
    # ------------------------------------------------------------------

    @mcp.tool(
        name="graphrag_diff",
        title="Context diff",
        description="Compare two SubgraphContext envelopes and return the structural delta (entities added/removed, relationships changed).",
    )
    def graphrag_diff(
        context_a: dict[str, Any],
        context_b: dict[str, Any],
        label_a: str = "a",
        label_b: str = "b",
    ) -> str:
        from mcp_server.contracts.diff import DiffContract
        try:
            ctx_a = SubgraphContext(**context_a)
            ctx_b = SubgraphContext(**context_b)
        except Exception as exc:  # noqa: BLE001
            return _json({"error": f"Invalid context: {exc}"})
        return _json(DiffContract(STATE.adapter).diff_contexts(ctx_a, ctx_b, label_a=label_a, label_b=label_b))

    @mcp.tool(
        name="graphrag_diff_queries",
        title="Query diff",
        description="Run two different queries and return the diff of their result sets.",
    )
    def graphrag_diff_queries(
        query_a: str,
        query_b: str,
        mode: str = "auto",
        top_k: int = 10,
        depth: int = 2,
    ) -> str:
        from mcp_server.contracts.diff import DiffContract
        return _json(DiffContract(STATE.adapter).diff_queries(query_a=query_a, query_b=query_b, mode=mode, top_k=top_k, depth=depth))

    # ------------------------------------------------------------------
    # Contract 15 — Aggregate
    # ------------------------------------------------------------------

    @mcp.tool(
        name="graphrag_count",
        title="Count entities",
        description="Count entities of a given type, optionally with attribute filters. Uses schema stats (real backend counts).",
    )
    def graphrag_count(
        entity_type: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> str:
        from mcp_server.contracts.aggregate import AggregateContract
        return _json(AggregateContract(STATE.adapter).count(entity_type=entity_type, filters=filters))

    @mcp.tool(
        name="graphrag_group_by",
        title="Group entities by attribute",
        description="Group entities of a type by an attribute and return counts per group.",
    )
    def graphrag_group_by(
        entity_type: str,
        attribute: str,
        top_n: int = 20,
    ) -> str:
        from mcp_server.contracts.aggregate import AggregateContract
        return _json(AggregateContract(STATE.adapter).group_by(entity_type=entity_type, attribute=attribute, top_n=top_n))

    @mcp.tool(
        name="graphrag_top_n",
        title="Top-N entities by attribute",
        description="Return top-N entities of a type ranked by a numeric attribute value.",
    )
    def graphrag_top_n(
        entity_type: str,
        rank_by: str,
        n: int = 10,
        descending: bool = True,
    ) -> str:
        from mcp_server.contracts.aggregate import AggregateContract
        return _json(AggregateContract(STATE.adapter).top_n(entity_type=entity_type, rank_by=rank_by, n=n, descending=descending))

    @mcp.tool(
        name="graphrag_stats_summary",
        title="Graph statistics summary",
        description="Comprehensive statistics: vertex/edge counts by type, density, connected components.",
    )
    def graphrag_stats_summary() -> str:
        from mcp_server.contracts.aggregate import AggregateContract
        return _json(AggregateContract(STATE.adapter).stats_summary())

    @mcp.tool(
        name="graphrag_job_status",
        title="Ingestion job status",
        description="Check the status of a background ingestion job started with async_mode=True.",
    )
    def graphrag_job_status(job_id: str) -> str:
        # Job registry is stored in STATE; jobs are dict entries added by async ingest
        jobs = getattr(STATE, "_jobs", {})
        if job_id in jobs:
            return _json(jobs[job_id])
        return _json({"job_id": job_id, "status": "not_found", "error": "Unknown job id"})

    @mcp.tool(
        name="graphrag_register_backend",
        title="Register federated backend",
        description="Register a named backend adapter for federated queries (Contract 6). Returns the BackendRef.",
    )
    def graphrag_register_backend(
        name: str,
        graph_id: str,
        weight: float = 1.0,
        admin_token: str | None = None,
    ) -> str:
        decision = STATE.authorization.check_permission("ingest", token=admin_token)
        if not decision.allowed:
            return _json({"error": "permission denied", **decision.model_dump()})
        ref = STATE.federation.register_backend(name=name, weight=weight)
        return _json(ref.model_dump())

    @mcp.tool(
        name="graphrag_audit_log",
        title="Audit log",
        description="Return recent write operations (ingest/delete) from the streaming event bus, filtered to mutation events.",
    )
    def graphrag_audit_log(limit: int = 50) -> str:
        mutation_types = {"entity_created", "entity_updated", "entity_deleted", "edge_created", "ingestion_completed"}
        events = STREAM_BUS.recent(max(1, min(limit, 500)))
        audit = [e.model_dump(mode="json") for e in events if e.event_type.value in mutation_types]
        return _json({"total": len(audit), "events": audit})

    return mcp


def main() -> None:
    """Run the MCP server over stdio (the transport MCP clients expect)."""
    load_dotenv()
    server = build_server()
    server.run(transport="stdio")


if __name__ == "__main__":
    main()