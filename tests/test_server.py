"""Unit tests for the HTTP demo server (mcp_server/server.py).

Hermetic: the module-level adapter is swapped for the in-memory demo adapter
before requests run, so no live TigerGraph/LLM is touched. The suite asserts
honest behavior: real retrieval through the contracts layer, extraction-only
answers without an LLM, and null eval metrics until a real harness runs.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import mcp_server.server as srv
from mcp_server.adapters import DemoGraphRAGAdapter
from mcp_server.contracts.retrieval import RetrievalContract


@pytest.fixture()
def client(monkeypatch):
    """Hermetic TestClient with the demo adapter wired in."""
    adapter = DemoGraphRAGAdapter()
    monkeypatch.setattr(srv, "_ADAPTER", adapter)
    monkeypatch.setattr(srv, "_RETRIEVAL", RetrievalContract(adapter))
    monkeypatch.setattr(srv, "_LLM_AVAILABLE", False)
    return TestClient(srv.app)


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["backend"]
    assert "available" in body["llm"]


def test_query_runs_three_pipelines(client):
    body = client.post("/query", json={"query": "How does BERT relate to the Transformer?"}).json()
    for key in ("pipeline_1", "pipeline_2", "pipeline_3"):
        p = body[key]
        assert p["answer"]
        assert p["answer_source"] == "extraction_only"  # no LLM in hermetic test
        assert isinstance(p["tokens_total"], int) and p["tokens_total"] > 0
        assert p["latency_ms"] >= 0
        assert p["retrieval_method"] in {"none", "local_search", "global_search", "hybrid_search", "entity_lookup", "path_search", "neighborhood", "community_members"}
    # Honest labeling: no model name claimed for extraction-only answers.
    assert body["pipeline_1"]["model"] is None
    # Pipeline 2/3 retrieve real context and carry provenance.
    assert body["pipeline_2"]["provenance"]["backend"]
    assert body["pipeline_3"]["retrieval_method"] != "none"


def test_query_rejects_bad_mode(client):
    r = client.post("/query", json={"query": "x", "mode": "nonsense"})
    assert r.status_code == 422


def test_benchmark_results_null_eval(client):
    rows = client.get("/benchmark/results").json()
    assert rows
    for row in rows:
        assert row["query_id"]
        # Contract 9 honesty: no fabricated judge/bertscore numbers.
        assert row["evaluation"]["judge_pass"] is None
        assert row["evaluation"]["bertscore_f1"] is None


def test_schema_endpoint(client):
    schema = client.get("/schema").json()
    assert schema["graph_id"] == "demo_graph"
    assert "vertex_types" in schema and "edge_types" in schema


def test_graph_visualize(client):
    body = client.post("/graph/visualize", json={}).json()
    assert body["protocol"].startswith("graphrag/")
    assert body["results"]["entities"]
