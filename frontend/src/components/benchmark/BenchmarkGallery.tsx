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
      <div className="flex flex-wrap gap-2.5 mb-6 border-b-3 border-black pb-5">
        {GRAPHICS.map((g) => {
          const active = g.id === selectedId;
          return (
            <button
              key={g.id}
              onClick={() => setSelectedId(g.id)}
              className={`rounded-lg border-2 border-black px-4 py-2 font-mono text-xs font-black uppercase tracking-wider transition-all ${
                active
                  ? "bg-[#FFE600] text-black shadow-brutal-sm translate-x-[-1px] translate-y-[-1px]"
                  : "bg-white text-black shadow-brutal-xs hover:bg-yellow-100 hover:translate-x-[-2px] hover:translate-y-[-2px] active:translate-x-[1px] active:translate-y-[1px]"
              }`}
            >
              {g.title}
            </button>
          );
        })}
      </div>

      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h3 className="font-mono text-base font-black uppercase text-black">{selected.title}</h3>
            <p className="font-mono text-xs font-bold text-black/70">{selected.subtitle}</p>
          </div>
          <a
            href={selected.filename}
            download={selected.filename.split("/").pop()}
            className="inline-flex items-center gap-2 self-start rounded-lg border-2 border-black bg-black px-4 py-2 font-mono text-xs font-black uppercase tracking-wider text-white shadow-brutal hover:bg-[#FFE600] hover:text-black hover:translate-x-[-2px] hover:translate-y-[-2px] hover:shadow-brutal-lg active:translate-x-[2px] active:translate-y-[2px] active:shadow-brutal-sm transition-all"
          >
            <span>Download SVG</span>
            <span aria-hidden="true">&darr;</span>
          </a>
        </div>

        <div className="relative rounded-2xl border-4 border-black bg-slate-950 p-3 shadow-brutal-xl">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={selected.filename}
            alt={selected.title}
            className="w-full h-auto rounded-xl object-contain"
          />
        </div>
      </div>
    </Card>
  );
}
