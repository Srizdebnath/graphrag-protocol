"""GraphRAG Protocol — HTTP demo/dashboard server (FastAPI).

This is the **demo/dashboard** server, not the MCP server (that is
``mcp_server.mcp_server`` / the ``graphrag-mcp`` entrypoint).

Everything it returns is real:
- Retrieval and answers come from the shared pipeline runner
  (:mod:`mcp_server.pipelines`), which the evaluation harness also uses, so the
dashboard and ``hackathon/scripts/evaluate.py`` agree by construction.
- ``/benchmark/results`` scores answers with the real LLM-as-judge when a key
  is configured (``null`` + a reason when it is not).
- ``/ingest`` and document deletion go through Contract 4 (real TigerGraph
  upserts) and publish Contract 7 stream events.
- ``/stream/events`` is a real SSE feed over that event bus.
- ``/federated/search`` fans out via Contract 6.
- Write endpoints require the admin token (Contract 10) and fail closed.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from mcp_server.adapters import DemoGraphRAGAdapter, TigerGraphAdapter
from mcp_server.contracts.authorization import AuthorizationContract
from mcp_server.contracts.construction import ConstructionContract
from mcp_server.contracts.evaluation import EvaluationContract
from mcp_server.contracts.federation import FederationContract
from mcp_server.contracts.retrieval import RetrievalContract
from mcp_server.contracts.streaming import STREAM_BUS
from mcp_server.formatters import MarkdownFormatter
from mcp_server.pipelines import llm_client, llm_model, run_pipelines
from mcp_server.protocol import SubgraphContext
from mcp_server.protocol_extensions import (
    BackendRef,
    FederationConfig,
    IngestionConfig,
    MergeStrategy,
    StreamEventType,
)

load_dotenv()

_QUERY_FILE = Path("hackathon/data/queries/single_hop.json")
_REFERENCE_FILE = Path("hackathon/data/queries/reference_answers.json")


def _adapter() -> Any:
    """TigerGraph when configured and healthy; demo adapter otherwise."""
    try:
        adapter = TigerGraphAdapter()
        if adapter.health_check().get("status") == "ok":
            return adapter
        print("[server] TigerGraph unhealthy; using demo adapter")
    except Exception as exc:  # noqa: BLE001 - degrade to demo, never crash
        print(f"[server] TigerGraph unavailable ({type(exc).__name__}); using demo adapter")
    return DemoGraphRAGAdapter()


_ADAPTER = _adapter()
_RETRIEVAL = RetrievalContract(_ADAPTER)
_FORMATTER = MarkdownFormatter()
_EVALUATION = EvaluationContract(_ADAPTER)
_CONSTRUCTION = ConstructionContract(_ADAPTER)
_FEDERATION = FederationContract(_ADAPTER)
_AUTH = AuthorizationContract()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    mode: str = Field(default="auto", pattern="^(auto|local|global|hybrid|entity)$")


class GraphRequest(BaseModel):
    entity_id: str | None = Field(default=None, max_length=200)


class IngestRequest(BaseModel):
    documents: list[dict[str, Any]] = Field(..., min_length=1, max_length=50)
    dry_run: bool = False
    extraction: str = Field(default="frequency", pattern="^(frequency|llm)$")
    max_concepts_per_doc: int = Field(default=5, ge=1, le=50)


class FederatedRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    mode: str = Field(default="auto", pattern="^(auto|local|global|hybrid|entity)$")
    top_k: int = Field(default=10, ge=1, le=50)
    merge_strategy: str = Field(default="rrf", pattern="^(rrf|weighted_score)$")


class EntityLinkRequest(BaseModel):
    entity_name: str = Field(..., min_length=1, max_length=200)
    entity_type: str | None = Field(default=None, max_length=50)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_admin(operation: str, token: str | None) -> None:
    """Enforce Contract 10 for write operations; raises HTTP 403 when denied."""
    try:
        _AUTH.require(operation, token=token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


def _federation_config(backends: list[BackendRef] | None = None, **kwargs: Any) -> FederationConfig:
    """Build a federation config whose default backend is the active graph."""
    graph = getattr(_ADAPTER, "_graphname", None)
    return FederationConfig(
        backends=backends or ([BackendRef(name="primary", graph_id=graph)] if graph else []),
        **kwargs,
    )


def _dashboard_rows(query_set: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    """Run the 3-pipeline comparison with a real judge per answer."""
    rows: list[dict[str, Any]] = []
    for item in query_set:
        pipelines = run_pipelines(_RETRIEVAL, _FORMATTER, item["query"], mode=mode)
        verdict = _EVALUATION.evaluate_answer(
            query_id=item["id"],
            query=item["query"],
            answer=pipelines["pipeline_3"]["answer"],
            reference=item["reference"],
            context=None,
        )
        rows.append(
            {
                "query_id": item["id"],
                "query": item["query"],
                "category": item["category"],
                **pipelines,
                "evaluation": {
                    "judge_pass": verdict.judge_pass,
                    "judge_reason": verdict.judge_reason,
                    "bertscore_f1": verdict.bertscore_f1,
                },
            }
        )
    return rows


def _load_benchmark_queries(limit: int = 3) -> list[dict[str, Any]]:
    """Queries plus gold references for the dashboard benchmark.

    The query file is required (there is no sample fallback): a benchmark that
    silently ran on invented queries would misreport the system.

    Raises:
        HTTPException: 503 when the committed query file cannot be read.
    """
    references: dict[str, str] = {}
    try:
        references = json.loads(_REFERENCE_FILE.read_text())
    except Exception as exc:  # noqa: BLE001 - references are optional
        print(f"[server] references unavailable ({type(exc).__name__}); judge runs without gold text")
    try:
        items = [
            {"id": q["id"], "category": q.get("category", "single_hop"), "query": q["query"]}
            for q in json.loads(_QUERY_FILE.read_text())
        ]
    except Exception as exc:  # fail loudly, never invent queries
        raise HTTPException(
            status_code=503,
            detail=f"benchmark query file unusable ({type(exc).__name__}): {_QUERY_FILE}",
        ) from exc
    if not items:
        raise HTTPException(status_code=503, detail=f"benchmark query file is empty: {_QUERY_FILE}")
    items.sort(key=lambda q: q["id"])
    items = items[:limit]
    for item in items:
        item["reference"] = references.get(item["id"], "")
    return items


# ---------------------------------------------------------------------------
# App + endpoints
# ---------------------------------------------------------------------------

app = FastAPI(title="GraphRAG Protocol Demo Server", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-Admin-Token"],
)


@app.get("/health")
def health() -> dict[str, Any]:
    status = _ADAPTER.health_check()
    client = llm_client()
    return {
        "status": "ok",
        "backend": status.get("backend", "demo"),
        "llm": {"available": client is not None, "model": llm_model() if client else None},
        "stream_subscribers": STREAM_BUS.subscriber_count,
        "details": status,
    }


@app.post("/query")
def query_endpoint(payload: QueryRequest) -> dict[str, Any]:
    return run_pipelines(_RETRIEVAL, _FORMATTER, payload.query.strip(), payload.mode)


@app.get("/benchmark/results")
def benchmark_results(limit: int = 3, mode: str = "auto") -> list[dict[str, Any]]:
    return _dashboard_rows(_load_benchmark_queries(limit=max(1, min(limit, 20))), mode)


@app.get("/evaluation/report")
def evaluation_report(limit: int = 10, mode: str = "auto") -> dict[str, Any]:
    """Contract 9: aggregate EvaluationReport over the benchmark queries."""
    query_set = _load_benchmark_queries(limit=max(1, min(limit, 50)))
    report = _EVALUATION.evaluate_report(query_set, mode=mode)
    return report.model_dump()


@app.get("/schema")
def schema_endpoint() -> dict[str, Any]:
    return _ADAPTER.get_schema().model_dump()


@app.post("/graph/visualize")
def graph_visualize(payload: GraphRequest) -> SubgraphContext:
    entity_id = payload.entity_id
    if not entity_id:
        ctx = _RETRIEVAL.local_search(query="transformer", top_k=1, depth=0)
        ents = ctx.results.get("entities", [])
        entity_id = ents[0]["id"] if ents else "paper:attention"
    return _ADAPTER.entity_lookup(entity_id=entity_id, depth=2)


@app.post("/federated/search")
def federated_search(payload: FederatedRequest) -> SubgraphContext:
    """Contract 6: fan-out retrieval with an explicit merge policy."""
    config = _federation_config(
        top_k=payload.top_k,
        merge_strategy=MergeStrategy(payload.merge_strategy),
    )
    return _FEDERATION.federated_search(payload.query.strip(), config=config, mode=payload.mode)


@app.post("/graph/entity-link")
def entity_link(payload: EntityLinkRequest) -> list[dict[str, Any]]:
    """Contract 6: cross-graph entity resolution candidates."""
    links = _FEDERATION.cross_graph_entity_link(
        payload.entity_name.strip(), config=_federation_config(), entity_type=payload.entity_type
    )
    return [link.model_dump() for link in links]


@app.get("/auth/operations")
def auth_operations(x_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    """Contract 10: what the caller may do with the presented token."""
    return {
        "role": _AUTH.resolve_role(token=x_admin_token),
        "allowed_operations": _AUTH.get_allowed_operations(token=x_admin_token),
    }


@app.post("/ingest")
def ingest(payload: IngestRequest, x_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    """Contract 4: real ingestion (admin only).

    The contract itself publishes the Contract 7 events at the mutation point,
    so this endpoint never double-publishes.
    """
    _require_admin("ingest", x_admin_token)
    config = IngestionConfig(
        graph_id=getattr(_ADAPTER, "_graphname", "default"),
        extraction=payload.extraction,
        max_concepts_per_doc=payload.max_concepts_per_doc,
        dry_run=payload.dry_run,
    )
    try:
        report = _CONSTRUCTION.ingest(payload.documents, config)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return report.model_dump()


@app.delete("/documents/{document_id}")
def delete_document(document_id: str, x_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    """Contract 4: real document deletion (admin only); events come from the contract."""
    _require_admin("delete_document", x_admin_token)
    return _CONSTRUCTION.delete_document(document_id).model_dump()


@app.get("/stream/events")
async def stream_events(event_types: str | None = None, replay: bool = False) -> StreamingResponse:
    """Contract 7: real SSE feed of graph-mutation events."""
    wanted: list[StreamEventType] | None = None
    if event_types:
        try:
            wanted = [StreamEventType(t.strip()) for t in event_types.split(",") if t.strip()]
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"unknown event type: {exc}") from exc

    async def generator():
        try:
            async for event in STREAM_BUS.subscribe(event_types=wanted, replay=replay, timeout=15.0):
                if event is None:
                    yield ": ping\n\n"
                else:
                    yield f"data: {json.dumps(event.model_dump(mode='json'))}\n\n"
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def main() -> None:
    import uvicorn

    host = os.environ.get("DEMO_HOST", "127.0.0.1")
    port = int(os.environ.get("DEMO_PORT", "8000"))
    uvicorn.run("mcp_server.server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
