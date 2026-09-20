"""Tests for the extended protocol contracts (4, 6, 7, 9, 10).

Hermetic by design: a fake adapter/connection replaces TigerGraph, so these
tests need no credentials and no network. Live-backend behavior is covered
separately by the ``integration``-marked tests.
"""

from __future__ import annotations

import asyncio

import pytest

from mcp_server.adapters.base import BaseGraphRAGAdapter
from mcp_server.contracts.construction import ConstructionContract, extract_concepts
from mcp_server.contracts.evaluation import EvaluationContract, content_terms
from mcp_server.contracts.federation import FederationContract
from mcp_server.contracts.streaming import StreamBus, publish_ingestion_report
from mcp_server.protocol import (
    GraphSchema,
    Provenance,
    RetrievalMetrics,
    SubgraphContext,
)
from mcp_server.protocol_extensions import (
    BackendRef,
    FederationConfig,
    IngestionConfig,
    IngestionReport,
    MergeStrategy,
    ResolveStrategy,
    StreamEventType,
)


def make_context(
    operation: str = "local_search",
    entities: list[dict] | None = None,
    relationships: list[dict] | None = None,
    *,
    hops: int = 1,
    latency_ms: float = 5.0,
    chunks: list[dict] | None = None,
    sources: list[str] | None = None,
) -> SubgraphContext:
    """Build a protocol-valid context for tests."""
    return SubgraphContext(
        protocol="graphrag/1.0",
        operation=operation,
        query={"text": "test query"},
        results={
            "entities": entities or [],
            "relationships": relationships or [],
            "paths": [],
            "communities": [],
            "text_chunks": chunks or [],
        },
        provenance=Provenance(
            source_documents=sources or [],
            traversal_log=[],
            total_entities_examined=len(entities or []),
            total_chunks_returned=len(chunks or []),
            backend="fake",
        ),
        metrics=RetrievalMetrics(
            input_tokens=10,
            entities_returned=len(entities or []),
            relationships_returned=len(relationships or []),
            graph_hops_traversed=hops,
            latency_ms=latency_ms,
        ),
    )


class FakeConn:
    """Records writes instead of hitting TigerGraph."""

    def __init__(self, counts: dict[str, int] | None = None, existing: set | None = None) -> None:
        self.counts = counts or {"Paper": 100, "Author": 50, "Concept": 25}
        self.existing = existing or set()
        self.vertex_upserts: list[tuple[str, str, dict | None]] = []
        self.edge_upserts: list[tuple] = []
        self.deleted: list[tuple[str, str]] = []
        self.gsql_calls: list[str] = []
        self.installed: dict[str, dict] = {}

    def upsertVertex(self, vtype, vid, attributes=None):
        self.vertex_upserts.append((vtype, vid, attributes))
        self.counts[vtype] = self.counts.get(vtype, 0) + 1
        return 1

    def upsertEdge(self, stype, sid, etype, ttype, tid, attributes=None, vertexMustExist=False):
        self.edge_upserts.append((stype, sid, etype, ttype, tid, attributes))
        return 1

    def getVertexCount(self, vtype="*", where="", realtime=False):
        return self.counts.get(vtype, 0)

    def getVerticesById(self, vtype, vids, select=""):
        wanted = vids if isinstance(vids, list) else [vids]
        return [{"v_id": v} for v in wanted if (vtype, v) in self.existing]

    def delVerticesById(self, vtype, vids, permanent=False, timeout=0):
        self.deleted.append((vtype, str(vids)))
        return 1

    def delEdges(self, vtype, vid, where="", limit="", timeout=0):
        return 2

    def getInstalledQueries(self, fmt="py"):
        return self.installed

    def gsql(self, query, graphname=None, **kwargs):
        self.gsql_calls.append(query)
        return "ok"


