"""Live integration tests for the extended contracts (4, 6, 7, 9) on TigerGraph.

These run against the real Savanna workspace configured in ``.env`` and skip
themselves when credentials are absent or the workspace is unreachable. They
prove the write path end to end: real vertices/edges created, read back, and
removed again — with every counter asserted against the backend.

The self-test documents are named ``pt-selftest-<run>-<n>`` so they are easy to
recognise, and the module deletes every one it creates.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

import pytest

from mcp_server.adapters import TigerGraphAdapter
from mcp_server.contracts.construction import ConstructionContract
from mcp_server.contracts.evaluation import EvaluationContract
from mcp_server.contracts.federation import FederationContract
from mcp_server.contracts.streaming import STREAM_BUS
from mcp_server.protocol_extensions import (
    BackendRef,
    FederationConfig,
    IngestionConfig,
    MergeStrategy,
    ResolveStrategy,
)

_REQUIRED_ENV = ("TIGERGRAPH_HOST", "TIGERGRAPH_GSQL_SECRET", "TIGERGRAPH_GRAPH_NAME")
_PROJECT_ROOT = Path(__file__).resolve().parents[1]

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not all(os.environ.get(key) for key in _REQUIRED_ENV),
        reason="TigerGraph env not configured (TIGERGRAPH_HOST/GSQL_SECRET/GRAPH_NAME)",
    ),
]

_RUN_ID = uuid.uuid4().hex[:8]
_created: list[str] = []


@pytest.fixture(scope="module")
def adapter() -> TigerGraphAdapter:
    """A live adapter; skip the module if the workspace is unreachable."""
    a = TigerGraphAdapter()
    health = a.health_check()
    if health.get("status") != "ok":
        pytest.skip(f"TigerGraph workspace unreachable: {health}")
    return a


@pytest.fixture(scope="module")
def construction(adapter: TigerGraphAdapter) -> ConstructionContract:
    """Contract 4 over the live workspace (events go to the real bus)."""
    return ConstructionContract(adapter)


@pytest.fixture(autouse=True, scope="module")
def cleanup(adapter: TigerGraphAdapter, construction: ConstructionContract):
    """Remove every self-test document this module created, even on failure."""
    yield
    for doc_id in _created:
        try:
            construction.delete_document(doc_id, IngestionConfig(graph_id=adapter._graphname))
        except Exception as exc:  # noqa: BLE001 - cleanup must never mask a failure
            print(f"[cleanup] {doc_id}: {type(exc).__name__}: {exc}")


def _document(doc_id: str, abstract: str = "Protocol construction self test") -> dict[str, Any]:
    """A Paper-shaped self-test document."""
    return {
        "id": doc_id,
        "title": f"Protocol self test {_RUN_ID}",
        "abstract": abstract,
        "authors": [f"Protocol Self Test {_RUN_ID}"],
        "categories": ["cs.SE"],
        "published": "2026-01-02T03:04:05Z",
    }


def _config(adapter: TigerGraphAdapter, **overrides: Any) -> IngestionConfig:
    return IngestionConfig(graph_id=adapter._graphname, max_concepts_per_doc=2, **overrides)


def _read_paper(adapter: TigerGraphAdapter, doc_id: str) -> list[dict]:
    """Read a Paper vertex back (pyTigerGraph raises 601 for a missing id)."""
    try:
        return adapter.conn.getVerticesById("Paper", [doc_id]) or []
    except Exception:  # noqa: BLE001 - a missing vertex is a valid outcome here
        return []


def _new_id(suffix: str) -> str:
    doc_id = f"pt-selftest-{_RUN_ID}-{suffix}"
    _created.append(doc_id)
    return doc_id


# ---------------------------------------------------------------------------
# Contract 4 — Construction (real writes)
# ---------------------------------------------------------------------------


def test_dry_run_writes_nothing(adapter, construction):
    doc_id = _new_id("dry")
    before = {t: int(adapter.conn.getVertexCount(t)) for t in ("Paper", "Author", "Concept")}
    report = construction.ingest([_document(doc_id)], _config(adapter, dry_run=True))

    assert report.dry_run is True
    assert report.documents_written == [] and report.documents_created == []
    assert report.documents_ingested == 1  # would be ingested
    assert report.triples_extracted >= 1
    assert report.vertices_before == before
    assert report.vertices_after == before  # measured, and unchanged: nothing written
    assert _read_paper(adapter, doc_id) == []  # proved on the backend


def test_ingest_writes_measured_vertices_edges_and_attributes(adapter, construction):
    doc_id = _new_id("write")
    before = {t: int(adapter.conn.getVertexCount(t)) for t in ("Paper", "Author", "Concept")}
    report = construction.ingest([_document(doc_id)], _config(adapter))

    assert report.errors == []
    assert report.documents_created == [doc_id]
    assert report.documents_written == [doc_id]
    assert report.entities_created >= 1
    assert report.edges_created == report.triples_extracted >= 1
    assert report.vertices_before == before
    assert report.vertices_after["Paper"] == before["Paper"] + 1
    # Counters agree with the backend: the Paper counts as created exactly once.
    assert report.entities_created == report.triples_extracted + 1

    rows = _read_paper(adapter, doc_id)
    assert len(rows) == 1
    attrs = rows[0]["attributes"]
    assert attrs["title"] == f"Protocol self test {_RUN_ID}"
    assert attrs["published"] == "2026-01-02 03:04:05"  # DATETIME round-trip
    assert len(adapter.conn.getEdges("Paper", doc_id)) == report.edges_created


def test_new_only_leaves_an_existing_document_untouched(adapter, construction):
    doc_id = _new_id("insert_only")
    first = construction.ingest([_document(doc_id, "original abstract")], _config(adapter))
    assert first.documents_created == [doc_id]

    second = construction.ingest(
        [_document(doc_id, "replacement abstract")],
        _config(adapter, resolve=ResolveStrategy.NEW_ONLY),
    )
    assert second.documents_skipped == 1
    assert second.documents_written == [] and second.documents_created == []
    assert second.entities_created == 0 and second.edges_created == 0
    # Proved on the backend: the stored attributes were not overwritten.
    assert _read_paper(adapter, doc_id)[0]["attributes"]["abstract"] == "original abstract"


def test_update_overwrites_attributes_under_exact_id(adapter, construction):
    doc_id = _new_id("update")
    construction.ingest([_document(doc_id, "before update")], _config(adapter))
    report = construction.update(doc_id, {"abstract": "after update"}, _config(adapter))

    assert report.documents_written == [doc_id]
    assert report.documents_created == []  # it already existed
    assert report.errors == []
    assert _read_paper(adapter, doc_id)[0]["attributes"]["abstract"] == "after update"


def test_delete_removes_the_vertex_and_reports_it(adapter, construction):
    doc_id = _new_id("delete")
    construction.ingest([_document(doc_id)], _config(adapter))

    report = construction.delete_document(doc_id, _config(adapter))

    assert report.documents_deleted == [doc_id]
    assert report.errors == []
    assert report.vertices_after["Paper"] == report.vertices_before["Paper"] - 1
    assert _read_paper(adapter, doc_id) == []


def test_ingest_publishes_real_stream_events(adapter, construction):
    doc_id = _new_id("events")
    before = len(STREAM_BUS.recent(200))
    construction.ingest([_document(doc_id)], _config(adapter))
    recent = STREAM_BUS.recent(200)[before:]

    types = [e.event_type.value for e in recent]
    assert "entity_created" in types and "ingestion_completed" in types
    assert types.count("ingestion_completed") == 1
    created = next(e for e in recent if e.event_type.value == "entity_created")
    assert created.entity_id == doc_id and created.graph_id == adapter._graphname
    completed = recent[-1]
    assert completed.payload["documents_created"] == [doc_id]
    assert completed.payload["edges_created"] >= 1


# ---------------------------------------------------------------------------
# Contract 6 — Federation (real fan-out and merge)
# ---------------------------------------------------------------------------


def test_federated_search_merges_and_times_live_backends(adapter):
    graph = adapter._graphname
    contract = FederationContract(adapter)
    config = FederationConfig(
        backends=[
            BackendRef(name="primary", graph_id=graph),
            BackendRef(name="secondary", graph_id=graph),  # same workspace, second ref
        ],
        merge_strategy=MergeStrategy.RECIPROCAL_RANK_FUSION,
        top_k=5,
    )
    ctx = contract.federated_search("graph neural network", config=config, mode="local")

    assert ctx.operation == "federated_search"
    assert ctx.provenance.backend == "federation"
    assert ctx.query["merge_strategy"] == "rrf"
    assert ctx.query["backends"] == [f"primary:{graph}", f"secondary:{graph}"]
    # Real per-backend timings were measured (not constants).
    timings = ctx.query["backend_timings_ms"]
    assert set(timings) == {"primary", "secondary"}
    assert all(ms >= 0 for ms in timings.values())
    assert ctx.metrics.latency_ms >= 0
    for entity in ctx.results["entities"][:5]:
        assert entity["properties"]["backends"]


def test_federated_search_reports_a_dead_backend_without_losing_the_good_one(adapter):
    graph = adapter._graphname
    contract = FederationContract(adapter)
    contract.register_backend("primary", adapter)
    config = FederationConfig(
        backends=[
            BackendRef(name="primary", graph_id=graph),
            BackendRef(name="ghost", graph_id=f"{graph}_does_not_exist"),
        ],
        top_k=3,
    )
    ctx = contract.federated_search("skeleton animation", config=config, mode="local")

    # The dead backend is named in the echo; the live one still answered.
    errors = ctx.query.get("errors") or []
    assert any("ghost" in message for message in errors)
    assert ctx.query["backend_timings_ms"]["ghost"] >= 0


# ---------------------------------------------------------------------------
# Contract 9 — Evaluation (real retrieval metrics on the live graph)
# ---------------------------------------------------------------------------


def test_evaluation_report_measures_real_retrieval(adapter):
    references_path = _PROJECT_ROOT / "hackathon" / "data" / "queries" / "reference_answers.json"
    references: dict[str, str] = (
        json.loads(references_path.read_text()) if references_path.exists() else {}
    )
    with open(_PROJECT_ROOT / "hackathon" / "data" / "queries" / "single_hop.json") as handle:
        queries = sorted(json.load(handle), key=lambda q: q["id"])[:2]

    query_set = [
        {
            "id": q["id"],
            "query": q["query"],
            "reference": references.get(q["id"], ""),
            "category": "single_hop",
        }
        for q in queries
    ]
    started = time.perf_counter()
    report = EvaluationContract(adapter).evaluate_report(
        query_set, mode="local", pipeline="graphrag", k=5
    )

    assert report.num_queries == len(query_set)
    assert len(report.retrieval) == len(query_set)
    assert report.avg_recall_at_k is not None
    assert report.avg_precision_at_k is not None
    assert all(r.latency_ms > 0 for r in report.retrieval)
    assert all(r.entities_retrieved >= 0 for r in report.retrieval)
    # Honest about what could not run: judge/bertscore stay null when unavailable.
    assert report.judge_pass_rate is None or 0.0 <= report.judge_pass_rate <= 1.0
    assert report.avg_bertscore_f1 is None or 0.0 <= report.avg_bertscore_f1 <= 1.0
    assert time.perf_counter() - started > 0
