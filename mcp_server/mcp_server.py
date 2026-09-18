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
from mcp_server.contracts.provenance import ProvenanceContract
from mcp_server.contracts.retrieval import RetrievalContract
from mcp_server.contracts.schema_discovery import SchemaDiscoveryContract
from mcp_server.formatters import MarkdownFormatter, StructuredFormatter
from mcp_server.protocol import SubgraphContext

_DEFAULT_MAX_TOKENS = 4096


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
    """Construct the MCP server with all 20 tools registered."""
    mcp = MCPServer(
        name="graphrag-protocol",
        version="0.1.0",
        instructions=(
            "GraphRAG Protocol: uniform access to any GraphRAG backend. "
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
        ctx = SubgraphContext(**context)
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
                "llm_model": os.environ.get("LLM_MODEL", "gemini-2.5-flash"),
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

    return mcp


def main() -> None:
    """Run the MCP server over stdio (the transport MCP clients expect)."""
    load_dotenv()
    server = build_server()
    server.run(transport="stdio")


if __name__ == "__main__":
    main()