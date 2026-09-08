"use client";

import { useState } from "react";
import { runQuery } from "../../lib/api";
import type { PipelineResult } from "../../lib/types";
import PipelineResultCard from "../../components/query/PipelineResultCard";
import type { DecoratedPipeline } from "../../components/query/PipelineResultCard";
import TokenComparisonChart from "../../components/query/TokenComparisonChart";
import LoadingSpinner from "../../components/shared/LoadingSpinner";
import ErrorState from "../../components/shared/ErrorState";

export default function QueryPage() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<{
    pipeline_1: PipelineResult;
    pipeline_2: PipelineResult;
    pipeline_3: PipelineResult;
  } | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;

    setLoading(true);
    setError(null);
    setResults(null);

    try {
      const data = await runQuery(q);
      setResults(data);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  const pipelines: DecoratedPipeline[] | null = results
    ? [
        { ...results.pipeline_1, name: "Pipeline 1 — LLM-only", subtitle: "No retrieval context", accent: "bg-gray-400" },
        { ...results.pipeline_2, name: "Pipeline 2 — Basic RAG", subtitle: "Vector similarity retrieval", accent: "bg-blue-500" },
        { ...results.pipeline_3, name: "Pipeline 3 — GraphRAG", subtitle: "Protocol-mediated graph retrieval", accent: "bg-emerald-500" },
      ]
    : null;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <h1 className="mb-2 text-xl font-bold text-gray-900">Query Comparison</h1>
      <p className="mb-6 text-sm text-gray-500">Run a question through all three pipelines side by side.</p>

      <form onSubmit={handleSubmit} className="mb-8 flex gap-3">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. What methods are used by papers citing the Attention Is All You Need paper?"
          className="flex-1 rounded-lg border border-gray-300 px-4 py-2.5 text-sm text-gray-900 shadow-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="rounded-lg bg-gray-900 px-5 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Running..." : "Run Query"}
        </button>
      </form>

      {loading && <LoadingSpinner label="Running query across all 3 pipelines..." />}
      {error && <ErrorState message={error} hint="Make sure the backend server is running at http://localhost:8000" />}

      {!loading && !error && !results && (
        <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 py-16 text-center text-sm text-gray-400">
          Enter a query and click Run to compare pipeline results.
        </div>
      )}

      {pipelines && (
        <>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {pipelines.map((p) => (
              <PipelineResultCard key={p.name} pipeline={p} />
            ))}
          </div>

          <div className="mt-6">
            <TokenComparisonChart
              pipeline1={results!.pipeline_1}
              pipeline2={results!.pipeline_2}
              pipeline3={results!.pipeline_3}
            />
          </div>
        </>
      )}
    </div>
  );
}