class FakeAdapter(BaseGraphRAGAdapter):
    """Minimal live-shaped adapter: configurable retrieval, optional conn."""

    def __init__(self, graphname: str = "fake_graph", entities: list[dict] | None = None, conn=None) -> None:
        self._graphname = graphname
        self._entities = entities or []
        self.conn = conn
        self.lookups: list[dict] = []

    def local_search(self, query, entity_hints=None, depth=2, top_k=10, filters=None):
        return make_context("local_search", self._entities[:top_k], hops=depth)

    def global_search(self, query, community_level=2, top_communities=10):
        return make_context("global_search", self._entities)

    def hybrid_search(self, query, vector_weight=0.5, graph_weight=0.5, top_k=10, depth=2):
        return make_context("hybrid_search", self._entities[:top_k], hops=depth)

    def entity_lookup(self, entity_id=None, entity_name=None, entity_type=None, depth=1):
        self.lookups.append({"entity_id": entity_id, "entity_name": entity_name, "entity_type": entity_type})
        return make_context("entity_lookup", self._entities)

    def path_search(self, source, target, max_hops=4):
        return make_context("path_search", self._entities)

    def neighborhood(self, entity_id, depth=2, edge_types=None):
        return make_context("neighborhood", self._entities, hops=depth)

    def community_members(self, community_id, include_summary=True):
        return make_context("community_members", self._entities)

    def get_schema(self, graph_id=None) -> GraphSchema:
        return GraphSchema(
            protocol="graphrag/1.0",
            graph_id=graph_id or self._graphname,
            entity_types=[],
            relationship_types=[],
            statistics={"total_vertices": 0, "total_edges": 0, "density": 0.0, "components": 0},
        )

    def get_provenance(self, context) -> Provenance:
        return context.provenance

    def health_check(self) -> dict:
        return {"status": "ok", "backend": "fake", "graph_id": self._graphname}


class FailingAdapter(FakeAdapter):
    """Adapter whose retrieval always raises (for fan-out isolation tests)."""

    def local_search(self, query, entity_hints=None, depth=2, top_k=10, filters=None):
        raise RuntimeError("backend down")


# ---------------------------------------------------------------------------
# Contract 4 — Construction
# ---------------------------------------------------------------------------


def test_extract_concepts_is_deterministic_and_filtered():
    first = extract_concepts("Graph Neural Networks", "graph neural networks learn representations", 3)
    second = extract_concepts("Graph Neural Networks", "graph neural networks learn representations", 3)
    assert first == second
    assert "graph" in first and "neural" in first
    assert all(len(c) >= 4 for c in first)
    assert "the" not in first


def test_extract_entities_builds_triples_per_author_and_concept():
    contract = ConstructionContract(FakeAdapter(conn=FakeConn()))
    triples = contract.extract_entities(
        {
            "id": "2609.05415",
            "title": "UniMate: unified skeleton animation",
            "abstract": "topology aware diffusion transformer",
            "authors": ["Linzhan Mou", "Jiahui Lei"],
            "references": ["2608.00001"],
        },
        IngestionConfig(graph_id="g", max_concepts_per_doc=2),
    )
    predicates = {t.predicate for t in triples}
    assert predicates == {"AUTHORED_BY", "MENTIONS", "CITES"}
    assert sum(1 for t in triples if t.predicate == "AUTHORED_BY") == 2
    assert sum(1 for t in triples if t.predicate == "MENTIONS") == 2
    assert all(t.subject_id == "2609.05415" for t in triples)


def test_construction_dry_run_writes_nothing():
    conn = FakeConn()
    contract = ConstructionContract(FakeAdapter(conn=conn))
    report = contract.ingest(
        [{"id": "p1", "title": "t", "abstract": "a", "authors": ["A"]}],
        IngestionConfig(graph_id="g", dry_run=True),
    )
    assert report.dry_run is True
    assert conn.vertex_upserts == [] and conn.edge_upserts == []
    assert report.documents_ingested == 1
    assert report.triples_extracted >= 1


def test_construction_ingest_writes_vertices_and_edges():
    conn = FakeConn()
    contract = ConstructionContract(FakeAdapter(conn=conn))
    report = contract.ingest(
        [{"id": "p1", "title": "Skeleton animation", "abstract": "diffusion transformer", "authors": ["A"]}],
        IngestionConfig(graph_id="g", max_concepts_per_doc=2),
    )
    assert report.documents_ingested == 1
    assert report.errors == []
    written_types = [u[0] for u in conn.vertex_upserts]
    assert written_types[0] == "Paper"
    assert "Author" in written_types
    assert report.edges_created == report.triples_extracted
    assert conn.edge_upserts[0][5] is None  # edges carry no attributes
    assert report.vertices_before and report.vertices_after
    assert report.vertices_after["Paper"] > report.vertices_before["Paper"]


