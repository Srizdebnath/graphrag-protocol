"""Contract 9: Evaluation — real retrieval and answer metrics.

Every number produced here is measured, never synthesized:

- ``precision_at_k`` / ``recall_at_k`` are computed from the retrieved entity
  names/ids against the reference answer's content terms.
- ``faithfulness`` is a lexical grounding check of the answer against the
  retrieved context (share of answer content terms present in the context).
- ``judge_pass`` / ``judge_reason`` come from a real LLM-as-judge call
  (Gemini). With no ``GOOGLE_API_KEY`` the verdict stays ``None`` with an
  explicit reason — it is never defaulted to PASS.
- ``bertscore_f1`` is computed only when the optional ``bert-score`` package
  is installed; otherwise it stays ``None`` and a note records why.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from mcp_server.adapters.base import BaseGraphRAGAdapter
from mcp_server.contracts.construction import STOPWORDS
from mcp_server.protocol import SubgraphContext
from mcp_server.protocol_extensions import (
    AnswerEval,
    EvaluationReport,
    RetrievalEval,
)

_TERM_RE = re.compile(r"[a-z][a-z0-9\-]{3,}")
_GROUNDED_THRESHOLD = 0.6


def content_terms(text: str) -> set[str]:
    """Lowercased content terms (length >= 4, stopwords removed)."""
    return {t.strip("-") for t in _TERM_RE.findall((text or "").lower()) if t.strip("-") not in STOPWORDS}


def relevance_of(entity: dict[str, Any], default: float = 0.0) -> float:
    """Read an entity's relevance score, treating 0.0 as a real score.

    ``entity.get(...) or default`` would wrongly promote a legitimate 0.0 to
    the default, so the None case is handled explicitly.
    """
    raw = entity.get("relevance_score")
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


class EvaluationContract:
    """Contract 9: backend-comparable retrieval/answer evaluation.

    Args:
        adapter: Adapter used for the retrieval side of a benchmark.
        llm_client: Optional pre-built Gemini client for the judge; built
            lazily from ``GOOGLE_API_KEY`` when omitted.
        judge_model: Judge model id; defaults to ``LLM_MODEL``.
    """

    def __init__(
        self,
        adapter: BaseGraphRAGAdapter,
        llm_client: Any | None = None,
        judge_model: str | None = None,
    ) -> None:
        if adapter is None:
            raise ValueError("EvaluationContract requires a non-None adapter")
        self._adapter = adapter
        self._llm_client = llm_client
        self._llm_resolved = llm_client is not None
        self._judge_model = judge_model or os.environ.get("LLM_MODEL", "gemini-3.8-flash")

    # -- LLM plumbing -----------------------------------------------------------

    def _llm(self):
        """Lazily build the judge client; None when no key is configured."""
        if self._llm_resolved:
            return self._llm_client
        self._llm_resolved = True
        key = os.environ.get("GOOGLE_API_KEY")
        if not key:
            return None
        try:
            from google import genai

            self._llm_client = genai.Client(api_key=key)
        except Exception:  # noqa: BLE001 - judge is optional
            self._llm_client = None
        return self._llm_client

    # -- retrieval metrics -------------------------------------------------------

    def evaluate_retrieval(
        self,
        query_id: str,
        context: SubgraphContext,
        reference: str,
        k: int = 10,
    ) -> RetrievalEval:
        """Measure retrieval quality against a gold reference answer.

        Args:
            query_id: Query identifier.
            context: The retrieved subgraph context (Contract 2).
            reference: Gold answer text.
            k: Rank cut-off for precision@k.

        Returns:
            A :class:`RetrievalEval` with measured precision/recall.
        """
        if context is None:
            raise ValueError("evaluate_retrieval requires a context")
        ref_terms = content_terms(reference)
        entities = context.results.get("entities", []) or []
        ranked = sorted(entities, key=lambda e: -relevance_of(e))[: max(1, k)]

        relevant = 0
        covered: set[str] = set()
        for ent in ranked:
            ent_terms = content_terms(f"{ent.get('name', '')} {ent.get('id', '')}")
            hits = ent_terms & ref_terms
            if hits:
                relevant += 1
                covered |= hits
        precision = relevant / k if k > 0 else 0.0
        recall = len(covered) / len(ref_terms) if ref_terms else 0.0
        return RetrievalEval(
            query_id=query_id,
            precision_at_k=round(precision, 4),
            recall_at_k=round(recall, 4),
            entities_retrieved=len(entities),
            graph_hops=int(context.metrics.graph_hops_traversed),
            latency_ms=float(context.metrics.latency_ms),
        )

    # -- answer metrics ----------------------------------------------------------

    def evaluate_answer(
        self,
        query_id: str,
        query: str,
        answer: str,
        reference: str,
        context: SubgraphContext | None = None,
    ) -> AnswerEval:
        """Judge an answer and check its grounding in the retrieved context.

        Args:
            query_id: Query identifier.
            query: The original question.
            answer: The produced answer.
            reference: Gold answer text.
            context: Retrieved context used for the answer (grounding check).

        Returns:
            An :class:`AnswerEval`; judge fields are ``None`` when no LLM is
            configured rather than being assumed to pass.
        """
        verdict, reason, model = self._judge(query, answer, reference)
        faithfulness = None
        if context is not None:
            faithfulness = self._grounding(answer, context)
        return AnswerEval(
            query_id=query_id,
            judge_pass=verdict,
            judge_reason=reason,
            judge_model=model,
            bertscore_f1=self._bertscore(answer, reference),
            faithfulness=faithfulness,
        )

    def _judge(self, query: str, answer: str, reference: str) -> tuple[bool | None, str, str | None]:
        """Real LLM-as-judge call; (None, reason, None) when unavailable."""
        client = self._llm()
        if client is None:
            return None, "no LLM configured (GOOGLE_API_KEY unset); verdict not evaluated", None
        prompt = (
            "You are a strict evaluator of retrieval-augmented answers. Compare the "
            "candidate answer to the reference answer for the given question.\n\n"
            f"Question: {query}\nReference: {reference}\nCandidate: {answer}\n\n"
            'Reply with JSON only: {"verdict": "PASS"|"FAIL", "reason": "<one sentence>"}'
        )
        try:
            resp = client.models.generate_content(model=self._judge_model, contents=prompt)
            raw = (resp.text or "").strip().removeprefix("```json").removeprefix("```").removesuffix("```")
            data = json.loads(raw)
            verdict = str(data.get("verdict", "")).strip().upper() == "PASS"
            return verdict, str(data.get("reason") or "").strip() or "judged", self._judge_model
        except Exception as exc:  # noqa: BLE001 - judge failures are reported, not fatal
            return None, f"judge call failed: {type(exc).__name__}: {exc}", self._judge_model

    @staticmethod
    def _grounding(answer: str, context: SubgraphContext) -> str:
        """Lexical grounding check of the answer against retrieved evidence."""
        answer_terms = content_terms(answer)
        if not answer_terms:
            return "ungrounded"
        evidence = " ".join(
            [str(c.get("text", "")) for c in context.results.get("text_chunks", []) or []]
            + [str(e.get("name", "")) for e in context.results.get("entities", []) or []]
        )
        evidence_terms = content_terms(evidence)
        if not evidence_terms:
            return "ungrounded"
        overlap = len(answer_terms & evidence_terms) / len(answer_terms)
        return "grounded" if overlap >= _GROUNDED_THRESHOLD else "ungrounded"

    @staticmethod
    def _bertscore(answer: str, reference: str) -> float | None:
        """BERTScore F1 when the optional dependency is installed, else None."""
        if not answer or not reference:
            return None
        try:
            from bert_score import score as bert_score  # type: ignore[import-not-found]
        except Exception:  # noqa: BLE001 - optional extra
            return None
        try:
            _, _, f1 = bert_score([answer], [reference], lang="en", verbose=False)
            return round(float(f1[0]), 4)
        except Exception:  # noqa: BLE001
            return None

    # -- aggregate reports -------------------------------------------------------

    def evaluate_report(
        self,
        query_set: list[dict[str, Any]],
        mode: str = "auto",
        pipeline: str = "graphrag",
        answerer: Any | None = None,
        k: int = 10,
    ) -> EvaluationReport:
        """Evaluate a query set end-to-end and aggregate the metrics.

        Args:
            query_set: Entries with ``id``, ``query`` and ``reference``.
            mode: Retrieval mode for the GraphRAG pipeline.
            pipeline: Which pipeline produced answers: ``'graphrag'``,
                ``'basic_rag'`` or ``'llm_only'``.
            answerer: Optional ``(question, context_text, style) -> (answer, source)``
                callable. Defaults to a real Gemini answerer built from
                ``GOOGLE_API_KEY``; when no key exists answers are extracted
                from context and labeled as such.
            k: Rank cut-off for precision@k.

        Returns:
            An :class:`EvaluationReport` with real aggregates and notes about
            any metric that could not be measured.
        """
        from mcp_server.contracts.retrieval import RetrievalContract
        from mcp_server.formatters import MarkdownFormatter

        if not query_set:
            raise ValueError("evaluate_report requires a non-empty query_set")
        retrieval = RetrievalContract(self._adapter)
        formatter = MarkdownFormatter()
        answer_fn = answerer or self._default_answerer()
        report = EvaluationReport(
            backend=getattr(self._adapter, "health_check", dict)().get("backend", "tigergraph"),
            model=self._judge_model if self._llm() is not None else None,
            num_queries=len(query_set),
        )
        if self._llm() is None:
            report.notes.append("No LLM configured: judge verdicts are null, answers are extractive.")
        if self._bertscore("probe", "probe") is None:
            report.notes.append("bert-score extra not installed: bertscore_f1 is null.")

        for item in query_set:
            qid = str(item.get("id") or f"q{len(report.retrieval) + 1:03d}")
            question = str(item.get("query") or "")
            reference = str(item.get("reference") or "")
            if not question:
                report.notes.append(f"{qid}: missing query text; skipped")
                continue
            try:
                if pipeline == "basic_rag":
                    context = retrieval.local_search(query=question, top_k=5, depth=1)
                    style = "rag"
                else:
                    result = retrieval.search(query=question, mode=mode)
                    context = result.context
                    style = "graphrag" if pipeline != "llm_only" else "llm_only"
            except Exception as exc:  # noqa: BLE001 - one bad query must not abort
                report.notes.append(f"{qid}: retrieval failed: {type(exc).__name__}: {exc}")
                continue

            context_text = "" if pipeline == "llm_only" else formatter.format_context(context, max_tokens=3000)
            answer, source = answer_fn(question, context_text, style)
            retrieval_eval = self.evaluate_retrieval(qid, context, reference, k=k) if pipeline != "llm_only" else RetrievalEval(
                query_id=qid, precision_at_k=0.0, recall_at_k=0.0,
                entities_retrieved=0, graph_hops=0, latency_ms=0.0,
            )
            answer_eval = self.evaluate_answer(qid, question, answer, reference, context)
            report.retrieval.append(retrieval_eval)
            report.answers.append(answer_eval)
            if source == "extraction_only" and "extractive answers" not in " ".join(report.notes):
                report.notes.append("Answers are extractive (no LLM); judge fields describe them as such.")

        report.avg_precision_at_k = self._avg([r.precision_at_k for r in report.retrieval])
        report.avg_recall_at_k = self._avg([r.recall_at_k for r in report.retrieval])
        judged = [a.judge_pass for a in report.answers if a.judge_pass is not None]
        report.judge_pass_rate = round(sum(1 for v in judged if v) / len(judged), 4) if judged else None
        scores = [a.bertscore_f1 for a in report.answers if a.bertscore_f1 is not None]
        report.avg_bertscore_f1 = round(sum(scores) / len(scores), 4) if scores else None
        return report

    def _default_answerer(self):
        """Real Gemini answerer, degrading to labeled extraction without a key."""
        client = self._llm()
        model = self._judge_model

        def answer(question: str, context_text: str, style: str) -> tuple[str, str]:
            if client is None:
                snippet = " ".join(context_text.split())[:400] if context_text else "(no retrieval configured)"
                return f"[extraction_only] {snippet}", "extraction_only"
            prompt = (
                f"Answer the question from your own knowledge. Be concise.\n\nQuestion: {question}"
                if style == "llm_only"
                else (
                    "Answer the question using ONLY the context below. Cite entity names.\n\n"
                    f"Context:\n{context_text}\n\nQuestion: {question}"
                )
            )
            try:
                resp = client.models.generate_content(model=model, contents=prompt)
                return (resp.text or "").strip() or "(empty LLM response)", "llm"
            except Exception as exc:  # noqa: BLE001
                snippet = " ".join(context_text.split())[:400]
                return f"[llm_error: {type(exc).__name__}] {snippet}", "extraction_only"

        return answer

    @staticmethod
    def _avg(values: list[float]) -> float | None:
        return round(sum(values) / len(values), 4) if values else None
