"use client";

import { useState } from "react";
import Card from "../shared/Card";

interface BenchmarkGraphic {
  id: string;
  title: string;
  subtitle: string;
  filename: string;
}

const GRAPHICS: BenchmarkGraphic[] = [
  {
    id: "pipeline",
    title: "3-Pipeline Comparison",
    subtitle: "Answer accuracy, hallucination reduction, and multi-hop recall",
    filename: "/benchmarks/pipeline_comparison.svg",
  },
  {
    id: "multi-hop",
    title: "Multi-Hop Reasoning",
    subtitle: "Accuracy degradation across 1 to 4 graph traversal hops",
    filename: "/benchmarks/multi_hop_reasoning.svg",
  },
  {
    id: "pareto",
    title: "Pareto Frontier",
    subtitle: "End-to-end query latency vs answer precision trade-off",
    filename: "/benchmarks/latency_vs_accuracy.svg",
  },
  {
    id: "provenance",
    title: "Provenance & Audit",
    subtitle: "Zero-hallucination guarantee via Contract 5 citation verification",
    filename: "/benchmarks/provenance_audit.svg",
  },
  {
    id: "scorecard",
    title: "Executive Scorecard",
    subtitle: "Key pitch metrics and relative gains over basic vector RAG",
    filename: "/benchmarks/benchmark_scorecard.svg",
  },
];

export default function BenchmarkGallery() {
  const [selectedId, setSelectedId] = useState<string>("pipeline");
  const selected = GRAPHICS.find((g) => g.id === selectedId) || GRAPHICS[0];

  return (
    <Card
      title="Benchmark Graphics &amp; Pitch Deck"
      subtitle="Visual benchmarks comparing GraphRAG Protocol against Basic Vector RAG and LLM-only baselines"
    >
      <div className="flex flex-wrap gap-2 mb-6 border-b border-gray-100 pb-4">
        {GRAPHICS.map((g) => {
          const active = g.id === selectedId;
          return (
            <button
              key={g.id}
              onClick={() => setSelectedId(g.id)}
              className={`rounded-lg px-3.5 py-2 text-xs font-semibold transition-all ${
                active
                  ? "bg-gray-900 text-white shadow-sm"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200 hover:text-gray-900"
              }`}
            >
              {g.title}
            </button>
          );
        })}
      </div>

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-gray-900">{selected.title}</h3>
            <p className="text-xs text-gray-500">{selected.subtitle}</p>
          </div>
          <a
            href={selected.filename}
            download={selected.filename.split("/").pop()}
            className="inline-flex items-center gap-1.5 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 shadow-sm transition-colors"
          >
            <span>Download SVG</span>
            <span aria-hidden="true">&darr;</span>
          </a>
        </div>

        <div className="relative rounded-xl overflow-hidden border border-gray-800 bg-slate-950 p-2 shadow-2xl">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={selected.filename}
            alt={selected.title}
            className="w-full h-auto rounded-lg object-contain"
          />
        </div>
      </div>
    </Card>
  );
}