def test_construction_requires_writable_backend():
    contract = ConstructionContract(FakeAdapter(conn=None))
    with pytest.raises(RuntimeError):
        contract.ingest([{"id": "p1", "title": "t", "abstract": "a"}])


def test_construction_delete_document_records_removal():
    conn = FakeConn(existing={("Paper", "p1")})
    contract = ConstructionContract(FakeAdapter(conn=conn))
    report = contract.delete_document("p1")
    assert conn.deleted == [("Paper", "p1")]
    assert report.documents_deleted == ["p1"]
    assert report.documents_ingested == 0  # nothing was ingested by a delete
    assert report.errors == []


def test_construction_delete_dry_run_deletes_nothing():
    conn = FakeConn(existing={("Paper", "p1")})
    contract = ConstructionContract(FakeAdapter(conn=conn))
    report = contract.delete_document("p1", IngestionConfig(graph_id="g", dry_run=True))
    assert conn.deleted == []  # proved: the backend was not touched
    assert report.dry_run is True
    assert report.documents_deleted == ["p1"]  # what WOULD be removed


def test_construction_counters_never_double_count_resolved_entities():
    """A resolved vertex is counted once, in ``entities_resolved`` only."""
    conn = FakeConn(existing={("Author", "Linzhan Mou")})
    contract = ConstructionContract(FakeAdapter(conn=conn))
    report = contract.ingest(
        [
            {
                "id": "p1",
                "title": "Skeleton animation",
                "abstract": "diffusion transformer",
                "authors": ["Linzhan Mou"],
            }
        ],
        IngestionConfig(graph_id="g", max_concepts_per_doc=1),
    )
    assert report.triples_extracted == 2  # 1 author + 1 concept
    assert report.entities_resolved == 1  # the pre-existing author
    assert report.entities_created == 2  # the Paper + the new concept only
    assert report.documents_written == ["p1"]
    assert report.documents_created == ["p1"]
    assert report.documents_skipped == 0
    assert report.edges_created == 2


def test_construction_ingest_dry_run_reports_would_be_created():
    conn = FakeConn(existing={("Paper", "p1"), ("Author", "A")})
    contract = ConstructionContract(FakeAdapter(conn=conn))
    report = contract.ingest(
        [{"id": "p1", "title": "Skeleton animation", "abstract": "diffusion transformer", "authors": ["A"]}],
        IngestionConfig(graph_id="g", dry_run=True, max_concepts_per_doc=1),
    )
    assert conn.vertex_upserts == [] and conn.edge_upserts == []
    assert report.documents_written == []  # nothing was written
    assert report.entities_resolved == 2  # Paper p1 + Author A exist
    assert report.entities_created == 1  # only the new concept would be created
    assert report.vertices_after == report.vertices_before


def test_construction_new_only_skips_existing_document_and_entities():
    conn = FakeConn(existing={("Paper", "p1"), ("Author", "A"), ("Concept", "animation")})
    contract = ConstructionContract(FakeAdapter(conn=conn))
    report = contract.ingest(
        [{"id": "p1", "title": "Skeleton animation", "abstract": "diffusion transformer", "authors": ["A"]}],
        IngestionConfig(graph_id="g", resolve=ResolveStrategy.NEW_ONLY, max_concepts_per_doc=1),
    )
    assert conn.vertex_upserts == [] and conn.edge_upserts == []  # insert-only: no writes
    assert report.documents_skipped == 1
    assert report.documents_written == [] and report.documents_created == []
    assert report.entities_created == 0
    assert report.entities_resolved == 3  # Paper + Author + Concept already existed


