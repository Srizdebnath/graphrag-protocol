"""GraphRAG Protocol — HTTP demo/dashboard server (FastAPI).

This is the **demo server** for the Next.js dashboard; it is NOT the MCP
server. The MCP entrypoint is ``mcp_server.mcp_server`` (``graphrag-mcp``),
which exposes the protocol as MCP tools over stdio.

What this server does honestly:
- Retrieval is REAL: every pipeline calls the shared adapter (TigerGraph when
  configured and healthy, else the in-memory demo adapter) through the
  protocol contracts layer.
- Answer generation is REAL when ``GOOGLE_API_KEY`` is set: each pipeline
  prompts the configured Gemini model with its own retrieval context
  (LLM-only / Basic-RAG-style / GraphRAG-style). Token counts are measured
  from the actual context strings.
- When no API key is configured, answers are explicitly labeled
  ``extraction_only``: extractive snippets from retrieved context, clearly
  marked — never presented as LLM output.
- ``/benchmark/results`` runs real queries through the same pipelines and
  reports real measured metrics. LLM-judge / BERTScore fields are ``null``
  until a real eval harness runs (see SPEC.md Contract 9).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from mcp_server.adapters import DemoGraphRAGAdapter, TigerGraphAdapter
from mcp_server.contracts.retrieval import RetrievalContract
from mcp_server.formatters import MarkdownFormatter
from mcp_server.protocol import SubgraphContext

load_dotenv()

_DEFAULT_QUERIES = [
    {"id": "q01", "category": "single_hop", "query": "What is the relationship between the Transformer and BERT?"},
    {"id": "q02", "category": "multi_hop", "query": "How do retrieval systems use graph structure in reasoning?"},
    {"id": "q03", "category": "global", "query": "What are the main research trends in transformer-based AI?"},
]


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    mode: str = Field(default="auto", pattern="^(auto|local|global|hybrid|entity)$")


class GraphRequest(BaseModel):
    entity_id: str | None = Field(default=None, max_length=200)


def _adapter() -> Any:
    """TigerGraph when configured and healthy; demo adapter otherwise."""
    try:
        adapter = TigerGraphAdapter()
        if adapter.health_check().get("status") == "ok":
            return adapter
    except Exception as exc:  # noqa: BLE001 - degrade to demo, never crash
        print(f"[server] TigerGraph unavailable ({type(exc).__name__}); using demo adapter")
        return DemoGraphRAGAdapter()
    print("[server] TigerGraph unhealthy; using demo adapter")
    return DemoGraphRAGAdapter()


_ADAPTER = _adapter()
_RETRIEVAL = RetrievalContract(_ADAPTER)
_FORMATTER = MarkdownFormatter()

_LLM_MODEL = os.environ.get("LLM_MODEL", "gemini-2.5-flash")
_LLM_CLIENT: Any | None = None
_LLM_AVAILABLE: bool | None = None


def _llm():
    """Lazily build the Gemini client; None when unavailable."""
    global _LLM_CLIENT, _LLM_AVAILABLE
    if _LLM_AVAILABLE is False:
        return None
    if _LLM_CLIENT is None:
        key = os.environ.get("GOOGLE_API_KEY")
        if not key:
            _LLM_AVAILABLE = False
            return None
        try:
            from google import genai

            _LLM_CLIENT = genai.Client(api_key=key)
            _LLM_AVAILABLE = True
        except Exception as exc:  # noqa: BLE001
            print(f"[server] LLM unavailable ({type(exc).__name__}); serving extraction-only answers")
            _LLM_AVAILABLE = False
            return None
    return _LLM_CLIENT


def _tokens(text: str) -> int:
    """Rough but honest token estimate (~4 chars/token)."""
    return max(1, len(text) // 4)


def _answer(question: str, context_text: str, *, style: str) -> tuple[str, str, str | None]:
    """Generate one pipeline's answer. Returns (answer, answer_source, model_used).

    style: 'llm_only' prompts without retrieved context; 'rag'/'graphrag'
    prompt with their respective context. Primary model is retried 3x with
    backoff (503 overload / transient 429); if ``LLM_FALLBACK_MODEL`` is set,
    it is tried once more on hard failure (e.g. daily quota exhausted on a
    new 3.x model). Falls back to a clearly-labeled extractive answer when
    no LLM succeeds (never fabricates).
    """
    fallback_model = os.environ.get("LLM_FALLBACK_MODEL") or None
    client = _llm()
    if client is None:
        snippet = " ".join(context_text.split())[:400] if context_text else "(no retrieval configured)"
        return (f"[extraction_only — no LLM configured] {snippet}", "extraction_only", None)
    if style == "llm_only":
        prompt = f"Answer the question from your own knowledge. Be concise.\n\nQuestion: {question}"
    else:
        prompt = (
            "Answer the question using ONLY the context below. "
            "Cite entity names you use.\n\n"
            f"Context:\n{context_text}\n\nQuestion: {question}"
        )
    try:
        # New Gemini 3.x models intermittently return 503 UNAVAILABLE under
        # high demand, and free tier caps e.g. gemini-3.8-flash at 20 req/day.
        resp = None
        model_used = _LLM_MODEL
        for attempt in range(3):
            try:
                resp = client.models.generate_content(model=model_used, contents=prompt)
                break
            except Exception as retry_exc:  # noqa: BLE001 - 503/429 are transient
                if attempt == 2 and fallback_model:
                    model_used = fallback_model
                    resp = client.models.generate_content(model=model_used, contents=prompt)
                    break
                if attempt == 2:
                    raise
                print(f"[server] LLM attempt {attempt + 1} failed ({type(retry_exc).__name__}); retrying")
                time.sleep(2 * (attempt + 1))
        return (resp.text or "").strip() or "(empty LLM response)", "llm", model_used
    except Exception as exc:  # noqa: BLE001 - degrade, never 500
        snippet = " ".join(context_text.split())[:400] if context_text else "(no retrieval)"
        return (
            f"[llm_error: {type(exc).__name__}; extraction_only fallback] {snippet}",
            "extraction_only",
            None,
        )


def _pipeline(
    *,
    name: str,
    question: str,
    ctx: SubgraphContext | None,
    context_text: str,
    style: str,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    answer, source, model_used = _answer(question, context_text, style=style)
    latency_ms = (time.perf_counter() - t0) * 1000
    # Honest token accounting: tokens actually sent as prompt input.
    # pipeline_1 (LLM-only) = question only; pipelines 2/3 = context + question.
    prompt_text = question if style == "llm_only" else f"{context_text}\n\n{question}"
    tokens_total = _tokens(prompt_text)
    out: dict[str, Any] = {
        "pipeline": name,
        "answer": answer,
        "answer_source": source,
        "retrieval_method": "none" if ctx is None else ctx.operation,
        "tokens_total": tokens_total,
        "latency_ms": round(latency_ms, 1),
        "model": model_used,
    }
    if ctx is not None:
        out["entities_used"] = ctx.metrics.entities_returned
        out["graph_hops"] = ctx.metrics.graph_hops_traversed
        out["provenance"] = ctx.provenance.model_dump()
    return out


def _run_pipelines(question: str, mode: str = "auto") -> dict[str, Any]:
    """Run the 3-pipeline comparison with real retrieval + real generation."""
    p1 = _pipeline(name="pipeline_1_llm_only", question=question, ctx=None, context_text="", style="llm_only")

    ctx2 = _RETRIEVAL.local_search(query=question, top_k=5, depth=1)
    text2 = _FORMATTER.format_context(ctx2, max_tokens=1500)
    p2 = _pipeline(name="pipeline_2_basic_rag", question=question, ctx=ctx2, context_text=text2, style="rag")

    result3 = _RETRIEVAL.search(query=question, mode=mode)
    text3 = _FORMATTER.format_context(result3.context, max_tokens=3000)
    p3 = _pipeline(
        name="pipeline_3_graphrag",
        question=question,
        ctx=result3.context,
        context_text=text3,
        style="graphrag",
    )
    return {"pipeline_1": p1, "pipeline_2": p2, "pipeline_3": p3}


def _load_queries() -> list[dict[str, Any]]:
    """Prefer the real hackathon query set; fall back to the built-in sample."""
    path = Path("hackathon/data/queries/single_hop.json")
    try:
        items = [
            {"id": q["id"], "category": q.get("category", "single_hop"), "query": q["query"]}
            for q in json.loads(path.read_text())
        ]
        items.sort(key=lambda q: q["id"])
        if items:
            return items[:3]
    except Exception as exc:  # noqa: BLE001 - any problem -> built-in sample
        print(f"[server] query file unusable ({type(exc).__name__}); using built-in sample")
    return _DEFAULT_QUERIES


app = FastAPI(title="GraphRAG Protocol Demo Server", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
def health() -> dict[str, Any]:
    status = _ADAPTER.health_check()
    return {
        "status": "ok",
        "backend": status.get("backend", "demo"),
        "llm": {"available": _llm() is not None, "model": _LLM_MODEL if _llm() else None},
        "details": status,
    }


@app.post("/query")
def query_endpoint(payload: QueryRequest) -> dict[str, Any]:
    return _run_pipelines(payload.query.strip(), payload.mode)


@app.get("/benchmark/results")
def benchmark_results() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for q in _load_queries():
        pipelines = _run_pipelines(q["query"])
        results.append(
            {
                "query_id": q["id"],
                "query": q["query"],
                "category": q["category"],
                **pipelines,
                # Honest eval: judge/bertscore require the optional eval extras
                # and stay null until a real eval harness runs (Contract 9).
                "evaluation": {"judge_pass": None, "judge_reason": None, "bertscore_f1": None},
            }
        )
    return results


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


def main() -> None:
    import uvicorn

    host = os.environ.get("DEMO_HOST", "127.0.0.1")
    port = int(os.environ.get("DEMO_PORT", "8000"))
    uvicorn.run("mcp_server.server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
