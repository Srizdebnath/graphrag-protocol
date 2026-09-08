"use client";

import { useMemo } from "react";
import {
  Line,
  LineChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { BenchmarkResult } from "../../lib/types";
import Card from "../shared/Card";

interface CostAccumulationChartProps {
  results: BenchmarkResult[];
}

interface AccumPoint {
  query: number;
  pipeline_1: number;
  pipeline_2: number;
  pipeline_3: number;
  savings: number;
}

export default function CostAccumulationChart({ results }: CostAccumulationChartProps) {
  const data: AccumPoint[] = useMemo(() => {
    const acc: AccumPoint[] = [];
    let cum1 = 0;
    let cum2 = 0;
    let cum3 = 0;

    results.forEach((r, i) => {
      cum1 += r.pipeline_1.tokens_total;
      cum2 += r.pipeline_2.tokens_total;
      cum3 += r.pipeline_3.tokens_total;
      acc.push({
        query: i + 1,
        pipeline_1: cum1,
        pipeline_2: cum2,
        pipeline_3: cum3,
        savings: cum1 - cum3,
      });
    });

    return acc;
  }, [results]);

  if (data.length === 0) {
    return (
      <Card title="Cumulative Cost" subtitle="Tokens accumulated per query">
        <p className="py-6 text-center text-sm text-gray-400">No data available</p>
      </Card>
    );
  }

  return (
    <Card title="Cumulative Cost" subtitle="Tokens accumulated per query — lower is better">
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: -8 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="query" label={{ value: "Query #", position: "bottom", offset: -4, fontSize: 12 }} />
          <YAxis tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}k`} />
          <Tooltip formatter={(v) => Number(v).toLocaleString()} />
          <Legend />
          <Line type="monotone" dataKey="pipeline_1" name="LLM-only" stroke="#94a3b8" dot={false} strokeWidth={2} />
          <Line type="monotone" dataKey="pipeline_2" name="Basic RAG" stroke="#3b82f6" dot={false} strokeWidth={2} />
          <Line type="monotone" dataKey="pipeline_3" name="GraphRAG" stroke="#10b981" dot={false} strokeWidth={2} />
          <Line type="monotone" dataKey="savings" name="Savings (LLM-only − GraphRAG)" stroke="#f59e0b" dot={false} strokeWidth={2} strokeDasharray="5 5" />
        </LineChart>
      </ResponsiveContainer>
    </Card>
  );
}
