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
    <div className="mx-auto max-w-7xl px-4 py-8 space-y-8">
      <div>
        <h1 className="text-2xl font-black uppercase tracking-tight text-black">Query Comparison</h1>
        <p className="mt-1 font-mono text-xs font-bold text-black/70">
          Contract 2 Subgraph Context // Run queries across 3 pipelines side by side.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-3">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. What methods are used by papers citing the Attention Is All You Need paper?"
          className="flex-1 rounded-xl border-3 border-black bg-white px-4 py-3 font-mono text-sm font-semibold text-black shadow-brutal placeholder:text-black/40 focus:outline-none focus:shadow-brutal-lg transition-all"
        />
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="rounded-xl border-3 border-black bg-[#FFE600] px-8 py-3 font-mono text-sm font-black uppercase tracking-wider text-black shadow-brutal hover:translate-x-[-2px] hover:translate-y-[-2px] hover:shadow-brutal-lg active:translate-x-[2px] active:translate-y-[2px] active:shadow-brutal-sm disabled:cursor-not-allowed disabled:opacity-50 transition-all"
        >
          {loading ? "Running..." : "Run Query"}
        </button>
      </form>

      {loading && <LoadingSpinner label="Running query across all 3 pipelines..." />}
      {error && <ErrorState message={error} hint="Ensure the backend server is reachable at https://grip-protocol-backend.onrender.com" />}

      {!loading && !error && !results && (
        <div className="rounded-xl border-3 border-dashed border-black bg-white/70 py-16 text-center font-mono text-xs font-black uppercase tracking-wider text-black/60 shadow-brutal-sm">
          Enter a question above and click Run Query to compare LLM-only, Vector RAG, and Protocol GraphRAG.
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
