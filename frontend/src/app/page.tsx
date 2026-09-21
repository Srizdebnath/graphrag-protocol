import Link from "next/link";
import CodeBlock from "../components/shared/CodeBlock";
import Badge from "../components/shared/Badge";
import { Terminal, Zap, ArrowRight } from "lucide-react";

export default function Home() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-12 space-y-16">
      {/* Hero Section */}
      <div className="rounded-2xl border-4 border-black bg-white p-8 md:p-12 shadow-brutal-xl space-y-8 relative overflow-hidden">
        {/* Top Badges */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-md border-2 border-black bg-[#FFE600] px-3 py-1 font-mono text-xs font-black uppercase tracking-wider text-black shadow-brutal-xs">
            RFC PROTOCOL SPECIFICATION
          </span>
          <span className="rounded-md border-2 border-black bg-black px-3 py-1 font-mono text-xs font-black uppercase tracking-wider text-[#55EFC4] shadow-brutal-xs">
            v0.5.0 ON PYPI
          </span>
          <span className="rounded-md border-2 border-black bg-[#55EFC4] px-3 py-1 font-mono text-xs font-black uppercase tracking-wider text-black shadow-brutal-xs">
            50 MCP TOOLS
          </span>
          <span className="rounded-md border-2 border-black bg-[#A29BFE] px-3 py-1 font-mono text-xs font-black uppercase tracking-wider text-black shadow-brutal-xs">
            20 FORMAL CONTRACTS
          </span>
          <span className="rounded-md border-2 border-black bg-[#FDA4AF] px-3 py-1 font-mono text-xs font-black uppercase tracking-wider text-black shadow-brutal-xs">
            PRODUCTION READY
          </span>
        </div>

        {/* Hero Title & Subtitle */}
        <div className="space-y-4">
          <h1 className="text-3xl sm:text-5xl md:text-6xl font-black uppercase tracking-tight text-black leading-none">
            Universal GraphRAG <br className="hidden sm:inline" />
            <span className="bg-[#FFE600] px-3 py-1 border-3 border-black inline-block mt-2 shadow-brutal">
              Interoperability Protocol
            </span>
          </h1>
          <p className="max-w-3xl font-mono text-sm md:text-base font-bold text-black/80 leading-relaxed">
            The open wire standard connecting AI agents to enterprise knowledge graphs.
            Eliminate vendor lock-in across TigerGraph and Neo4j, verify citation lineage with cryptographic provenance,
            and conquer multi-hop reasoning without prompt hallucination.
          </p>
        </div>

        {/* Quick CTA Buttons */}
        <div className="flex flex-wrap gap-4 pt-2">
          <Link
            href="/connect"
            className="flex items-center gap-2 rounded-xl border-3 border-black bg-[#55EFC4] px-6 py-3.5 font-mono text-sm font-black uppercase tracking-wider text-black shadow-brutal hover:translate-x-[-2px] hover:translate-y-[-2px] hover:shadow-brutal-lg active:translate-x-[2px] active:translate-y-[2px] active:shadow-brutal-sm transition-all"
          >
            <span>Connect to Your IDE (Guides) &rarr;</span>
          </Link>
          <Link
            href="/docs"
            className="flex items-center gap-2 rounded-xl border-3 border-black bg-[#FFE600] px-6 py-3.5 font-mono text-sm font-black uppercase tracking-wider text-black shadow-brutal hover:translate-x-[-2px] hover:translate-y-[-2px] hover:shadow-brutal-lg active:translate-x-[2px] active:translate-y-[2px] active:shadow-brutal-sm transition-all"
          >
            <span>Protocol Documentation</span>
          </Link>
          <Link
            href="/protocol"
            className="flex items-center gap-2 rounded-xl border-3 border-black bg-white px-6 py-3.5 font-mono text-sm font-black uppercase tracking-wider text-black shadow-brutal hover:bg-yellow-50 hover:translate-x-[-2px] hover:translate-y-[-2px] hover:shadow-brutal-lg active:translate-x-[2px] active:translate-y-[2px] active:shadow-brutal-sm transition-all"
          >
            <span>Explore 20 Contracts</span>
          </Link>
        </div>

        {/* Quick Install Banner */}
        <div className="rounded-xl border-3 border-black bg-[#F7F5EE] p-4 shadow-brutal-xs space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-mono text-xs font-black uppercase text-black flex items-center gap-1.5">
              <Terminal className="h-4 w-4" /> Quick Install:
            </span>
            <span className="font-mono text-[11px] font-bold text-black/60">
              pip / pipx package index
            </span>
          </div>
          <CodeBlock
            code="pip install -U 'grip-protocol[tigergraph,llm]'"
            language="bash"
          />
        </div>
      </div>

      {/* Agentic IDE Setup Preview Strip */}
      <div className="rounded-2xl border-4 border-black bg-[#FFE600] p-8 shadow-brutal-xl space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <Zap className="h-5 w-5 text-black" />
              <h2 className="text-xl md:text-2xl font-black uppercase tracking-tight text-black">
                One-Click IDE &amp; Agent Integrations
              </h2>
            </div>
            <p className="font-mono text-xs md:text-sm font-bold text-black/80 mt-1">
              Step-by-step setup guides to empower your AI developers and coding agents.
            </p>
          </div>
          <Link
            href="/connect"
            className="inline-flex items-center gap-1.5 rounded-lg border-2 border-black bg-black px-4 py-2 font-mono text-xs font-black uppercase tracking-wider text-white shadow-brutal-xs hover:bg-neutral-800 transition-all"
          >
            <span>View All 8 Guides</span>
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>

        {/* Quick IDE Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { name: "Claude Code", badge: "CLI Agent", id: "claude-code" },
            { name: "Cursor IDE", badge: "Composer", id: "cursor" },
            { name: "Cline", badge: "VS Code", id: "cline" },
            { name: "OpenCode", badge: "Open Source", id: "opencode" },
          ].map((ide) => (
            <Link
              key={ide.name}
              href="/connect"
              className="rounded-xl border-3 border-black bg-white p-4 shadow-brutal hover:translate-x-[-2px] hover:translate-y-[-2px] hover:shadow-brutal-lg transition-all space-y-1 block"
            >
              <span className="font-mono text-[10px] font-black uppercase text-black/50 block">
                {ide.badge}
              </span>
              <h3 className="font-mono text-sm font-black uppercase text-black">
                {ide.name}
              </h3>
              <p className="font-mono text-[11px] font-bold text-black/70">
                Setup guide &rarr;
              </p>
            </Link>
          ))}
        </div>
      </div>

      {/* 6 Core Protocol Invariants Grid */}
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl md:text-3xl font-black uppercase tracking-tight text-black">
            The 6 Pillars of the GRIP Protocol
          </h2>
          <p className="font-mono text-xs md:text-sm font-bold text-black/70">
            Engineered to replace fragmented graph retrieval with a unified, verifiable standard.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[
            {
              contract: "Contract 1",
              title: "7 Standard Retrieval Modalities",
              desc: "Auto-routed search, k-hop local expansion, global community summaries, hybrid score fusion, and shortest paths without writing GSQL or Cypher.",
              bg: "bg-[#93C5FD]",
            },
            {
              contract: "Contract 2",
              title: "Canonical Subgraph Envelope",
              desc: "Every query returns a deterministic JSON envelope with typed entities, relationships, paths, communities, and microsecond telemetry.",
              bg: "bg-[#FEF08A]",
            },
            {
              contract: "Contract 5",
              title: "Cryptographic Provenance",
              desc: "Every assertion is linked to source chunk hashes and traversal steps. Visited-not-cited leakage auditing ensures 100% grounded answers.",
              bg: "bg-[#86EFAC]",
            },
            {
              contract: "Contract 6",
              title: "Multi-Backend Federation",
              desc: "Simultaneous query fan-out across hybrid TigerGraph + Neo4j clusters, merged via Reciprocal Rank Fusion (RRF).",
              bg: "bg-[#D8B4FE]",
            },
            {
              contract: "Contract 8",
              title: "Dynamic Token Bounding",
              desc: "Prevents prompt overflow by dynamically compacting large graph neighborhoods into bounded Markdown within the caller's token budget.",
              bg: "bg-[#FDA4AF]",
            },
            {
              contract: "Contract 10",
              title: "5-Tier RBAC Security",
              desc: "Cryptographically signed HMAC capability tokens prevent unauthorized prompt injections from executing destructive writes.",
              bg: "bg-[#FED7AA]",
            },
          ].map((pillar) => (
            <div
              key={pillar.title}
              className={`rounded-xl border-3 border-black ${pillar.bg} p-6 shadow-brutal space-y-3`}
            >
              <span className="rounded bg-black px-2 py-0.5 font-mono text-[10px] font-black text-[#FFE600]">
                {pillar.contract}
              </span>
              <h3 className="text-base font-black uppercase tracking-tight text-black">
                {pillar.title}
              </h3>
              <p className="font-mono text-xs font-semibold text-black/80 leading-relaxed">
                {pillar.desc}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Benchmark Visual Showcase (Featuring the new neo-brutalist SVGs!) */}
      <div className="rounded-2xl border-4 border-black bg-white p-8 shadow-brutal-xl space-y-8">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <Badge color="green">EMPIRICAL BENCHMARKS</Badge>
              <Badge color="purple">TIGERGRAPH SAVANNA</Badge>
            </div>
            <h2 className="text-2xl md:text-3xl font-black uppercase tracking-tight text-black mt-2">
              Empirical Performance Evidence
            </h2>
            <p className="font-mono text-xs md:text-sm font-bold text-black/70">
              Evaluated on 49,656 vertices and 79,044 edges from the ArXiv graph using Gemini 2.5 Flash.
            </p>
          </div>
          <Link
            href="/benchmark"
            className="inline-flex items-center gap-1.5 rounded-lg border-2 border-black bg-[#FFE600] px-4 py-2 font-mono text-xs font-black uppercase tracking-wider text-black shadow-brutal-xs hover:bg-yellow-300 transition-all"
          >
            <span>View Full Deck</span>
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>

        {/* Display the new Neo-Brutalist SVG directly! */}
        <div className="rounded-xl border-3 border-black overflow-hidden shadow-brutal">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/benchmarks/pipeline_comparison.svg"
            alt="3-Pipeline Performance Comparison"
            className="w-full h-auto"
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="rounded-xl border-3 border-black overflow-hidden shadow-brutal">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/benchmarks/multi_hop_reasoning.svg"
              alt="Multi-hop Reasoning Cliff"
              className="w-full h-auto"
            />
          </div>
          <div className="rounded-xl border-3 border-black overflow-hidden shadow-brutal">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/benchmarks/latency_vs_accuracy.svg"
              alt="Pareto Frontier Latency vs Accuracy"
              className="w-full h-auto"
            />
          </div>
        </div>
      </div>

      {/* Bottom CTA Banner */}
      <div className="rounded-2xl border-4 border-black bg-[#55EFC4] p-8 md:p-12 shadow-brutal-xl flex flex-col sm:flex-row items-center justify-between gap-6">
        <div className="space-y-2">
          <h3 className="text-2xl md:text-4xl font-black uppercase tracking-tight text-black">
            Ready to Build With GRIP?
          </h3>
          <p className="font-mono text-xs md:text-sm font-bold text-black/80 max-w-xl">
            Download the official wheel from PyPI, connect to your local or cloud knowledge graph, and equip your AI agents with 50 standardized GraphRAG tools.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <Link
            href="/connect"
            className="rounded-xl border-3 border-black bg-[#FFE600] px-6 py-3 font-mono text-sm font-black uppercase text-black shadow-brutal hover:bg-yellow-300 transition-all"
          >
            Connect to IDE &rarr;
          </Link>
          <Link
            href="/docs"
            className="rounded-xl border-3 border-black bg-white px-6 py-3 font-mono text-sm font-black uppercase text-black shadow-brutal hover:bg-neutral-100 transition-all"
          >
            Read the Docs
          </Link>
        </div>
      </div>
    </div>
  );
}