def test_construction_new_only_still_writes_genuinely_new_vertices():
    conn = FakeConn(existing={("Author", "A")})
    contract = ConstructionContract(FakeAdapter(conn=conn))
    report = contract.ingest(
        [{"id": "p1", "title": "Skeleton animation", "abstract": "diffusion transformer", "authors": ["A"]}],
        IngestionConfig(graph_id="g", resolve=ResolveStrategy.NEW_ONLY, max_concepts_per_doc=1),
    )
    written_ids = [vid for _, vid, _ in conn.vertex_upserts]
    assert "A" not in written_ids  # the existing author is never overwritten
    assert written_ids == ["p1", "animation"]
    assert report.entities_created == 2 and report.entities_resolved == 1
    assert report.documents_skipped == 0 and report.documents_written == ["p1"]


def test_construction_ingest_publishes_real_events():
    """Contract 4 emits Contract 7 events at the mutation point, exactly once."""
    bus = StreamBus()
    from mcp_server.contracts import streaming

    original = streaming.STREAM_BUS
    streaming.STREAM_BUS = bus
    try:
        conn = FakeConn(existing={("Author", "A")})
        contract = ConstructionContract(FakeAdapter(conn=conn))
        contract.ingest(
            [{"id": "p1", "title": "Skeleton animation", "abstract": "diffusion transformer", "authors": ["A"]}],
            IngestionConfig(graph_id="g", max_concepts_per_doc=1),
        )
        contract.ingest(
            [{"id": "p2", "title": "Skeleton animation", "abstract": "diffusion transformer", "authors": ["A"]}],
            IngestionConfig(graph_id="g", dry_run=True),  # dry runs publish nothing
        )
        published = list(bus.recent(20))
    finally:
        streaming.STREAM_BUS = original

    assert [e.event_type for e in published] == [
        StreamEventType.ENTITY_CREATED,
        StreamEventType.EDGE_CREATED,
        StreamEventType.INGESTION_COMPLETED,
    ]
    assert published[0].entity_id == "p1"
    assert published[-1].payload["documents_created"] == ["p1"]
    assert published[-1].payload["entities_resolved"] == 1


def test_construction_resolve_marks_existing_objects():
    conn = FakeConn(existing={("Author", "Linzhan Mou")})
    contract = ConstructionContract(FakeAdapter(conn=conn))
    triples = contract.extract_entities(
        {"id": "p1", "title": "t", "abstract": "a", "authors": ["Linzhan Mou"]},
        IngestionConfig(graph_id="g", max_concepts_per_doc=1),
    )
    resolved = contract.resolve_entities(triples, IngestionConfig(graph_id="g"))
    author = next(t for t in resolved if t.predicate == "AUTHORED_BY")
    assert author.properties["resolved"] is True


# ---------------------------------------------------------------------------
# Contract 6 — Federation
# ---------------------------------------------------------------------------


def _entities(*pairs: tuple[str, float]) -> list[dict]:
    return [
        {"id": pid, "type": "Paper", "name": f"Paper {pid}", "properties": {}, "relevance_score": score}
        for pid, score in pairs
    ]


def test_federation_rrf_merges_and_tags_backends():
    primary = FakeAdapter("g1", _entities(("p1", 0.9), ("p2", 0.5)))
    secondary = FakeAdapter("g2", _entities(("p1", 0.8), ("p3", 0.7)))
    contract = FederationContract(primary)
    contract.register_backend("secondary", secondary, weight=1.0)
    config = FederationConfig(
        backends=[BackendRef(name="primary", graph_id="g1"), BackendRef(name="secondary", graph_id="g2")],
        merge_strategy=MergeStrategy.RECIPROCAL_RANK_FUSION,
        top_k=5,
    )
    ctx = contract.federated_search("q", config=config, mode="local")
    assert ctx.operation == "federated_search"
    by_id = {e["id"]: e for e in ctx.results["entities"]}
    # p1 appears in both backends -> tagged twice and ranked first (1/61 + 1/62)
    assert by_id["p1"]["properties"]["backends"] == ["primary", "secondary"]
    assert ctx.results["entities"][0]["id"] == "p1"
    # p1 ranks first in BOTH backends: 1/(60+1) twice, rounded to 6 decimals.
    assert by_id["p1"]["relevance_score"] == pytest.approx(2 / 61, abs=1e-6)
    assert ctx.query["merge_strategy"] == "rrf"
    assert ctx.provenance.backend == "federation"


