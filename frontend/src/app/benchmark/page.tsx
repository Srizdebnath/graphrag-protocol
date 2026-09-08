"use client";

import { useEffect, useState } from "react";
import { getBenchmarkResults } from "../../lib/api";
import type { BenchmarkResult } from "../../lib/types";
import MetricsSummary from "../../components/benchmark/MetricsSummary";
import ResultsTable from "../../components/benchmark/ResultsTable";
import AccuracyRadar from "../../components/benchmark/AccuracyRadar";
import CostAccumulationChart from "../../components/benchmark/CostAccumulationChart";
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
    <div className="mx-auto max-w-7xl px-4 py-8">
      <h1 className="mb-2 text-xl font-bold text-gray-900">Benchmark Results</h1>
      <p className="mb-6 text-sm text-gray-500">Full evaluation across all queries.</p>

      {loading && <LoadingSpinner label="Fetching benchmark results..." />}
      {error && <ErrorState message={error} hint="Make sure the backend server is running at http://localhost:8000" />}

      {!loading && !error && results.length === 0 && (
        <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 py-16 text-center text-sm text-gray-400">
          No benchmark results available yet. Run the benchmark from the backend first.
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
  );
}
