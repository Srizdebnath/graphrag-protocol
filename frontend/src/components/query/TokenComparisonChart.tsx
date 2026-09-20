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
          <CartesianGrid strokeDasharray="2 2" stroke="#000000" strokeOpacity={0.15} />
          <XAxis dataKey="name" stroke="#000000" tick={{ fill: "#000000", fontWeight: 700, fontSize: 12 }} />
          <YAxis stroke="#000000" tick={{ fill: "#000000", fontWeight: 600, fontSize: 11 }} />
          <Tooltip
            contentStyle={{
              backgroundColor: "#FFFFFF",
              border: "3px solid #000000",
              boxShadow: "4px 4px 0px 0px #000000",
              borderRadius: "8px",
              fontFamily: "monospace",
              fontWeight: "bold",
            }}
          />
          <Legend wrapperStyle={{ fontFamily: "monospace", fontWeight: "bold", fontSize: "12px", paddingTop: "8px" }} />
          <Bar dataKey="answer" name="Total tokens" fill="#74B9FF" stroke="#000000" strokeWidth={2} />
          <Bar dataKey="context" name="Context tokens" fill="#FFE600" stroke="#000000" strokeWidth={2} />
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}