def test_federation_weighted_score_normalises_by_weight():
    primary = FakeAdapter("g1", _entities(("p1", 1.0)))
    secondary = FakeAdapter("g2", _entities(("p1", 0.0)))
    contract = FederationContract(primary)
    contract.register_backend("secondary", secondary, weight=1.0)
    config = FederationConfig(
        backends=[BackendRef(name="primary", graph_id="g1", weight=3.0), BackendRef(name="secondary", graph_id="g2", weight=1.0)],
        merge_strategy=MergeStrategy.WEIGHTED_SCORE,
    )
    ctx = contract.federated_search("q", config=config, mode="local")
    # (3*1.0 + 1*0.0) / 4 = 0.75
    assert ctx.results["entities"][0]["relevance_score"] == pytest.approx(0.75)


def test_federation_isolates_a_failing_backend():
    primary = FakeAdapter("g1", _entities(("p1", 0.9)))
    contract = FederationContract(primary)
    contract.register_backend("broken", FailingAdapter("g2"))
    config = FederationConfig(
        backends=[BackendRef(name="primary", graph_id="g1"), BackendRef(name="broken", graph_id="g2")],
    )
    ctx = contract.federated_search("q", config=config, mode="local")
    assert [e["id"] for e in ctx.results["entities"]] == ["p1"]
    assert any("broken" in err for err in ctx.query["errors"])


def test_federation_entity_link_scores_exact_match_higher():
    adapter = FakeAdapter(
        "g1",
        [
            {"id": "Linzhan Mou", "type": "Author", "name": "Linzhan Mou", "properties": {}, "relevance_score": 1.0},
            {"id": "Linzhan Mou Jr", "type": "Author", "name": "Linzhan Mou Jr", "properties": {}, "relevance_score": 1.0},
        ],
    )
    contract = FederationContract(adapter)
    links = contract.cross_graph_entity_link(
        "Linzhan Mou", config=FederationConfig(backends=[BackendRef(name="primary", graph_id="g1")])
    )
    assert [link.score for link in links] == [1.0, 0.6]
    assert adapter.lookups[0]["entity_name"] == "Linzhan Mou"


# ---------------------------------------------------------------------------
# Contract 7 — Streaming
# ---------------------------------------------------------------------------


def test_stream_bus_delivers_to_subscribers_with_filters():
    async def scenario():
        bus = StreamBus()
        received: list[str] = []

        async def consume():
            async for event in bus.subscribe(event_types=[StreamEventType.ENTITY_CREATED]):
                received.append(event.event_id)

        task = asyncio.create_task(consume())
        await asyncio.sleep(0)
        assert bus.subscriber_count == 1
        bus.emit(StreamEventType.EDGE_CREATED, "g")
        bus.emit(StreamEventType.ENTITY_CREATED, "g", entity_id="p1")
        await asyncio.sleep(0.05)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        return received

    assert asyncio.run(scenario()) == ["evt-2"]


def test_stream_bus_replays_history_and_unsubscribes():
    async def scenario():
        bus = StreamBus()
        bus.emit(StreamEventType.INGESTION_COMPLETED, "g")
        bus.emit(StreamEventType.COMMUNITY_RECOMPUTED, "g")
        seen: list[str] = []
        subscription = bus.subscribe(replay=True)
        async for event in subscription:
            seen.append(event.event_type.value)
            if len(seen) == 2:
                break
        # Closing the generator runs its cleanup, which unsubscribes.
        await subscription.aclose()
        return seen, bus.subscriber_count

    seen, subscribers = asyncio.run(scenario())
    assert seen == ["ingestion_completed", "community_recomputed"]
    assert subscribers == 0


def test_publish_ingestion_report_emits_measured_events():
    bus = StreamBus()
    from mcp_server.contracts import streaming

    original = streaming.STREAM_BUS
    streaming.STREAM_BUS = bus
    try:
        report = IngestionReport(
            graph_id="g",
            document_ids=["p1", "p2"],
            documents_written=["p1", "p2"],
            documents_created=["p2"],
            documents_ingested=2,
            edges_created=7,
            duration_ms=3.5,
        )
        events = publish_ingestion_report(report)
        dry = publish_ingestion_report(IngestionReport(graph_id="g", document_ids=["x"], dry_run=True))
    finally:
        streaming.STREAM_BUS = original

    # p1 already existed -> updated; p2 is new -> created; edges then completion.
    assert [e.event_type for e in events] == [
        StreamEventType.ENTITY_UPDATED,
        StreamEventType.ENTITY_CREATED,
        StreamEventType.EDGE_CREATED,
        StreamEventType.INGESTION_COMPLETED,
    ]
    assert events[0].entity_id == "p1" and events[1].entity_id == "p2"
    assert events[2].payload["edges_created"] == 7
    assert events[-1].payload["edges_created"] == 7
    assert dry == []


