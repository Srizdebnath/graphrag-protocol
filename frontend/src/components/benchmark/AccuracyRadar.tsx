"use client";

import { useMemo } from "react";
import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from "recharts";
import type { BenchmarkResult } from "../../lib/types";
import Card from "../shared/Card";

interface AccuracyRadarProps {
  results: BenchmarkResult[];
}

interface MetricPoint {
  metric: string;
  pipeline_1: number;
  pipeline_2: number;
  pipeline_3: number;
}

function normalise(values: number[], min: number, max: number): number[] {
  const range = max - min || 1;
  return values.map((v) => ((v - min) / range) * 100);
}

export default function AccuracyRadar({ results }: AccuracyRadarProps) {
  const data: MetricPoint[] = useMemo(() => {
    if (results.length === 0) return [];

    const n = results.length;

    const avgAccuracy = [
      results.reduce((s, r) => s + (r.evaluation.judge_pass ? 1 : 0), 0) / n,
      results.reduce((s, r) => s + (r.evaluation.bertscore_f1 * 100), 0) / n,
      results.reduce((s, r) => s + (r.evaluation.judge_pass ? 1 : 0), 0) / n,
    ];

    const avgTokens = [
      results.reduce((s, r) => s + r.pipeline_1.tokens_total, 0) / n,
      results.reduce((s, r) => s + r.pipeline_2.tokens_total, 0) / n,
      results.reduce((s, r) => s + r.pipeline_3.tokens_total, 0) / n,
    ];

    const avgLatency = [
      results.reduce((s, r) => s + r.pipeline_1.latency_ms, 0) / n,
      results.reduce((s, r) => s + r.pipeline_2.latency_ms, 0) / n,
      results.reduce((s, r) => s + r.pipeline_3.latency_ms, 0) / n,
    ];

    const avgProvenance = [
      results.reduce((s, r) => s + (r.pipeline_1.provenance?.completeness_score ?? 0), 0) / n * 100,
      results.reduce((s, r) => s + (r.pipeline_2.provenance?.completeness_score ?? 0), 0) / n * 100,
      results.reduce((s, r) => s + (r.pipeline_3.provenance?.completeness_score ?? 0), 0) / n * 100,
    ];

    // Invert tokens & latency so lower is better → higher radar value
    const invTokens = normalise(avgTokens.map((v) => -v), -Math.max(...avgTokens), 0);
    const invLatency = normalise(avgLatency.map((v) => -v), -Math.max(...avgLatency), 0);

    const metrics: [string, number[]][] = [
      ["Accuracy", avgAccuracy],
      ["Tokens", invTokens],
      ["Latency", invLatency],
      ["Provenance", avgProvenance],
    ];

    return metrics.map(([metric, vals]) => ({
      metric,
      pipeline_1: Math.round(vals[0]),
      pipeline_2: Math.round(vals[1]),
      pipeline_3: Math.round(vals[2]),
    }));
  }, [results]);

  if (data.length === 0) {
    return (
      <Card title="Pipeline Radar" subtitle="Accuracy / tokens / latency / provenance">
        <p className="py-6 text-center text-sm text-gray-400">No data available</p>
      </Card>
    );
  }

  return (
    <Card title="Pipeline Radar" subtitle="Accuracy / tokens / latency / provenance">
      <ResponsiveContainer width="100%" height={340}>
        <RadarChart data={data}>
          <PolarGrid />
          <PolarAngleAxis dataKey="metric" tick={{ fontSize: 12 }} />
          <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} />
          <Radar name="LLM-only" dataKey="pipeline_1" stroke="#94a3b8" fill="#94a3b8" fillOpacity={0.15} />
          <Radar name="Basic RAG" dataKey="pipeline_2" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.15} />
          <Radar name="GraphRAG" dataKey="pipeline_3" stroke="#10b981" fill="#10b981" fillOpacity={0.25} />
          <Legend />
          <Tooltip />
        </RadarChart>
      </ResponsiveContainer>
    </Card>
  );
}
