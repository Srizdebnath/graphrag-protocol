"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { PipelineResult } from "../../lib/types";
import Card from "../shared/Card";

interface TokenComparisonChartProps {
  pipeline1: PipelineResult;
  pipeline2: PipelineResult;
  pipeline3: PipelineResult;
}

export default function TokenComparisonChart({
  pipeline1,
  pipeline2,
  pipeline3,
}: TokenComparisonChartProps) {
  const data = [
    {
      name: "LLM-only",
      answer: pipeline1.tokens_total,
      context: pipeline1.context_tokens ?? 0,
    },
    {
      name: "Basic RAG",
      answer: pipeline2.tokens_total,
      context: pipeline2.context_tokens ?? 0,
    },
    {
      name: "GraphRAG",
      answer: pipeline3.tokens_total,
      context: pipeline3.context_tokens ?? 0,
    },
  ];

  return (
    <Card title="Token Comparison" subtitle="Total and context tokens per pipeline">
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: -8 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Bar dataKey="answer" name="Total tokens" fill="#3b82f6" />
          <Bar dataKey="context" name="Context tokens" fill="#10b981" />
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}
