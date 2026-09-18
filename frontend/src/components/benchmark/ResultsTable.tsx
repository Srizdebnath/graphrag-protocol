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
        className="cursor-pointer select-none px-3 py-2 text-left text-xs font-semibold text-gray-600 hover:text-gray-900"
        onClick={() => toggle(key)}
      >
        {label}
        {arrow}
      </th>
    );
  }

  return (
    <Card title="Results" subtitle={`${results.length} queries`}>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-gray-200 bg-gray-50">
            <tr>
              {header("Query", "query")}
              {header("Category", "category")}
              {header("LLM-only", "tokens_p1")}
              {header("Basic RAG", "tokens_p2")}
              {header("GraphRAG", "tokens_p3")}
              {header("Latency", "latency")}
              {header("Judge", "judge")}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {sorted.map((r) => (
              <tr key={r.query_id} className="hover:bg-gray-50/50">
                <td className="max-w-[260px] truncate px-3 py-2 text-gray-800">{r.query}</td>
                <td className="px-3 py-2">
                  <Badge color="blue">{r.category}</Badge>
                </td>
                <td className="px-3 py-2 font-mono text-xs text-gray-700">
                  {r.pipeline_1.tokens_total.toLocaleString()}
                </td>
                <td className="px-3 py-2 font-mono text-xs text-gray-700">
                  {r.pipeline_2.tokens_total.toLocaleString()}
                </td>
                <td className="px-3 py-2 font-mono text-xs text-gray-700">
                  {r.pipeline_3.tokens_total.toLocaleString()}
                </td>
                <td className="px-3 py-2 font-mono text-xs text-gray-700">
                  {r.pipeline_3.latency_ms.toFixed(0)}ms
                </td>
                <td className="px-3 py-2">
                  {r.evaluation.judge_pass === null ? (
                    <Badge color="gray">NOT EVALUATED</Badge>
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
