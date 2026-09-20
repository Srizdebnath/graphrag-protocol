#!/usr/bin/env python3
"""Run the real evaluation harness over the benchmark query set.

Produces measured numbers only: retrieval precision@k/recall@k from the
retrieved entities vs. the gold reference answers, LLM-as-judge verdicts from
real Gemini calls, optional BERTScore, plus the 3-pipeline comparison
(LLM-only / Basic RAG / GraphRAG) in the dashboard shape.

When ``GOOGLE_API_KEY`` is unset the judge fields are written as ``null`` (with
an explanatory note) and answers are labeled extractive — never faked as PASS.

Usage:
    .venv/bin/python hackathon/scripts/evaluate.py --limit 10
    .venv/bin/python hackathon/scripts/evaluate.py --pipeline basic_rag --mode local
    .venv/bin/python hackathon/scripts/evaluate.py --skip-benchmark
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

from mcp_server.contracts.evaluation import EvaluationContract
from mcp_server.contracts.retrieval import RetrievalContract
from mcp_server.formatters import MarkdownFormatter
from mcp_server.pipelines import run_pipelines

QUERIES_DIR = PROJECT_ROOT / "hackathon" / "data" / "queries"
CATEGORIES = ("single_hop", "multi_hop", "global", "comparison")


def pick_adapter():
    """TigerGraph when configured and healthy; demo adapter otherwise."""
    from mcp_server.adapters import DemoGraphRAGAdapter, TigerGraphAdapter

    try:
        adapter = TigerGraphAdapter()
        health = adapter.health_check()
        if health.get("status") == "ok":
            print(f"[adapter] tigergraph {health.get('version', '')} graph={health.get('graph_id')}")
            return adapter
        print(f"[adapter] TigerGraph unhealthy ({health}); using demo adapter")
    except Exception as exc:  # noqa: BLE001
        print(f"[adapter] TigerGraph unavailable ({type(exc).__name__}: {exc}); using demo adapter")
    return DemoGraphRAGAdapter()


def load_queries(limit: int | None) -> list[dict]:
    """All benchmark queries across categories, validated against the data."""
    items: list[dict] = []
    for category in CATEGORIES:
        path = QUERIES_DIR / f"{category}.json"
        if not path.exists():
            print(f"[queries] missing {path.name}; skipped")
            continue
        for q in json.loads(path.read_text()):
            items.append(
                {
                    "id": q["id"],
                    "category": q.get("category", category),
                    "query": q["query"],
                }
            )
    items.sort(key=lambda q: q["id"])
    if limit:
        items = items[:limit]
    return items


def load_references() -> dict[str, str]:
    path = QUERIES_DIR / "reference_answers.json"
    if not path.exists():
        print(f"[queries] missing {path.name}; evaluation will run without references")
        return {}
    return json.loads(path.read_text())


def build_query_set(limit: int | None) -> list[dict]:
    references = load_references()
    query_set = []
    for item in load_queries(limit):
        query_set.append({**item, "reference": references.get(item["id"], "")})
    return query_set


def benchmark_rows(adapter, query_set: list[dict], mode: str) -> list[dict]:
    """3-pipeline dashboard rows with per-pipeline real evaluation."""
    evaluation = EvaluationContract(adapter)
    retrieval = RetrievalContract(adapter)
    formatter = MarkdownFormatter()
    rows: list[dict] = []
    for i, item in enumerate(query_set, start=1):
        t0 = time.perf_counter()
        pipelines = run_pipelines(retrieval, formatter, item["query"], mode=mode)
        per_pipeline_eval: dict[str, dict] = {}
        for key in ("pipeline_1", "pipeline_2", "pipeline_3"):
            row = pipelines[key]
            verdict = evaluation.evaluate_answer(
                query_id=item["id"],
                query=item["query"],
                answer=row["answer"],
                reference=item["reference"],
                context=None,
            )
            per_pipeline_eval[key] = {
                "judge_pass": verdict.judge_pass,
                "judge_reason": verdict.judge_reason,
                "bertscore_f1": verdict.bertscore_f1,
                "answer_source": row["answer_source"],
            }
        headline = per_pipeline_eval["pipeline_3"]
        rows.append(
            {
                "query_id": item["id"],
                "query": item["query"],
                "category": item["category"],
                "reference": item["reference"],
                **pipelines,
                "evaluation": {
                    "judge_pass": headline["judge_pass"],
                    "judge_reason": headline["judge_reason"],
                    "bertscore_f1": headline["bertscore_f1"],
                },
                "pipeline_evaluations": per_pipeline_eval,
                "wall_ms": round((time.perf_counter() - t0) * 1000, 1),
            }
        )
        print(f"  [{i}/{len(query_set)}] {item['id']}: judge={headline['judge_pass']} source={headline['answer_source']}")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the GraphRAG protocol pipelines")
    parser.add_argument("--limit", type=int, default=10, help="max queries (0 = all)")
    parser.add_argument("--mode", default="auto", help="retrieval mode for the GraphRAG pipeline")
    parser.add_argument(
        "--pipeline",
        default="graphrag",
        choices=("graphrag", "basic_rag", "llm_only"),
        help="pipeline used for the aggregate EvaluationReport",
    )
    parser.add_argument("--k", type=int, default=10, help="rank cut-off for precision@k")
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "hackathon" / "results"),
        help="directory for evaluation.json / benchmark_results.json",
    )
    parser.add_argument("--skip-benchmark", action="store_true", help="only write the EvaluationReport")
    args = parser.parse_args()

    adapter = pick_adapter()
    query_set = build_query_set(args.limit or None)
    if not query_set:
        raise SystemExit("no queries found under hackathon/data/queries")
    with_refs = sum(1 for q in query_set if q["reference"])
    print(f"[queries] {len(query_set)} queries ({with_refs} with reference answers)")

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[eval] aggregate report (pipeline={args.pipeline}, mode={args.mode})")
    contract = EvaluationContract(adapter)
    report = contract.evaluate_report(query_set, mode=args.mode, pipeline=args.pipeline, k=args.k)
    (out_dir / "evaluation.json").write_text(json.dumps(report.model_dump(), indent=2))
    print(f"  precision@k={report.avg_precision_at_k} recall@k={report.avg_recall_at_k}")
    print(f"  judge_pass_rate={report.judge_pass_rate} bertscore_f1={report.avg_bertscore_f1}")
    for note in report.notes:
        print(f"  note: {note}")

    if not args.skip_benchmark:
        print("[benchmark] 3-pipeline comparison with real judge per pipeline")
        rows = benchmark_rows(adapter, query_set, args.mode)
        (out_dir / "benchmark_results.json").write_text(json.dumps(rows, indent=2))
        judged = [r["evaluation"]["judge_pass"] for r in rows if r["evaluation"]["judge_pass"] is not None]
        if judged:
            print(f"  graphrag judge pass rate: {sum(1 for v in judged if v)}/{len(judged)}")
        else:
            print("  judge not evaluated (no LLM configured); answers are labeled extraction_only")

    print(f"[done] wrote results to {out_dir}")


if __name__ == "__main__":
    main()
