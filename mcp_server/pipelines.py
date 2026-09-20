"""Shared 3-pipeline runner (LLM-only / Basic RAG / GraphRAG).

Used by the HTTP demo server AND by ``hackathon/scripts/evaluate.py`` so the
dashboard and the evaluation harness always report identical numbers for
identical queries. Nothing here is synthesized: retrieval goes through the
protocol contracts, token counts are measured from the exact prompt text, and
answers come from a real Gemini call whenever ``GOOGLE_API_KEY`` is set (with
an explicitly labeled extractive fallback otherwise).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from mcp_server.contracts.retrieval import RetrievalContract
from mcp_server.formatters import MarkdownFormatter
from mcp_server.protocol import SubgraphContext

PIPELINE_1 = "pipeline_1_llm_only"
PIPELINE_2 = "pipeline_2_basic_rag"
PIPELINE_3 = "pipeline_3_graphrag"

DEFAULT_QUERY_FILE = Path("hackathon/data/queries/single_hop.json")

_LLM_CLIENT: Any | None = None
_LLM_STATE: bool | None = None  # None = not probed yet, False = unavailable


def llm_model() -> str:
    """Configured answer/judge model id."""
    return os.environ.get("LLM_MODEL", "gemini-3.8-flash")


def llm_client():
    """Lazily build the Gemini client; ``None`` when no key is configured.

    The probe result is cached so a missing key never retries per request.
    """
    global _LLM_CLIENT, _LLM_STATE
    if _LLM_STATE is False:
        return None
    if _LLM_CLIENT is None:
        key = os.environ.get("GOOGLE_API_KEY")
        if not key:
            _LLM_STATE = False
            return None
        try:
            from google import genai

            _LLM_CLIENT = genai.Client(api_key=key)
            _LLM_STATE = True
        except Exception as exc:  # noqa: BLE001 - degrade, never fail a request
            print(f"[pipelines] LLM unavailable ({type(exc).__name__}); extraction-only answers")
            _LLM_STATE = False
            return None
    return _LLM_CLIENT


def estimate_tokens(text: str) -> int:
    """Measured-length token estimate (~4 chars/token); never zero for text."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def answer_question(question: str, context_text: str, style: str) -> tuple[str, str]:
    """Answer one question for one pipeline. Returns ``(answer, answer_source)``.

    Args:
        question: The user question.
        context_text: Retrieved context (empty for the LLM-only pipeline).
        style: ``'llm_only'`` prompts without context; ``'rag'`` and
            ``'graphrag'`` prompt strictly from the supplied context.

    Returns:
        ``(answer, source)`` where source is ``'llm'`` or ``'extraction_only'``.
        The extractive fallback is always labeled in the answer text so it can
        never be mistaken for model output.
    """
    import time

    client = llm_client()
    if client is None:
        snippet = " ".join(context_text.split())[:400] if context_text else "(no retrieval configured)"
        return f"[extraction_only — no LLM configured] {snippet}", "extraction_only"
    if style == "llm_only":
        prompt = f"Answer the question from your own knowledge. Be concise.\n\nQuestion: {question}"
    else:
        prompt = (
            "Answer the question using ONLY the context below. Cite entity names you use.\n\n"
            f"Context:\n{context_text}\n\nQuestion: {question}"
        )

    attempts = 3
    backoff = 0.5
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            resp = client.models.generate_content(model=llm_model(), contents=prompt)
            return (resp.text or "").strip() or "(empty LLM response)", "llm"
        except Exception as exc:  # noqa: BLE001 - degrade, never fail the request
            last_exc = exc
            err_str = str(exc).lower()
            if attempt < attempts - 1 and any(c in err_str for c in ("503", "unavailable", "resource_exhausted", "429", "rate")):
                time.sleep(backoff)
                backoff *= 2
                continue
            break

    snippet = " ".join(context_text.split())[:400] if context_text else "(no retrieval)"
    return f"[llm_error: {type(last_exc).__name__ if last_exc else 'unknown'}; extraction_only fallback] {snippet}", "extraction_only"


def _pipeline_row(
    *,
    name: str,
    question: str,
    ctx: SubgraphContext | None,
    context_text: str,
    style: str,
) -> dict[str, Any]:
    """Build one dashboard row with measured tokens/latency and real provenance."""
    import time

    t0 = time.perf_counter()
    answer, source = answer_question(question, context_text, style=style)
    latency_ms = (time.perf_counter() - t0) * 1000
    prompt_text = question if style == "llm_only" else f"{context_text}\n\n{question}"
    row: dict[str, Any] = {
        "pipeline": name,
        "answer": answer,
        "answer_source": source,
        "retrieval_method": "none" if ctx is None else ctx.operation,
        "tokens_total": estimate_tokens(prompt_text),
        "latency_ms": round(latency_ms, 1),
        "model": None if source == "extraction_only" else llm_model(),
    }
    if ctx is not None:
        row["entities_used"] = ctx.metrics.entities_returned
        row["graph_hops"] = ctx.metrics.graph_hops_traversed
        row["provenance"] = ctx.provenance.model_dump()
    return row


def run_pipelines(
    retrieval: RetrievalContract,
    formatter: MarkdownFormatter,
    question: str,
    mode: str = "auto",
) -> dict[str, dict[str, Any]]:
    """Run the three-pipeline comparison for one question.

    Args:
        retrieval: Contract-1 wrapper over the live adapter.
        formatter: Contract-8 formatter used to serialize context.
        question: The user question.
        mode: Retrieval mode for the GraphRAG pipeline.

    Returns:
        ``{"pipeline_1": row, "pipeline_2": row, "pipeline_3": row}``.
    """
    row1 = _pipeline_row(name=PIPELINE_1, question=question, ctx=None, context_text="", style="llm_only")

    ctx2 = retrieval.local_search(query=question, top_k=5, depth=1)
    text2 = formatter.format_context(ctx2, max_tokens=1500)
    row2 = _pipeline_row(name=PIPELINE_2, question=question, ctx=ctx2, context_text=text2, style="rag")

    result3 = retrieval.search(query=question, mode=mode)
    text3 = formatter.format_context(result3.context, max_tokens=3000)
    row3 = _pipeline_row(
        name=PIPELINE_3, question=question, ctx=result3.context, context_text=text3, style="graphrag"
    )
    return {"pipeline_1": row1, "pipeline_2": row2, "pipeline_3": row3}


def load_query_set(path: Path | str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    """Load benchmark queries from the real query files.

    There is deliberately no built-in sample fallback: inventing queries would
    make the dashboard and the evaluation harness disagree with the benchmark
    data that is actually committed.

    Args:
        path: JSON file of queries; defaults to the single-hop set.
        limit: Optional cap on the number of queries returned.

    Returns:
        Query dicts with ``id``, ``category`` and ``query`` keys.

    Raises:
        FileNotFoundError: The query file does not exist.
        ValueError: The file holds no usable (id + query) entries.
    """
    target = Path(path) if path else DEFAULT_QUERY_FILE
    if not target.exists():
        raise FileNotFoundError(f"benchmark query file not found: {target}")
    items = [
        {
            "id": str(entry["id"]).strip(),
            "category": entry.get("category", "single_hop"),
            "query": str(entry["query"]).strip(),
        }
        for entry in json.loads(target.read_text())
        if entry.get("id") and str(entry.get("query") or "").strip()
    ]
    if not items:
        raise ValueError(f"benchmark query file holds no usable queries: {target}")
    items.sort(key=lambda q: q["id"])
    return items[:limit] if limit else items
