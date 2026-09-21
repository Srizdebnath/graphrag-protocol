"use client";

import { useEffect, useState } from "react";
import { getBenchmarkResults } from "../../lib/api";
import type { BenchmarkResult } from "../../lib/types";
import MetricsSummary from "../../components/benchmark/MetricsSummary";
import ResultsTable from "../../components/benchmark/ResultsTable";
import AccuracyRadar from "../../components/benchmark/AccuracyRadar";
import CostAccumulationChart from "../../components/benchmark/CostAccumulationChart";
import BenchmarkGallery from "../../components/benchmark/BenchmarkGallery";
import LoadingSpinner from "../../components/shared/LoadingSpinner";
import ErrorState from "../../components/shared/ErrorState";

export default function BenchmarkPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<BenchmarkResult[]>([]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    getBenchmarkResults()
      .then((data) => {
        if (!cancelled) setResults(data);
      })
      .catch((err) => {
        if (!cancelled) setError((err as Error).message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-gray-900">Benchmark Results &amp; Pitch Deck</h1>
        <p className="mt-1 text-sm text-gray-500">
          Rigorous evaluation across single-hop, multi-hop, and global queries comparing GraphRAG against baselines.
        </p>
      </div>

      {/* Visual Pitch Deck Benchmark Gallery */}
      <BenchmarkGallery />

      {/* Live Benchmark Execution Results */}
      <div>
        <h2 className="mb-2 text-lg font-bold text-gray-900">Live Workspace Evaluation</h2>
        <p className="mb-4 text-xs text-gray-500">Real evaluation measured against the active TigerGraph Cloud backend.</p>

        {loading && <LoadingSpinner label="Fetching benchmark results..." />}
        {error && <ErrorState message={error} hint="Ensure the backend server is reachable at https://grip-protocol-backend.onrender.com" />}

        {!loading && !error && results.length === 0 && (
          <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 py-12 text-center text-sm text-gray-400">
            No live benchmark runs cached yet. Trigger an evaluation from the backend or MCP tool.
          </div>
        )}

        {results.length > 0 && (
          <div className="space-y-6">
            <MetricsSummary results={results} />
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <AccuracyRadar results={results} />
              <CostAccumulationChart results={results} />
            </div>
            <ResultsTable results={results} />
          </div>
        )}
      </div>
    </div>
  );
}
