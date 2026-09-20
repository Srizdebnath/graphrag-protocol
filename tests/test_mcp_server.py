"""MCP server tests — in-memory, real tools, demo adapter, zero network.

Verifies the MCP layer itself: tool registration (all 42 protocol tools),
invocation through the contract layer, JSON envelope shape, formatting and
admin tools. The TigerGraph adapter is bypassed by injecting the demo
adapter into the shared state, so these run hermetically; live-backend
behavior is covered separately by integration tests.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from mcp_server import mcp_server as m
from mcp_server.adapters import DemoGraphRAGAdapter


@pytest.fixture()
def server():
    """build_server() with the shared state pinned to the demo adapter."""
    saved = m.STATE
    state = m.GraphRAGState()
    state._adapter = DemoGraphRAGAdapter()
    m.STATE = state
    yield m.build_server()
    m.STATE = saved


def _call(server, name: str, arguments: dict) -> dict:
    result = asyncio.run(server.call_tool(name, arguments))
    assert result.is_error is not True, f"tool {name} errored: {result.content}"
    return json.loads(result.content[0].text)


def test_registers_all_50_protocol_tools(server):
    tools = asyncio.run(server.list_tools())
    names = {t.name for t in tools}
    assert len(names) == 50
    # Original 27 tools
    original_27 = {
        "graphrag_search",
        "graphrag_local_search",
        "graphrag_global_search",
        "graphrag_hybrid_search",
        "graphrag_entity",
        "graphrag_path",
        "graphrag_neighborhood",
        "graphrag_community",
        "graphrag_schema",
        "graphrag_entity_types",
        "graphrag_relationship_types",
        "graphrag_sample",
        "graphrag_provenance",
        "graphrag_trajectory",
        "graphrag_sources",
        "graphrag_audit",
        "graphrag_format",
        "graphrag_status",
        "graphrag_config",
        "graphrag_list_backends",
        "graphrag_ingest",
        "graphrag_delete_document",
        "graphrag_federated_search",
        "graphrag_entity_link",
        "graphrag_events",
        "graphrag_evaluate",
        "graphrag_authorize",
    }
    # 15 tools (Contracts 11-15 + job, backend, audit)
    new_15 = {
        "graphrag_similarity",
        "graphrag_entity_similarity",
        "graphrag_batch_similarity",
        "graphrag_temporal_search",
        "graphrag_explain",
        "graphrag_explain_path",
        "graphrag_diff",
        "graphrag_diff_queries",
        "graphrag_count",
        "graphrag_group_by",
        "graphrag_top_n",
        "graphrag_stats_summary",
        "graphrag_job_status",
        "graphrag_register_backend",
        "graphrag_audit_log",
    }
    # 5 tools (Contracts 16-18 + pagination & capability tokens)
    new_5 = {
        "graphrag_export_subgraph",
        "graphrag_batch",
        "graphrag_watch",
        "graphrag_next_page",
        "graphrag_capability_token",
    }
    # 3 tools (Contracts 19-20 + autonomous investigation)
    new_3 = {
        "graphrag_agent_investigate",
        "graphrag_resolve_conflicts",
        "graphrag_triage_query",
    }
    expected = original_27 | new_15 | new_5 | new_3
    assert names == expected


def test_search_returns_protocol_envelope(server):
    out = _call(server, "graphrag_search", {"query": "transformer attention", "mode": "auto"})
    assert out["protocol"].startswith("graphrag/")
    assert out["operation"] in {"local_search", "global_search", "hybrid_search", "entity_lookup"}
    assert {"entities", "relationships", "paths", "communities", "text_chunks"} <= set(out["results"])
    assert "provenance" in out and "metrics" in out


def test_entity_lookup_by_id(server):
    out = _call(server, "graphrag_entity", {"entity_id": "paper:attention", "depth": 1})
    entities = out["results"]["entities"]
    assert entities, "expected at least the requested entity"
    assert entities[0]["id"] == "paper:attention"


def test_schema_shape(server):
    out = _call(server, "graphrag_schema", {})
    assert out["protocol"].startswith("graphrag/")
    assert isinstance(out["vertex_types"], list) and out["vertex_types"]
    assert isinstance(out["edge_types"], list)
    assert "total_vertices" in out["statistics"]


def test_provenance_trace(server):
    out = _call(server, "graphrag_provenance", {"fact_id": "paper:attention"})
    assert "traversal_log" in out and "source_documents" in out
    assert out["traversal_log"], "seed entity should appear in the traversal log"


def test_format_roundtrip(server):
    envelope = _call(server, "graphrag_search", {"query": "attention mechanism", "mode": "local"})
    result = asyncio.run(
        server.call_tool("graphrag_format", {"context": envelope, "format_text": "markdown", "max_tokens": 512})
    )
    assert result.is_error is not True
    text = result.content[0].text
    assert isinstance(text, str) and len(text) > 0
    # Re-formatting into JSON mode must produce parseable structured text.
    result2 = asyncio.run(
        server.call_tool("graphrag_format", {"context": envelope, "format_text": "structured", "max_tokens": 512})
    )
    assert result2.is_error is not True


def test_status_and_config(server):
    status = _call(server, "graphrag_status", {})
    assert status["backend"]["backend"] == "demo"
    assert status["statistics"]["total_vertices"] >= 0
    config = _call(server, "graphrag_config", {})
    assert config["protocol"] == "graphrag/1.0"
    assert "secret" not in json.dumps(config).lower()


def test_unknown_tool_raises(server):
    from mcp.server.mcpserver.exceptions import ToolError

    with pytest.raises(ToolError):
        asyncio.run(server.call_tool("graphrag_nonexistent", {}))


def test_new_similarity_tools(server):
    res = _call(server, "graphrag_similarity", {"text_a": "attention transformer", "text_b": "attention mechanism"})
    assert "score" in res
    assert 0.0 <= res["score"] <= 1.0

    res2 = _call(server, "graphrag_entity_similarity", {"entity_id_a": "paper:bert", "entity_id_b": "paper:attention"})
    assert "score" in res2
    assert res2["entity_a"] == "paper:bert"

    res3 = _call(server, "graphrag_batch_similarity", {"anchor": "transformer", "candidates": ["attention", "biology"]})
    assert len(res3) == 2


def test_new_temporal_tool(server):
    res = _call(server, "graphrag_temporal_search", {"query": "transformer", "start": "2017-01-01", "end": "2024-01-01"})
    assert res["operation"] == "temporal_search"
    assert "entities" in res["results"]


def test_new_explanation_tools(server):
    ctx = _call(server, "graphrag_search", {"query": "transformer", "mode": "local"})
    exp = _call(server, "graphrag_explain", {"context": ctx})
    assert "explanations" in exp
    assert "traversal_summary" in exp

    path_ctx = _call(server, "graphrag_path", {"source": "paper:attention", "target": "concept:transformer"})
    exp_path = _call(server, "graphrag_explain_path", {"context": path_ctx})
    assert "paths" in exp_path


def test_new_diff_tools(server):
    ctx_a = _call(server, "graphrag_search", {"query": "transformer", "mode": "local"})
    ctx_b = _call(server, "graphrag_search", {"query": "bert", "mode": "local"})
    d = _call(server, "graphrag_diff", {"context_a": ctx_a, "context_b": ctx_b})
    assert "entities" in d
    assert "summary" in d

    dq = _call(server, "graphrag_diff_queries", {"query_a": "transformer", "query_b": "bert"})
    assert "entities" in dq
    assert "summary" in dq


def test_new_aggregate_tools(server):
    count_res = _call(server, "graphrag_count", {"entity_type": "Paper"})
    assert "count" in count_res

    group_res = _call(server, "graphrag_group_by", {"entity_type": "Paper", "attribute": "year"})
    assert "groups" in group_res

    top_res = _call(server, "graphrag_top_n", {"entity_type": "Paper", "rank_by": "year", "n": 2})
    assert "entities" in top_res

    stats = _call(server, "graphrag_stats_summary", {})
    assert "total_vertices" in stats


def test_new_admin_and_job_tools(server, monkeypatch):
    status = _call(server, "graphrag_job_status", {"job_id": "nonexistent_job"})
    assert status["status"] == "not_found"

    monkeypatch.setenv("GRAPHRAG_ADMIN_TOKEN", "test_admin_token")
    reg = _call(server, "graphrag_register_backend", {"name": "test_be", "graph_id": "demo_graph", "admin_token": "test_admin_token"})
    assert reg["name"] == "test_be"

    audit = _call(server, "graphrag_audit_log", {"limit": 10})
    assert "events" in audit


def test_new_export_tool(server):
    ctx = _call(server, "graphrag_search", {"query": "transformer", "mode": "local"})
    exp_graphml = _call(server, "graphrag_export_subgraph", {"context": ctx, "format": "graphml"})
    assert exp_graphml["format"] == "graphml"
    assert "<graphml" in exp_graphml["content"]

    exp_cypher = _call(server, "graphrag_export_subgraph", {"context": ctx, "format": "cypher"})
    assert exp_cypher["format"] == "cypher"
    assert "MERGE" in exp_cypher["content"]


def test_new_batch_tool(server):
    batch_res = _call(
        server,
        "graphrag_batch",
        {
            "calls": [
                {"tool": "graphrag_count", "arguments": {"entity_type": "Paper"}},
                {"tool": "graphrag_similarity", "arguments": {"text_a": "deep learning", "text_b": "neural network"}},
            ]
        },
    )
    assert batch_res["total"] == 2
    assert batch_res["successful"] == 2


def test_new_watch_tool(server):
    watch_res = _call(server, "graphrag_watch", {"limit": 10})
    assert "events" in watch_res
    assert "subscriber_count" in watch_res


def test_new_capability_token_tool(server, monkeypatch):
    monkeypatch.setenv("GRAPHRAG_ADMIN_TOKEN", "admin_secret_token")
    tok_res = _call(
        server,
        "graphrag_capability_token",
        {"role": "analyst", "ttl_seconds": 1800, "admin_token": "admin_secret_token"},
    )
    assert "token" in tok_res
    assert tok_res["token"].startswith("cap_")


def test_new_pagination_cursor(server):
    from mcp_server.mcp_server import _CURSORS

    _CURSORS["cur_test"] = {"items": [{"id": f"p_{i}"} for i in range(120)], "offset": 0}
    page1 = _call(server, "graphrag_next_page", {"cursor": "cur_test", "page_size": 50})
    assert page1["page_size"] == 50
    assert page1["has_more"] is True
    assert page1["next_cursor"] == "cur_test"


def test_mcp_resources_and_prompts(server):
    resources = asyncio.run(server.list_resources())
    assert any(r.uri == "graphrag://schema" for r in resources)

    prompts = asyncio.run(server.list_prompts())
    prompt_names = {p.name for p in prompts}
    assert {"entity_analysis", "path_reasoning", "community_summary"} <= prompt_names


