"use client";

import { useMemo, useState } from "react";
import type { BenchmarkResult } from "../../lib/types";
import Badge from "../shared/Badge";
import Card from "../shared/Card";

type SortKey = "query" | "category" | "tokens_p1" | "tokens_p2" | "tokens_p3" | "latency" | "judge";

interface ResultsTableProps {
  results: BenchmarkResult[];
}

export default function ResultsTable({ results }: ResultsTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("query");
  const [sortAsc, setSortAsc] = useState(true);

  const sorted = useMemo(() => {
    const copy = [...results];
    copy.sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case "query":
          cmp = a.query.localeCompare(b.query);
          break;
        case "category":
          cmp = a.category.localeCompare(b.category);
          break;
        case "tokens_p1":
          cmp = a.pipeline_1.tokens_total - b.pipeline_1.tokens_total;
          break;
        case "tokens_p2":
          cmp = a.pipeline_2.tokens_total - b.pipeline_2.tokens_total;
          break;
        case "tokens_p3":
          cmp = a.pipeline_3.tokens_total - b.pipeline_3.tokens_total;
          break;
        case "latency":
          cmp = a.pipeline_3.latency_ms - b.pipeline_3.latency_ms;
          break;
        case "judge":
          cmp = (a.evaluation.judge_pass ? 1 : 0) - (b.evaluation.judge_pass ? 1 : 0);
          break;
      }
      return sortAsc ? cmp : -cmp;
    });
    return copy;
  }, [results, sortKey, sortAsc]);

  function toggle(key: SortKey) {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(true);
    }
  }

  function header(label: string, key: SortKey) {
    const arrow = sortKey === key ? (sortAsc ? " \u25B2" : " \u25BC") : "";
    return (
      <th
        className="cursor-pointer select-none px-3.5 py-3 text-left font-mono text-xs font-black uppercase tracking-wider text-black hover:bg-yellow-400 transition-colors"
        onClick={() => toggle(key)}
      >
        {label}
        {arrow}
      </th>
    );
  }

  return (
    <Card title="Benchmark Execution Results" subtitle={`${results.length} total test queries evaluated`}>
      <div className="overflow-x-auto rounded-lg border-2 border-black shadow-brutal-sm">
        <table className="w-full text-left text-sm">
          <thead className="border-b-3 border-black bg-[#FFE600]">
            <tr>
              {header("Query", "query")}
              {header("Category", "category")}
              {header("LLM Tokens", "tokens_p1")}
              {header("Basic RAG Tokens", "tokens_p2")}
              {header("GraphRAG Tokens", "tokens_p3")}
              {header("Latency", "latency")}
              {header("Judge Verdict", "judge")}
            </tr>
          </thead>
          <tbody className="divide-y-2 divide-black/10 bg-white font-mono text-xs">
            {sorted.map((r) => (
              <tr key={r.query_id} className="hover:bg-yellow-50/80 transition-colors">
                <td className="max-w-[260px] truncate px-3.5 py-2.5 font-bold text-black" title={r.query}>{r.query}</td>
                <td className="px-3.5 py-2.5">
                  <Badge color="blue">{r.category}</Badge>
                </td>
                <td className="px-3.5 py-2.5 font-bold text-black/80">
                  {r.pipeline_1.tokens_total.toLocaleString()}
                </td>
                <td className="px-3.5 py-2.5 font-bold text-black/80">
                  {r.pipeline_2.tokens_total.toLocaleString()}
                </td>
                <td className="px-3.5 py-2.5 font-black text-black">
                  {r.pipeline_3.tokens_total.toLocaleString()}
                </td>
                <td className="px-3.5 py-2.5 font-bold text-black">
                  {r.pipeline_3.latency_ms.toFixed(0)}ms
                </td>
                <td className="px-3.5 py-2.5">
                  {r.evaluation.judge_pass === null ? (
                    <Badge color="gray">UNEVALUATED</Badge>
                  ) : (
                    <Badge color={r.evaluation.judge_pass ? "green" : "red"}>
                      {r.evaluation.judge_pass ? "PASS" : "FAIL"}
                    </Badge>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
