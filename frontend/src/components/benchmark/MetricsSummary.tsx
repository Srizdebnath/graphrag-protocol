import { useMemo } from "react";
import type { BenchmarkResult } from "../../lib/types";

interface MetricsSummaryProps {
  results: BenchmarkResult[];
}

export default function MetricsSummary({ results }: MetricsSummaryProps) {
  const stats = useMemo(() => {
    if (results.length === 0) return null;

    const total = results.length;
    const avgGraphTokens =
      results.reduce((acc, r) => acc + r.pipeline_3.tokens_total, 0) / total;
    const avgLatency =
      results.reduce((acc, r) => acc + r.pipeline_3.latency_ms, 0) / total;
    const evaluated = results.filter((r) => r.evaluation.judge_pass !== null);
    const evaluatedCount = evaluated.length;
    const judgePasses = evaluated.filter((r) => r.evaluation.judge_pass).length;
    const judgePassRate = evaluatedCount
      ? (judgePasses / evaluatedCount) * 100
      : 0;

    return {
      total,
      avgGraphTokens,
      avgLatency,
      evaluatedCount,
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
      label: "Avg Graph Context",
      value: `${Math.round(stats.avgGraphTokens).toLocaleString()} tok`,
      sub: "Contract 8 Bounded Graph",
      highlight: true,
      bg: "bg-[#DCFCE7]",
    },
    {
      label: "Avg Latency",
      value: `${stats.avgLatency.toFixed(0)}ms`,
      sub: "Agentic GraphRAG (Live Cloud DB)",
      bg: "bg-[#FEF08A]",
    },
    {
      label: "Judge Pass Rate",
      value: stats.evaluatedCount > 0 ? `${stats.judgePassRate.toFixed(0)}%` : "N/A",
      sub:
        stats.evaluatedCount > 0
          ? `${stats.judgePasses}/${stats.evaluatedCount} evaluated passed`
          : "API quota limited / unevaluated",
      highlight: stats.evaluatedCount > 0 && stats.judgePassRate >= 80,
      bg: stats.evaluatedCount > 0 ? "bg-[#FCE7F3]" : "bg-[#F1F5F9]",
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