def test_publish_ingestion_report_emits_delete_event():
    bus = StreamBus()
    from mcp_server.contracts import streaming

    original = streaming.STREAM_BUS
    streaming.STREAM_BUS = bus
    try:
        events = publish_ingestion_report(
            IngestionReport(graph_id="g", documents_deleted=["p1"], documents_ingested=0)
        )
    finally:
        streaming.STREAM_BUS = original

    assert [e.event_type for e in events] == [
        StreamEventType.ENTITY_DELETED,
        StreamEventType.INGESTION_COMPLETED,
    ]
    assert events[0].entity_id == "p1"
    assert events[-1].payload["documents_deleted"] == ["p1"]


# ---------------------------------------------------------------------------
# Contract 9 — Evaluation
# ---------------------------------------------------------------------------


def test_content_terms_filters_stopwords_and_short_tokens():
    assert content_terms("The transformation of graph attention") == {"transformation", "graph", "attention"}
    assert content_terms("") == set()


def test_evaluate_retrieval_measures_precision_and_recall():
    contract = EvaluationContract(FakeAdapter())
    ctx = make_context(
        "hybrid_search",
        entities=[
            {"id": "2609.05415", "type": "Paper", "name": "UniMate skeleton animation", "properties": {}, "relevance_score": 0.9},
            {"id": "2608.00001", "type": "Paper", "name": "Unrelated topic", "properties": {}, "relevance_score": 0.4},
        ],
    )
    evaluation = contract.evaluate_retrieval(
        "q001", ctx, "UniMate animates skeletons authored by Linzhan Mou", k=2
    )
    assert evaluation.precision_at_k == pytest.approx(0.5)  # 1 of 2 ranked entities matched
    assert 0 < evaluation.recall_at_k <= 1
    assert evaluation.entities_retrieved == 2
    assert evaluation.latency_ms == 5.0


def test_evaluate_answer_judge_is_null_without_llm(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    contract = EvaluationContract(FakeAdapter())
    verdict = contract.evaluate_answer("q1", "q", "UniMate animates skeletons", "UniMate animates skeletons", None)
    assert verdict.judge_pass is None
    assert "no LLM configured" in (verdict.judge_reason or "")
    assert verdict.judge_model is None


def test_evaluate_answer_grounding_detects_supported_and_unsupported():
    contract = EvaluationContract(FakeAdapter())
    ctx = make_context(
        chunks=[{"id": "c1", "text": "UniMate animates diverse skeletons with topology aware diffusion", "source_doc": "p", "metadata": {}}]
    )
    grounded = contract.evaluate_answer("q1", "q", "UniMate animates diverse skeletons", "r", ctx)
    ungrounded = contract.evaluate_answer("q1", "q", "Quantum chromodynamics lattice gauge theory", "r", ctx)
    assert grounded.faithfulness == "grounded"
    assert ungrounded.faithfulness == "ungrounded"


def test_evaluate_report_aggregates_and_notes_missing_extras(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    contract = EvaluationContract(FakeAdapter("g", _entities(("p1", 0.9))))
    monkeypatch.setattr(contract, "_bertscore", staticmethod(lambda a, r: None))
    report = contract.evaluate_report(
        [{"id": "q1", "query": "skeleton animation", "reference": "UniMate animates skeletons"}],
        pipeline="graphrag",
    )
    assert report.num_queries == 1
    assert len(report.retrieval) == 1 and len(report.answers) == 1
    assert report.judge_pass_rate is None
    assert report.avg_bertscore_f1 is None
    assert report.avg_recall_at_k is not None
    assert any("No LLM configured" in note for note in report.notes)
