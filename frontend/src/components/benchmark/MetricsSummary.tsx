import { useMemo } from "react";
import type { BenchmarkResult } from "../../lib/types";
import Card from "../shared/Card";

interface MetricsSummaryProps {
  results: BenchmarkResult[];
}

export default function MetricsSummary({ results }: MetricsSummaryProps) {
  const stats = useMemo(() => {
    if (results.length === 0) return null;

    const total = results.length;
    const avgTokenReduction =
      (results.reduce(
        (acc, r) =>
          acc +
          ((r.pipeline_1.tokens_total - r.pipeline_3.tokens_total) /
            r.pipeline_1.tokens_total) *
            100,
        0
      ) / total) *
      -1;
    const avgLatency =
      results.reduce((acc, r) => acc + r.pipeline_3.latency_ms, 0) / total;
    const judgePasses = results.filter((r) => r.evaluation.judge_pass).length;
    const judgePassRate = (judgePasses / total) * 100;

    return {
      total,
      avgTokenReduction,
      avgLatency,
      judgePassRate,
      judgePasses,
    };
  }, [results]);

  if (!stats) return null;

  const cards = [
    {
      label: "Total Queries",
      value: stats.total.toLocaleString(),
      sub: "after GraphRAG vs LLM-only",
    },
    {
      label: "Avg Token Reduction",
      value: `${stats.avgTokenReduction.toFixed(1)}%`,
      sub: "GraphRAG vs LLM-only",
      highlight: stats.avgTokenReduction > 0,
    },
    {
      label: "Avg Latency",
      value: `${stats.avgLatency.toFixed(0)}ms`,
      sub: "GraphRAG pipeline",
    },
    {
      label: "Judge Pass Rate",
      value: `${stats.judgePassRate.toFixed(0)}%`,
      sub: `${stats.judgePasses}/${stats.total} queries passed`,
      highlight: stats.judgePassRate >= 90,
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((card) => (
        <Card key={card.label}>
          <p className="text-xs text-gray-500">{card.label}</p>
          <p
            className={`mt-1 text-2xl font-bold ${
              card.highlight === true
                ? "text-green-600"
                : card.highlight === false
                  ? "text-red-600"
                  : "text-gray-900"
            }`}
          >
            {card.value}
          </p>
          <p className="mt-0.5 text-xs text-gray-400">{card.sub}</p>
        </Card>
      ))}
    </div>
  );
}
