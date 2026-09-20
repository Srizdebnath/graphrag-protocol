"""GraphRAG Protocol — real MCP server (mcp SDK v2, stdio & streamable-http transports).

Exposes all 18 protocol contracts (retrieval, schema discovery, provenance,
construction, federation, streaming, formatting, evaluation, authorization,
similarity, temporal, explanation, diff, aggregation, export, batch, watch)
as 47 MCP tools, browseable MCP resources, and prompt templates.

Any MCP client — Claude Desktop, Claude Code, LangGraph, Cursor, CrewAI —
can query any GraphRAG backend uniformly.

Run:
    python -m mcp_server.mcp_server                            # stdio transport
    python -m mcp_server.mcp_server --transport streamable-http # HTTP/SSE transport
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from typing import Any

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

from mcp_server.adapters import DemoGraphRAGAdapter, Neo4jGraphRAGAdapter, TigerGraphAdapter
from mcp_server.agent_harness import AgenticInvestigationHarness
from mcp_server.cache import QueryCache
from mcp_server.contracts.aggregate import AggregateContract
from mcp_server.contracts.authorization import AuthorizationContract
from mcp_server.contracts.batch import BatchContract
from mcp_server.contracts.conflicts import ConflictResolutionContract
from mcp_server.contracts.construction import ConstructionContract
from mcp_server.contracts.diff import DiffContract
from mcp_server.contracts.evaluation import EvaluationContract
from mcp_server.contracts.explanation import ExplanationContract
from mcp_server.contracts.export import ExportContract
from mcp_server.contracts.federation import FederationContract
from mcp_server.contracts.provenance import ProvenanceContract
from mcp_server.contracts.retrieval import RetrievalContract
from mcp_server.contracts.schema_discovery import SchemaDiscoveryContract
from mcp_server.contracts.similarity import SimilarityContract
from mcp_server.contracts.streaming import STREAM_BUS
from mcp_server.contracts.temporal import TemporalContract
from mcp_server.contracts.triage import QueryTriageContract
from mcp_server.contracts.watch import WatchContract
from mcp_server.formatters import MarkdownFormatter, StructuredFormatter
from mcp_server.protocol import SubgraphContext
from mcp_server.protocol_extensions import (
    BackendRef,
    FederationConfig,
    IngestionConfig,
    MergeStrategy,
)
from mcp_server.rate_limiter import RateLimiter
from mcp_server.storage import PersistentStorage

_DEFAULT_MAX_TOKENS = 4096
_DEFAULT_EXTRACTION_STRATEGY = os.environ.get("GRAPHRAG_EXTRACTION", "frequency")

# In-memory cursor storage for graphrag_next_page
_CURSORS: dict[str, dict[str, Any]] = {}


def _adapter() -> Any:
    """Pick the best available real adapter without crashing at import time.

    Checks Neo4j first if configured and healthy; then TigerGraph;
    otherwise falls back to DemoGraphRAGAdapter.
    """
    neo4j_uri = os.environ.get("NEO4J_URI")
    if neo4j_uri:
        try:
            adapter = Neo4jGraphRAGAdapter()
            if adapter.health_check().get("status") == "ok":
                return adapter
        except Exception as exc:  # noqa: BLE001
            print(f"[mcp_server] Neo4j unavailable ({exc}); trying TigerGraph", file=sys.stderr)

    try:
        adapter = TigerGraphAdapter()
        if adapter.health_check().get("status") == "ok":
            return adapter
    except Exception as exc:  # noqa: BLE001
        print(f"[mcp_server] TigerGraph unavailable ({exc}); using demo adapter", file=sys.stderr)
        return DemoGraphRAGAdapter()

    return DemoGraphRAGAdapter()


class GraphRAGState:
    """Lazily-initialized shared contracts over the active adapter."""

    def __init__(self) -> None:
        self._adapter: Any | None = None
        self._retrieval: RetrievalContract | None = None
        self._schema: SchemaDiscoveryContract | None = None
        self._provenance: ProvenanceContract | None = None
        self._construction: ConstructionContract | None = None
        self._federation: FederationContract | None = None
        self._evaluation: EvaluationContract | None = None
        self._authorization: AuthorizationContract | None = None
        self._similarity: SimilarityContract | None = None
        self._temporal: TemporalContract | None = None
        self._explanation: ExplanationContract | None = None
        self._diff: DiffContract | None = None
        self._aggregate: AggregateContract | None = None
        self._export: ExportContract | None = None
        self._watch: WatchContract | None = None
        self._conflicts: ConflictResolutionContract | None = None
        self._triage: QueryTriageContract | None = None
        self._markdown = MarkdownFormatter()
        self._structured = StructuredFormatter()
        self._storage = PersistentStorage.get_instance()
        self._cache = QueryCache.get_instance()
        self._limiter = RateLimiter.get_instance()

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

    @property
    def similarity(self) -> SimilarityContract:
        if self._similarity is None:
            self._similarity = SimilarityContract(self.adapter)
        return self._similarity

    @property
    def temporal(self) -> TemporalContract:
        if self._temporal is None:
            self._temporal = TemporalContract(self.adapter)
        return self._temporal

    @property
    def explanation(self) -> ExplanationContract:
        if self._explanation is None:
            self._explanation = ExplanationContract(self.adapter)
        return self._explanation

    @property
    def diff(self) -> DiffContract:
        if self._diff is None:
            self._diff = DiffContract(self.adapter)
        return self._diff

    @property
    def aggregate(self) -> AggregateContract:
        if self._aggregate is None:
            self._aggregate = AggregateContract(self.adapter)
        return self._aggregate

    @property
    def export(self) -> ExportContract:
        if self._export is None:
            self._export = ExportContract(self.adapter)
        return self._export

    @property
    def watch(self) -> WatchContract:
        if self._watch is None:
            self._watch = WatchContract(self._storage)
        return self._watch

    @property
    def conflicts(self) -> ConflictResolutionContract:
        if self._conflicts is None:
            self._conflicts = ConflictResolutionContract(self.adapter)
        return self._conflicts

    @property
    def triage(self) -> QueryTriageContract:
        if self._triage is None:
            self._triage = QueryTriageContract(self.adapter)
        return self._triage


STATE = GraphRAGState()


def _format(ctx: SubgraphContext, format_text: str, max_tokens: int) -> str | None:
    mode = (format_text or "none").lower()
    if mode == "markdown":
        return STATE._markdown.format_context(ctx, max_tokens=max_tokens)
    if mode in ("structured", "json"):
        return STATE._structured.format_context(ctx, max_tokens=max_tokens)
    return None


def _context_payload(
    ctx: SubgraphContext,
    format_text: str = "none",
    max_tokens: int = _DEFAULT_MAX_TOKENS,
) -> dict[str, Any]:
    dump = ctx.model_dump(mode="json")
    formatted = _format(ctx, format_text=format_text, max_tokens=max_tokens)
    if formatted is not None:
        dump["formatted"] = formatted
    return dump


def _json(obj: Any) -> str:
    return json.dumps(obj, indent=2, default=str)


def build_server() -> MCPServer:
    """Construct the MCP server with all 50 tools, resources, and prompts registered."""
    mcp = MCPServer(
        name="grip",
        version="0.3.0",
        instructions=(
            "GraphRAG Interoperability Protocol (GRIP): uniform access to any GraphRAG backend. "
            "Use graphrag_search for natural-language queries, graphrag_agent_investigate for "
            "autonomous multi-step reasoning, graphrag_schema to plan against the structure, "
            "graphrag_resolve_conflicts for contradictory evidence, and graphrag_batch for parallel execution."
        ),
    )

    # ------------------------------------------------------------------
    # MCP Resources
    # ------------------------------------------------------------------

    @mcp.resource("graphrag://schema")
    def resource_schema() -> str:
        """Browseable full schema of the active knowledge graph."""
        return _json(STATE.schema.get_schema().model_dump(mode="json"))

    @mcp.resource("graphrag://entity/{entity_id}")
    def resource_entity(entity_id: str) -> str:
        """Browseable single entity context by ID."""
        ctx = STATE.retrieval.entity_lookup(entity_id=entity_id, depth=1)
        return _json(_context_payload(ctx))

    @mcp.resource("graphrag://community/{community_id}")
    def resource_community(community_id: str) -> str:
        """Browseable community members and summary."""
        ctx = STATE.retrieval.community_members(community_id=community_id)
        return _json(_context_payload(ctx))

    # ------------------------------------------------------------------
    # MCP Prompts
    # ------------------------------------------------------------------

    @mcp.prompt("entity_analysis")
    def prompt_entity_analysis(entity_name: str) -> str:
        """Prompt template for deep analysis of a graph entity."""
        return (
            f"Please conduct a comprehensive analysis of the entity '{entity_name}'.\n"
            f"1. Query the knowledge graph using graphrag_entity or graphrag_neighborhood.\n"
            f"2. Inspect citations and source documents using graphrag_provenance.\n"
            f"3. Explain why related entities were linked using graphrag_explain.\n"
            f"4. Synthesize your findings citing supporting chunks."
        )

    @mcp.prompt("path_reasoning")
    def prompt_path_reasoning(source: str, target: str) -> str:
        """Prompt template to analyze the relationship chain between two entities."""
        return (
            f"Trace and explain the connection between '{source}' and '{target}'.\n"
            f"1. Call graphrag_path to discover paths between the nodes.\n"
            f"2. Call graphrag_explain_path to get a narrative reasoning breakdown.\n"
            f"3. Provide a clear explanation of how they influence or relate to each other."
        )

    @mcp.prompt("community_summary")
    def prompt_community_summary(community_id: str) -> str:
        """Prompt template to summarize a high-level graph cluster."""
        return (
            f"Examine the community cluster '{community_id}' using graphrag_community.\n"
            f"Describe the central theme, member entities, and overall significance."
        )

    # ------------------------------------------------------------------
    # Internal Tool Invoker (for batch execution)
    # ------------------------------------------------------------------

    def _call_tool_internal(name: str, args: dict[str, Any]) -> Any:
        return asyncio.run(mcp.call_tool(name, args))

    # ------------------------------------------------------------------
    # Contract 1 — Retrieval Tools
    # ------------------------------------------------------------------

    @mcp.tool(
        name="graphrag_search",
        title="Natural-language GraphRAG search",
        description="Search the graph with automatic routing (local/global/hybrid/entity).",
    )
    def graphrag_search(
        query: str,
        mode: str = "auto",
        depth: int = 2,
        top_k: int = 10,
        format_text: str = "none",
        max_tokens: int = _DEFAULT_MAX_TOKENS,
        explain: bool = False,
    ) -> str:
        cache_key = QueryCache.make_key("search", {"q": query, "m": mode, "d": depth, "k": top_k, "exp": explain})
        cached = STATE._cache.get(cache_key)
        if cached:
            return _json(cached)

        res = STATE.retrieval.search(query=query, mode=mode, depth=depth, top_k=top_k)
        payload = _context_payload(res.context, format_text=format_text, max_tokens=max_tokens)
        if explain:
            payload["why_retrieved"] = STATE.explanation.explain(res.context, max_entities=top_k)
        STATE._cache.set(cache_key, "search", payload)
        return _json(payload)

    @mcp.tool(
        name="graphrag_local_search",
        title="Entity-centric local subgraph search",
        description="Traverse outward from matched entities within depth hops.",
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
        title="Global community-summary search",
        description="Broad macro-level synthesis over precomputed community summaries.",
    )
    def graphrag_global_search(
        query: str,
        community_level: int = 2,
        top_communities: int = 10,
        format_text: str = "none",
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> str:
        ctx = STATE.retrieval.global_search(query=query, community_level=community_level, top_communities=top_communities)
        return _json(_context_payload(ctx, format_text=format_text, max_tokens=max_tokens))

    @mcp.tool(
        name="graphrag_hybrid_search",
        title="Hybrid vector + graph search",
        description="Score fusion between vector similarity and graph topology.",
    )
    def graphrag_hybrid_search(
        query: str,
        vector_weight: float = 0.5,
        graph_weight: float = 0.5,
        depth: int = 2,
        top_k: int = 10,
        format_text: str = "none",
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> str:
        ctx = STATE.retrieval.hybrid_search(
            query=query, vector_weight=vector_weight, graph_weight=graph_weight, depth=depth, top_k=top_k
        )
        return _json(_context_payload(ctx, format_text=format_text, max_tokens=max_tokens))

    @mcp.tool(
        name="graphrag_entity",
        title="Entity lookup",
        description="Fetch a specific entity by id/name plus its immediate context.",
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
        description="Find connections between two entities using BFS, Dijkstra, or Yen's algorithm.",
    )
    def graphrag_path(
        source: str,
        target: str,
        max_hops: int = 4,
        algorithm: str = "bfs",
        format_text: str = "none",
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> str:
        ctx = STATE.retrieval.path_search(source=source, target=target, max_hops=max_hops)
        return _json(_context_payload(ctx, format_text=format_text, max_tokens=max_tokens))

    @mcp.tool(
        name="graphrag_neighborhood",
        title="Entity neighborhood expansion",
        description="Expand outward from an entity within depth hops.",
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
        description="List members of a community cluster.",
    )
    def graphrag_community(
        community_id: str,
        include_summary: bool = True,
        format_text: str = "none",
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> str:
        ctx = STATE.retrieval.community_members(community_id=community_id, include_summary=include_summary)
        return _json(_context_payload(ctx, format_text=format_text, max_tokens=max_tokens))

    # ------------------------------------------------------------------
    # Contract 3 — Schema Discovery Tools
    # ------------------------------------------------------------------

    @mcp.tool(
        name="graphrag_schema",
        title="Graph schema",
        description="Return full graph schema: vertex types, edge types, statistics.",
    )
    def graphrag_schema(graph_id: str | None = None) -> str:
        return _json(STATE.schema.get_schema(graph_id=graph_id).model_dump(mode="json"))

    @mcp.tool(
        name="graphrag_entity_types",
        title="Entity types",
        description="List all vertex types with attributes and counts.",
    )
    def graphrag_entity_types(graph_id: str | None = None) -> str:
        types = STATE.schema.get_entity_types(graph_id=graph_id)
        return _json([t.model_dump(mode="json") for t in types])

    @mcp.tool(
        name="graphrag_relationship_types",
        title="Relationship types",
        description="List all edge types with source/target and counts.",
    )
    def graphrag_relationship_types(graph_id: str | None = None) -> str:
        types = STATE.schema.get_relationship_types(graph_id=graph_id)
        return _json([t.model_dump(mode="json") for t in types])

    @mcp.tool(
        name="graphrag_sample",
        title="Sample entities",
        description="Sample entities of a given vertex type for schema context.",
    )
    def graphrag_sample(entity_type: str, count: int = 5, graph_id: str | None = None) -> str:
        return _json(STATE.schema.get_sample_entities(entity_type=entity_type, count=count, graph_id=graph_id))

    # ------------------------------------------------------------------
    # Contract 5 — Provenance Tools
    # ------------------------------------------------------------------

    @mcp.tool(
        name="graphrag_provenance",
        title="Citation trace",
        description="Full citation chain and provenance for a fact or entity.",
    )
    def graphrag_provenance(fact_id: str) -> str:
        return _json(STATE.provenance.trace_citation(fact_id).model_dump(mode="json"))

    @mcp.tool(
        name="graphrag_trajectory",
        title="Traversal trajectory",
        description="Ordered traversal steps taken across the graph for a query.",
    )
    def graphrag_trajectory(query_id: str) -> str:
        steps = STATE.provenance.get_traversal_trajectory(query_id=query_id)
        return _json([s.model_dump(mode="json") for s in steps])

    @mcp.tool(
        name="graphrag_sources",
        title="Source documents",
        description="Deduplicated list of source documents supporting an entity.",
    )
    def graphrag_sources(entity_id: str) -> str:
        return _json(STATE.provenance.get_source_documents(entity_id=entity_id))

    @mcp.tool(
        name="graphrag_audit",
        title="Provenance audit",
        description="Audit completeness score for a SubgraphContext provenance trail.",
    )
    def graphrag_audit(context: dict[str, Any]) -> str:
        prov = STATE.provenance._coerce_provenance(context.get("provenance"))
        return _json(STATE.provenance.audit_provenance_completeness(prov))

    # ------------------------------------------------------------------
    # Contract 8 — Formatting Tool
    # ------------------------------------------------------------------

    @mcp.tool(
        name="graphrag_format",
        title="Format subgraph context",
        description="Format a SubgraphContext envelope into bounded, LLM-ready text.",
    )
    def graphrag_format(
        context: dict[str, Any],
        format_text: str = "markdown",
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> str:
        try:
            ctx = SubgraphContext(**context)
        except Exception as exc:  # noqa: BLE001
            return _json({"error": f"Invalid context structure: {exc}"})
        formatted = _format(ctx, format_text=format_text, max_tokens=max_tokens)
        return formatted or _json(ctx.model_dump(mode="json"))

    # ------------------------------------------------------------------
    # Admin / Status Tools
    # ------------------------------------------------------------------

    @mcp.tool(
        name="graphrag_status",
        title="Backend status & health",
        description="Health check and high-level graph statistics.",
    )
    def graphrag_status() -> str:
        health = STATE.adapter.health_check()
        try:
            stats = STATE.schema.get_statistics().model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001
            stats = {"error": str(exc)}
        return _json({
            "backend": health,
            "statistics": stats,
            "cache": {"hits": STATE._cache.hits, "misses": STATE._cache.misses},
        })

    @mcp.tool(
        name="graphrag_config",
        title="Server configuration",
        description="Echo current protocol, backend, and extraction config.",
    )
    def graphrag_config() -> str:
        return _json({
            "protocol": "graphrag/1.0",
            "server_version": "0.2.0",
            "backend_adapter": type(STATE.adapter).__name__,
            "default_max_tokens": _DEFAULT_MAX_TOKENS,
            "extraction_strategy": _DEFAULT_EXTRACTION_STRATEGY,
        })

    @mcp.tool(
        name="graphrag_list_backends",
        title="List federated backends",
        description="List registered backends available for federated queries.",
    )
    def graphrag_list_backends() -> str:
        return _json([b.model_dump(mode="json") for b in STATE.federation.list_backends()])

    # ------------------------------------------------------------------
    # Contract 4 — Construction Tools (admin protected)
    # ------------------------------------------------------------------

    @mcp.tool(
        name="graphrag_ingest",
        title="Ingest documents into knowledge graph",
        description="Ingest documents into graph (requires admin token or editor role).",
    )
    def graphrag_ingest(
        documents: list[dict[str, Any]],
        extraction_strategy: str = _DEFAULT_EXTRACTION_STRATEGY,
        admin_token: str | None = None,
        async_mode: bool = False,
    ) -> str:
        decision = STATE.authorization.check_permission("ingest", token=admin_token)
        if not decision.allowed:
            return _json({"error": "permission denied", **decision.model_dump()})

        if async_mode:
            job_id = f"job-{uuid.uuid4().hex[:8]}"
            STATE._storage.save_job(job_id=job_id, status="running", graph_id="default", document_count=len(documents))

            def _bg_run():
                try:
                    cfg = IngestionConfig(extraction_strategy=extraction_strategy)
                    rep = STATE.construction.ingest(documents, config=cfg)
                    STATE._storage.save_job(
                        job_id=job_id, status="completed", graph_id="default",
                        document_count=len(documents), report=rep.model_dump(mode="json")
                    )
                    STATE._cache.invalidate()
                except Exception as ex:  # noqa: BLE001
                    STATE._storage.save_job(job_id=job_id, status="failed", graph_id="default", error=str(ex))

            asyncio.get_event_loop().run_in_executor(None, _bg_run)
            return _json({"job_id": job_id, "status": "running", "message": "Ingestion job launched in background"})

        cfg = IngestionConfig(extraction_strategy=extraction_strategy)
        report = STATE.construction.ingest(documents, config=cfg)
        STATE._cache.invalidate()
        return _json(report.model_dump(mode="json"))

    @mcp.tool(
        name="graphrag_delete_document",
        title="Delete document vertex",
        description="Delete a document vertex and cascade references (requires admin token).",
    )
    def graphrag_delete_document(document_id: str, admin_token: str | None = None) -> str:
        decision = STATE.authorization.check_permission("delete_document", token=admin_token)
        if not decision.allowed:
            return _json({"error": "permission denied", **decision.model_dump()})
        report = STATE.construction.delete_document(document_id)
        STATE._cache.invalidate()
        return _json(report.model_dump(mode="json"))

    # ------------------------------------------------------------------
    # Contract 6 — Federation Tools
    # ------------------------------------------------------------------

    @mcp.tool(
        name="graphrag_federated_search",
        title="Federated search across graphs",
        description="Query multiple graph backends and merge results with RRF.",
    )
    def graphrag_federated_search(
        query: str,
        backends: list[str] | None = None,
        merge_strategy: str = "rrf",
        top_k: int = 10,
        format_text: str = "none",
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> str:
        allowed = [b.name for b in STATE.federation.list_backends()]
        chosen = backends or allowed or ["primary"]
        backend_refs = [
            BackendRef(name=b, graph_id=getattr(STATE.adapter, "_graphname", b))
            for b in chosen
        ]
        cfg = FederationConfig(
            backends=backend_refs,
            merge_strategy=MergeStrategy(merge_strategy),
            top_k=top_k,
        )
        ctx = STATE.federation.federated_search(query=query, config=cfg)
        return _json(_context_payload(ctx, format_text=format_text, max_tokens=max_tokens))

    @mcp.tool(
        name="graphrag_entity_link",
        title="Cross-graph entity link",
        description="Find entity references across federated backends.",
    )
    def graphrag_entity_link(entity_name: str, backends: list[str] | None = None) -> str:
        allowed = [b.name for b in STATE.federation.list_backends()]
        refs = [BackendRef(name=b, graph_id=b) for b in (backends or allowed)]
        links = STATE.federation.cross_graph_entity_link(entity_name=entity_name, backends=refs)
        return _json([link.model_dump(mode="json") for link in links])

    # ------------------------------------------------------------------
    # Contract 7 — Streaming Tool
    # ------------------------------------------------------------------

    @mcp.tool(
        name="graphrag_events",
        title="Recent graph mutation events",
        description="Read recent events from the streaming event bus.",
    )
    def graphrag_events(limit: int = 20) -> str:
        events = STREAM_BUS.recent(limit)
        return _json([e.model_dump(mode="json") for e in events])

    # ------------------------------------------------------------------
    # Contract 9 — Evaluation Tool
    # ------------------------------------------------------------------

    @mcp.tool(
        name="graphrag_evaluate",
        title="Evaluate retrieval and answer quality",
        description="Compute standard precision@k, recall@k, BERTScore, and LLM-as-judge scores.",
    )
    def graphrag_evaluate(
        query: str,
        answer: str,
        context: dict[str, Any],
        references_path: str | None = None,
        query_id: str | None = None,
        judge: bool = False,
        bert_score: bool = False,
    ) -> str:
        try:
            ctx = SubgraphContext(**context)
        except Exception as exc:  # noqa: BLE001
            return _json({"error": f"Invalid context: {exc}"})

        ref_file = references_path or os.environ.get("GRAPHRAG_REFERENCES_PATH")
        references: dict[str, Any] = {}
        if ref_file and os.path.isfile(ref_file):
            try:
                with open(ref_file, encoding="utf-8") as f:
                    references = json.load(f)
            except Exception:  # noqa: BLE001
                references = {}

        report = STATE.evaluation.evaluate_report(
            query=query, answer=answer, context=ctx, references=references,
            query_id=query_id, judge=judge, bert_score=bert_score
        )
        return _json(report.model_dump(mode="json"))

    # ------------------------------------------------------------------
    # Contract 10 — Authorization Tool
    # ------------------------------------------------------------------

    @mcp.tool(
        name="graphrag_authorize",
        title="Permission check",
        description="Check whether an operation is permitted for a bearer or capability token.",
    )
    def graphrag_authorize(
        operation: str,
        token: str | None = None,
        graph_id: str | None = None,
    ) -> str:
        res = STATE.authorization.check_permission(operation=operation, graph_id=graph_id, token=token)
        return _json(res.model_dump(mode="json"))

    # ------------------------------------------------------------------
    # Contract 11 — Semantic Similarity Tools
    # ------------------------------------------------------------------

    @mcp.tool(
        name="graphrag_similarity",
        title="Semantic similarity",
        description="Compute cosine (vector) or Jaccard similarity between two text blobs.",
    )
    def graphrag_similarity(text_a: str, text_b: str) -> str:
        return _json(STATE.similarity.similarity(text_a, text_b))

    @mcp.tool(
        name="graphrag_entity_similarity",
        title="Entity semantic similarity",
        description="Compare two entities by ID using their names and properties text.",
    )
    def graphrag_entity_similarity(entity_id_a: str, entity_id_b: str) -> str:
        return _json(STATE.similarity.entity_similarity(entity_id_a, entity_id_b))

    @mcp.tool(
        name="graphrag_batch_similarity",
        title="Batch similarity ranking",
        description="Rank candidate texts by similarity to an anchor text, highest first.",
    )
    def graphrag_batch_similarity(anchor: str, candidates: list[str]) -> str:
        return _json(STATE.similarity.batch_similarity(anchor, candidates))

    # ------------------------------------------------------------------
    # Contract 12 — Temporal Query Tool
    # ------------------------------------------------------------------

    @mcp.tool(
        name="graphrag_temporal_search",
        title="Temporal search",
        description="Retrieve entities filtered by date range (start/end ISO-8601).",
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
        ctx = STATE.temporal.temporal_search(
            query=query, start=start, end=end, mode=mode, top_k=top_k, depth=depth
        )
        return _json(_context_payload(ctx, format_text=format_text, max_tokens=max_tokens))

    # ------------------------------------------------------------------
    # Contract 13 — Explanation Tools
    # ------------------------------------------------------------------

    @mcp.tool(
        name="graphrag_explain",
        title="Explain retrieval",
        description="Generate natural-language explanations for why entities were retrieved for a query or in a SubgraphContext. Accepts either 'query' string or 'context' dictionary.",
    )
    def graphrag_explain(
        query: str | None = None,
        context: dict[str, Any] | None = None,
        max_entities: int = 10,
    ) -> str:
        if context is None and not query:
            return _json({"error": "Either 'query' or 'context' must be provided."})
        if context is None and query:
            ctx = STATE.retrieval.search(query=query, mode="auto").context
        else:
            try:
                ctx = SubgraphContext(**context)
            except Exception as exc:  # noqa: BLE001
                return _json({"error": f"Invalid context: {exc}"})
        return _json(STATE.explanation.explain(ctx, max_entities=max_entities))

    @mcp.tool(
        name="graphrag_explain_path",
        title="Explain path",
        description="Explain the reasoning behind each path found in a path_search SubgraphContext.",
    )
    def graphrag_explain_path(context: dict[str, Any]) -> str:
        try:
            ctx = SubgraphContext(**context)
        except Exception as exc:  # noqa: BLE001
            return _json({"error": f"Invalid context: {exc}"})
        return _json(STATE.explanation.explain_path(ctx))

    # ------------------------------------------------------------------
    # Contract 14 — Diff Tools
    # ------------------------------------------------------------------

    @mcp.tool(
        name="graphrag_diff",
        title="Context diff",
        description="Structural delta between two SubgraphContext envelopes.",
    )
    def graphrag_diff(
        context_a: dict[str, Any],
        context_b: dict[str, Any],
        label_a: str = "a",
        label_b: str = "b",
    ) -> str:
        try:
            ctx_a = SubgraphContext(**context_a)
            ctx_b = SubgraphContext(**context_b)
        except Exception as exc:  # noqa: BLE001
            return _json({"error": f"Invalid context: {exc}"})
        return _json(STATE.diff.diff_contexts(ctx_a, ctx_b, label_a=label_a, label_b=label_b))

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
        return _json(STATE.diff.diff_queries(query_a=query_a, query_b=query_b, mode=mode, top_k=top_k, depth=depth))

    # ------------------------------------------------------------------
    # Contract 15 — Aggregate Tools
    # ------------------------------------------------------------------

    @mcp.tool(
        name="graphrag_count",
        title="Count entities",
        description="Count entities of a given type, optionally with attribute filters.",
    )
    def graphrag_count(entity_type: str | None = None, filters: dict[str, Any] | None = None) -> str:
        return _json(STATE.aggregate.count(entity_type=entity_type, filters=filters))

    @mcp.tool(
        name="graphrag_group_by",
        title="Group entities by attribute",
        description="Group entities of a type by an attribute and return counts per group.",
    )
    def graphrag_group_by(entity_type: str, attribute: str, top_n: int = 20) -> str:
        return _json(STATE.aggregate.group_by(entity_type=entity_type, attribute=attribute, top_n=top_n))

    @mcp.tool(
        name="graphrag_top_n",
        title="Top-N entities by attribute",
        description="Return top-N entities of a type ranked by a numeric attribute value.",
    )
    def graphrag_top_n(entity_type: str, rank_by: str, n: int = 10, descending: bool = True) -> str:
        return _json(STATE.aggregate.top_n(entity_type=entity_type, rank_by=rank_by, n=n, descending=descending))

    @mcp.tool(
        name="graphrag_stats_summary",
        title="Graph statistics summary",
        description="Comprehensive statistics: vertex/edge counts by type, density, connected components.",
    )
    def graphrag_stats_summary() -> str:
        return _json(STATE.aggregate.stats_summary())

    @mcp.tool(
        name="graphrag_job_status",
        title="Ingestion job status",
        description="Check the status of a background ingestion job (persisted in SQLite).",
    )
    def graphrag_job_status(job_id: str) -> str:
        job = STATE._storage.get_job(job_id)
        if job:
            return _json(job)
        return _json({"job_id": job_id, "status": "not_found", "error": "Unknown job id"})

    @mcp.tool(
        name="graphrag_register_backend",
        title="Register federated backend",
        description="Register a named backend adapter for federated queries (requires admin token).",
    )
    def graphrag_register_backend(name: str, graph_id: str, weight: float = 1.0, admin_token: str | None = None) -> str:
        decision = STATE.authorization.check_permission("register_backend", token=admin_token)
        if not decision.allowed:
            return _json({"error": "permission denied", **decision.model_dump()})
        ref = STATE.federation.register_backend(name=name, weight=weight)
        return _json(ref.model_dump())

    @mcp.tool(
        name="graphrag_audit_log",
        title="Audit log",
        description="Return persistent timestamped write operations log from SQLite.",
    )
    def graphrag_audit_log(limit: int = 50) -> str:
        events = STATE._storage.get_events(limit=limit)
        return _json({"total": len(events), "events": events})

    # ------------------------------------------------------------------
    # Contract 16 — Subgraph Export
    # ------------------------------------------------------------------

    @mcp.tool(
        name="graphrag_export_subgraph",
        title="Export subgraph format",
        description="Export a SubgraphContext into portable graphml, cypher, json_ld, or rdf_turtle.",
    )
    def graphrag_export_subgraph(context: dict[str, Any], format: str = "graphml") -> str:
        try:
            ctx = SubgraphContext(**context)
        except Exception as exc:  # noqa: BLE001
            return _json({"error": f"Invalid context: {exc}"})
        return _json(STATE.export.export(ctx, format=format))

    # ------------------------------------------------------------------
    # Contract 17 — Batch Execution
    # ------------------------------------------------------------------

    @mcp.tool(
        name="graphrag_batch",
        title="Execute batch of tools",
        description="Execute an array of up to 25 tool operations concurrently in a single round-trip.",
    )
    def graphrag_batch(calls: list[dict[str, Any]]) -> str:
        batcher = BatchContract(tool_executor=_call_tool_internal)
        return _json(batcher.execute_batch(calls))

    # ------------------------------------------------------------------
    # Contract 18 — Watch & Push Notifications
    # ------------------------------------------------------------------

    @mcp.tool(
        name="graphrag_watch",
        title="Watch graph mutations",
        description="Query and observe graph change events with filters and replay.",
    )
    def graphrag_watch(
        graph_id: str | None = None,
        event_types: list[str] | None = None,
        entity_id: str | None = None,
        since_timestamp: str | None = None,
        limit: int = 50,
    ) -> str:
        return _json(STATE.watch.watch(
            graph_id=graph_id, event_types=event_types,
            entity_id=entity_id, since_timestamp=since_timestamp, limit=limit
        ))

    # ------------------------------------------------------------------
    # Pagination Cursor
    # ------------------------------------------------------------------

    @mcp.tool(
        name="graphrag_next_page",
        title="Next page of large subgraph",
        description="Fetch next page of entities and relationships using a cursor.",
    )
    def graphrag_next_page(cursor: str, page_size: int = 50) -> str:
        entry = _CURSORS.get(cursor)
        if not entry:
            return _json({"error": f"Cursor {cursor!r} not found or expired"})
        items = entry.get("items", [])
        offset = entry.get("offset", 0)
        sliced = items[offset:offset + page_size]
        new_offset = offset + page_size
        has_more = new_offset < len(items)
        if has_more:
            entry["offset"] = new_offset
        else:
            _CURSORS.pop(cursor, None)

        return _json({
            "items": sliced,
            "page_size": len(sliced),
            "next_cursor": cursor if has_more else None,
            "has_more": has_more,
        })

    # ------------------------------------------------------------------
    # Capability Tokens (5-tier RBAC)
    # ------------------------------------------------------------------

    @mcp.tool(
        name="graphrag_capability_token",
        title="Issue capability token",
        description="Mint a signed HMAC capability token granting analyst/editor/admin privileges.",
    )
    def graphrag_capability_token(
        role: str = "analyst",
        operations: list[str] | None = None,
        ttl_seconds: int = 3600,
        admin_token: str | None = None,
    ) -> str:
        try:
            token = STATE.authorization.issue_capability_token(
                role=role, operations=operations, ttl_seconds=ttl_seconds, admin_token=admin_token
            )
            return _json({
                "token": token,
                "role": role,
                "ttl_seconds": ttl_seconds,
                "status": "active",
            })
        except Exception as exc:  # noqa: BLE001
            return _json({"error": str(exc)})

    # ------------------------------------------------------------------
    # Contract 19 — Conflict & Uncertainty Resolution
    # ------------------------------------------------------------------

    @mcp.tool(
        name="graphrag_resolve_conflicts",
        title="Resolve contradictory facts",
        description=(
            "Detect and resolve conflicting properties, claims, or relationships on a topic or within a SubgraphContext "
            "using temporal recency and source authority. Accepts either a natural-language 'query' string (auto-retrieves "
            "the subgraph context) OR a pre-existing 'context' dictionary."
        ),
    )
    def graphrag_resolve_conflicts(
        query: str | None = None,
        context: dict[str, Any] | None = None,
        recency_weight: float = 0.6,
        authority_weight: float = 0.4,
    ) -> str:
        if context is None and not query:
            return _json({"error": "Either 'query' or 'context' must be provided to resolve conflicts."})
        if context is None and query:
            ctx = STATE.retrieval.search(query=query, mode="auto").context
        else:
            try:
                ctx = SubgraphContext(**context)
            except Exception as exc:  # noqa: BLE001
                return _json({"error": f"Invalid context envelope: {exc}"})
        return _json(
            STATE.conflicts.resolve_conflicts(
                ctx, recency_weight=recency_weight, authority_weight=authority_weight
            )
        )

    # ------------------------------------------------------------------
    # Contract 20 — Query Triage & ROI Classifier
    # ------------------------------------------------------------------

    @mcp.tool(
        name="graphrag_triage_query",
        title="Query triage and ROI classifier",
        description="Analyze a question and determine whether plain RAG, standard GraphRAG, or Agentic GraphRAG is optimal, computing estimated token cost vs accuracy ROI.",
    )
    def graphrag_triage_query(query: str) -> str:
        try:
            return _json(STATE.triage.triage(query))
        except Exception as exc:  # noqa: BLE001
            return _json({"error": str(exc)})

    # ------------------------------------------------------------------
    # Autonomous Agentic Investigation Harness
    # ------------------------------------------------------------------

    @mcp.tool(
        name="graphrag_agent_investigate",
        title="Autonomous multi-step investigation",
        description="Execute an autonomous multi-step agentic graph investigation across entity linking, traversal, paths, and evidence evaluation. Returns grounded answer and detailed agentic trace.",
    )
    def graphrag_agent_investigate(
        question: str,
        max_steps: int = 5,
        target_confidence: float = 0.85,
    ) -> str:
        try:
            harness = AgenticInvestigationHarness(STATE.adapter)
            res = harness.investigate(
                question=question,
                max_steps=max_steps,
                target_confidence=target_confidence,
            )
            return _json({
                "question": res.question,
                "answer": res.answer,
                "answer_source": res.answer_source,
                "trace": res.trace.model_dump(),
                "entities_used": len(res.context.results.get("entities") or []),
                "relationships_used": len(res.context.results.get("relationships") or []),
                "source_documents": res.context.provenance.source_documents,
            })
        except Exception as exc:  # noqa: BLE001
            return _json({"error": str(exc)})

    # ------------------------------------------------------------------
    # MCP Prompts
    # ------------------------------------------------------------------

    @mcp.prompt(
        name="investigate_complex_question",
        description="Execute an autonomous multi-step investigation across entities, relationships, and evidence to answer complex questions.",
    )
    def prompt_investigate(question: str) -> str:
        return (
            f"Please conduct an autonomous multi-step GraphRAG investigation to thoroughly answer this question:\n\n"
            f'"{question}"\n\n'
            "Workflow:\n"
            "1. Triage the question using `graphrag_triage_query`.\n"
            "2. If agentic reasoning is recommended, execute `graphrag_agent_investigate` or chain specialized tools (`graphrag_entity`, `graphrag_neighborhood`, `graphrag_path`).\n"
            "3. If multiple conflicting claims appear, resolve them with `graphrag_resolve_conflicts`.\n"
            "4. Verify the evidence trail with `graphrag_audit` and provide an answer with explicit citations."
        )

    @mcp.prompt(
        name="compare_pipelines",
        description="Benchmark RAG vs GraphRAG vs Agentic GraphRAG side-by-side with token and accuracy metrics.",
    )
    def prompt_compare(question: str) -> str:
        return (
            f"Benchmark the three retrieval paradigms on this query:\n\n"
            f'"{question}"\n\n'
            "1. Run plain text search using `graphrag_local_search(depth=0)`.\n"
            "2. Run standard GraphRAG using `graphrag_search(mode='auto')`.\n"
            "3. Run Agentic GraphRAG using `graphrag_agent_investigate`.\n"
            "4. Compare their answers, context sizes, and token efficiency."
        )

    @mcp.prompt(
        name="resolve_graph_conflicts",
        description="Detect and resolve contradictory statements, changing facts, or competing sources in the graph.",
    )
    def prompt_resolve_conflicts(entity_or_topic: str) -> str:
        return (
            f'Analyze contradictory evidence and temporal changes regarding: "{entity_or_topic}".\n\n'
            "1. Retrieve the neighborhood and temporal context using `graphrag_neighborhood` and `graphrag_temporal_search`.\n"
            "2. Call `graphrag_resolve_conflicts` to evaluate recency and provenance authority.\n"
            "3. Present the resolved ground truth and flag remaining uncertainties."
        )

    return mcp


def main() -> None:
    """Run the MCP server over stdio or streamable-http."""
    load_dotenv()
    parser = argparse.ArgumentParser(description="GraphRAG Interoperability Protocol (GRIP) MCP Server")
    parser.add_argument("--transport", default="stdio", choices=["stdio", "streamable-http", "sse"], help="Transport mode")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host for HTTP/SSE")
    parser.add_argument("--port", type=int, default=8000, help="Bind port for HTTP/SSE")
    args = parser.parse_args()

    server = build_server()
    if args.transport == "stdio":
        server.run(transport="stdio")
    elif args.transport in ("streamable-http", "sse"):
        server.run(transport="streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()