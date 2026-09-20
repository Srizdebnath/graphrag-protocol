#!/usr/bin/env python3
"""Live Contract 4 smoke test: real ingest into the configured TigerGraph graph.

Creates a clearly-marked self-test document, verifies the measured counters and
that the vertex is really readable, then deletes it again.

Usage:
    .venv/bin/python scripts/smoke_construction.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

from mcp_server.adapters import TigerGraphAdapter
from mcp_server.contracts.construction import ConstructionContract
from mcp_server.contracts.streaming import STREAM_BUS
from mcp_server.protocol_extensions import ExtractionStrategy, IngestionConfig


def read_paper(conn, doc_id: str) -> list:
    """Read a Paper vertex back; pyTigerGraph raises 601 for a missing id."""
    try:
        return conn.getVerticesById("Paper", [doc_id]) or []
    except Exception as exc:  # noqa: BLE001 - used as an existence probe
        print(f"    (read-back: {getattr(exc, 'args', [exc])[0]})")
        return []


def main() -> int:
    doc_id = f"protocol-selftest-{int(time.time())}"
    adapter = TigerGraphAdapter()
    health = adapter.health_check()
    print(f"[health] {health}")
    if health.get("status") != "ok":
        print("[skip] backend not healthy")
        return 1

    contract = ConstructionContract(adapter)
    config = IngestionConfig(
        graph_id=adapter._graphname,
        extraction=ExtractionStrategy.FREQUENCY,
        max_concepts_per_doc=3,
    )
    document = {
        "id": doc_id,
        "title": "Protocol construction contract self test",
        "abstract": (
            "This self-test document verifies real ingestion counters, vertex "
            "creation and edge creation through the construction contract."
        ),
        "authors": ["Protocol Self Test"],
        "categories": ["cs.SE"],
        "published": "2026-01-01T00:00:00Z",
    }

    print("\n[1] extract_entities")
    triples = contract.extract_entities(document, config)
    for t in triples:
        print(f"    {t.subject_id} -[{t.predicate}]-> {t.object_type}:{t.object_id}")

    print("\n[2] dry_run ingest (must not write)")
    dry = contract.ingest([document], config.model_copy(update={"dry_run": True}))
    print(f"    dry_run={dry.dry_run} documents_ingested={dry.documents_ingested} "
          f"vertices_before={dry.vertices_before} vertices_after={dry.vertices_after}")
    if dry.vertices_after != dry.vertices_before:
        print("[FAIL] dry run must not change the graph")
        return 1
    if read_paper(adapter.conn, doc_id):
        print("[FAIL] dry run created a vertex")
        return 1

    print("\n[3] real ingest")
    report = contract.ingest([document], config)
    print(f"    documents_ingested={report.documents_ingested} triples={report.triples_extracted} "
          f"created={report.entities_created} resolved={report.entities_resolved} "
          f"edges={report.edges_created} duration_ms={report.duration_ms}")
    print(f"    vertices_before={report.vertices_before}")
    print(f"    vertices_after ={report.vertices_after}")
    print(f"    errors={report.errors}")

    print("\n[4] verify the vertex is really readable")
    found = read_paper(adapter.conn, doc_id)
    print(f"    getVerticesById -> {len(found)} row(s)")
    for row in found:
        print(f"    attributes={row.get('attributes', {})}")

    print("\n[5] edge read-back")
    edges = adapter.conn.getEdges("Paper", doc_id)
    print(f"    outgoing edges={len(edges)}")

    print("\n[6] stream events published by the bus")
    print(f"    recent={[e.event_type.value for e in STREAM_BUS.recent(10)]}")

    print("\n[7] delete the self-test document")
    deleted = contract.delete_document(doc_id)
    remaining = read_paper(adapter.conn, doc_id)
    print(f"    documents_ingested={deleted.documents_ingested} errors={deleted.errors} "
          f"remaining_rows={len(remaining)}")

    ok = (
        report.documents_ingested == 1
        and report.edges_created > 0
        and bool(found)
        and not report.errors
        and not remaining
    )
    print(f"\n[result] {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
