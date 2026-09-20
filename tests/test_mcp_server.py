"""MCP server tests — in-memory, real tools, demo adapter, zero network.

Verifies the MCP layer itself: tool registration (all 16 protocol tools),
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


def test_registers_all_27_protocol_tools(server):
    tools = asyncio.run(server.list_tools())
    names = {t.name for t in tools}
    assert len(names) == 27
    expected = {
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
