"""Unit tests for the HTTP demo server (mcp_server/server.py).

Hermetic: module-level adapters are swapped for the in-memory demo adapter and
the LLM is forced off before requests run, so no live TigerGraph/Gemini call is
made. The suite asserts honest behavior: real retrieval through the contracts
layer, extraction-only answers without an LLM, write endpoints failing closed
without the admin token, and null eval metrics until a real judge runs.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

import mcp_server.server as srv
from mcp_server import pipelines
from mcp_server.adapters import DemoGraphRAGAdapter
from mcp_server.contracts.authorization import AuthorizationContract
from mcp_server.contracts.construction import ConstructionContract
from mcp_server.contracts.evaluation import EvaluationContract
from mcp_server.contracts.federation import FederationContract
from mcp_server.contracts.retrieval import RetrievalContract


@pytest.fixture()
def client(monkeypatch):
    """Hermetic TestClient with the demo adapter wired in and no LLM."""
    adapter = DemoGraphRAGAdapter()
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(pipelines, "_LLM_CLIENT", None)
    monkeypatch.setattr(pipelines, "_LLM_STATE", False)
    monkeypatch.setattr(srv, "_ADAPTER", adapter)
    monkeypatch.setattr(srv, "_RETRIEVAL", RetrievalContract(adapter))
    monkeypatch.setattr(srv, "_EVALUATION", EvaluationContract(adapter))
    monkeypatch.setattr(srv, "_FEDERATION", FederationContract(adapter))
    monkeypatch.setattr(srv, "_CONSTRUCTION", ConstructionContract(adapter))
    return TestClient(srv.app)


@pytest.fixture()
def admin_client(monkeypatch):
    """TestClient with an admin token configured (Contract 10)."""
    adapter = DemoGraphRAGAdapter()
    monkeypatch.setenv("GRAPHRAG_ADMIN_TOKEN", "test-admin-token")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(pipelines, "_LLM_CLIENT", None)
    monkeypatch.setattr(pipelines, "_LLM_STATE", False)
    monkeypatch.setattr(srv, "_ADAPTER", adapter)
    monkeypatch.setattr(srv, "_RETRIEVAL", RetrievalContract(adapter))
    monkeypatch.setattr(srv, "_EVALUATION", EvaluationContract(adapter))
    monkeypatch.setattr(srv, "_FEDERATION", FederationContract(adapter))
    monkeypatch.setattr(srv, "_CONSTRUCTION", ConstructionContract(adapter))
    monkeypatch.setattr(srv, "_AUTH", AuthorizationContract(admin_token="test-admin-token"))
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


# ---------------------------------------------------------------------------
# Contract 6 — federation endpoints
# ---------------------------------------------------------------------------


def test_federated_search_returns_protocol_context(client):
    body = client.post("/federated/search", json={"query": "transformer", "merge_strategy": "rrf"}).json()
    assert body["operation"] == "federated_search"
    assert body["query"]["merge_strategy"] == "rrf"
    assert "entities" in body["results"]


def test_federated_search_rejects_unknown_strategy(client):
    r = client.post("/federated/search", json={"query": "x", "merge_strategy": "magic"})
    assert r.status_code == 422


def test_entity_link_returns_candidates(client):
    body = client.post("/graph/entity-link", json={"entity_name": "Transformer"}).json()
    assert isinstance(body, list)


# ---------------------------------------------------------------------------
# Contract 10 — authorization
# ---------------------------------------------------------------------------


def test_auth_operations_anonymous_role(client):
    body = client.get("/auth/operations").json()
    assert body["role"] == "anonymous"
    assert "local_search" in body["allowed_operations"]
    assert "ingest" not in body["allowed_operations"]


def test_auth_operations_admin_role(admin_client):
    body = admin_client.get("/auth/operations", headers={"X-Admin-Token": "test-admin-token"}).json()
    assert body["role"] == "admin"
    assert "ingest" in body["allowed_operations"]


def test_ingest_denied_without_admin_token(client):
    r = client.post("/ingest", json={"documents": [{"id": "p1", "title": "t", "abstract": "a"}]})
    assert r.status_code == 403
    assert "requires" in r.json()["detail"]


def test_ingest_conflicts_when_adapter_is_read_only(admin_client):
    """The demo adapter is read-only: Contract 4 reports it instead of pretending."""
    r = admin_client.post(
        "/ingest",
        json={"documents": [{"id": "p1", "title": "t", "abstract": "a"}]},
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert r.status_code == 409
    assert "TigerGraph" in r.json()["detail"]


def test_delete_document_denied_without_admin_token(client):
    r = client.delete("/documents/2609.05415")
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Contract 7 — streaming
# ---------------------------------------------------------------------------


def test_stream_events_is_sse_and_reports_known_types(client):
    """The route exists and serves real SSE framing (no blocking read)."""
    paths = {getattr(route, "path", None) for route in srv.app.routes}
    assert "/stream/events" in paths

    async def first_event():
        from mcp_server.contracts.streaming import STREAM_BUS
        from mcp_server.protocol_extensions import StreamEventType

        STREAM_BUS.emit(StreamEventType.INGESTION_COMPLETED, "test_graph")
        response = await srv.stream_events(event_types="ingestion_completed", replay=True)
        iterator = response.body_iterator
        try:
            chunk = await asyncio.wait_for(iterator.__anext__(), timeout=5)
        finally:
            await iterator.aclose()
        return response.media_type, chunk

    media_type, chunk = asyncio.run(first_event())
    assert media_type == "text/event-stream"
    assert chunk.startswith("data: ")
    payload = json.loads(chunk[len("data: ") :].strip())
    assert payload["event_type"] == "ingestion_completed"
    assert payload["protocol"].startswith("graphrag/")


def test_stream_events_rejects_unknown_type(client):
    r = client.get("/stream/events", params={"event_types": "not_a_real_event"})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Contract 9 — evaluation
# ---------------------------------------------------------------------------


def test_evaluation_report_is_honest_without_llm(client):
    body = client.get("/evaluation/report", params={"limit": 1}).json()
    assert body["num_queries"] == 1
    # No LLM -> no fabricated judge verdicts or BERTScore.
    assert body["judge_pass_rate"] is None
    assert body["avg_bertscore_f1"] is None
    assert body["retrieval"] and body["answers"]
    assert any("No LLM configured" in note for note in body["notes"])
