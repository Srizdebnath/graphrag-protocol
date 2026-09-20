import { useMemo } from "react";
import type { BenchmarkResult } from "../../lib/types";

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
    const evaluated = results.filter((r) => r.evaluation.judge_pass !== null);
    const judgePasses = evaluated.filter((r) => r.evaluation.judge_pass).length;
    const judgePassRate = evaluated.length
      ? (judgePasses / evaluated.length) * 100
      : 0;

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
      sub: "evaluation dataset",
      bg: "bg-[#E0E7FF]",
    },
    {
      label: "Avg Token Reduction",
      value: `${stats.avgTokenReduction.toFixed(1)}%`,
      sub: "GraphRAG vs LLM-only",
      highlight: stats.avgTokenReduction > 0,
      bg: "bg-[#DCFCE7]",
    },
    {
      label: "Avg Latency",
      value: `${stats.avgLatency.toFixed(0)}ms`,
      sub: "GraphRAG pipeline",
      bg: "bg-[#FEF08A]",
    },
    {
      label: "Judge Pass Rate",
      value: `${stats.judgePassRate.toFixed(0)}%`,
      sub: `${stats.judgePasses}/${stats.total} queries passed`,
      highlight: stats.judgePassRate >= 90,
      bg: "bg-[#FCE7F3]",
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((card) => (
        <div
          key={card.label}
          className={`rounded-xl border-3 border-black ${card.bg} p-5 shadow-brutal transition-transform hover:translate-x-[-2px] hover:translate-y-[-2px]`}
        >
          <p className="font-mono text-xs font-black uppercase tracking-wider text-black/70">{card.label}</p>
          <p className="mt-2 font-mono text-3xl font-black text-black">
            {card.value}
          </p>
          <p className="mt-1 font-mono text-xs font-bold text-black/60">{card.sub}</p>
        </div>
      ))}
    </div>
  );
}
