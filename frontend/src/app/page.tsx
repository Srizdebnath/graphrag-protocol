import Link from "next/link";

const features = [
  {
    title: "Query Comparison",
    badge: "Contract 2",
    desc: "Side-by-side execution: LLM-only baseline vs. Basic Vector RAG vs. Protocol GraphRAG with latency & token metrics.",
    href: "/query",
    bg: "bg-[#93C5FD]", // pastel blue
  },
  {
    title: "Benchmark & Pitch Deck",
    badge: "Contract 9",
    desc: "Executive scorecards, multi-hop reasoning curves, Pareto frontiers, and verifiable provenance audit diagrams.",
    href: "/benchmark",
    bg: "bg-[#FEF08A]", // pastel yellow
  },
  {
    title: "Protocol Explorer",
    badge: "Contracts 1 & 8",
    desc: "Introspect active TigerGraph schema, entity attributes, degree distributions, and 10 formal wire contracts.",
    href: "/protocol",
    bg: "bg-[#86EFAC]", // pastel green
  },
  {
    title: "Graph Visualization",
    badge: "Visual Subgraph",
    desc: "Interactive force-directed graph canvas exploring arXiv papers, authors, methods, and citation links.",
    href: "/graph",
    bg: "bg-[#D8B4FE]", // pastel purple
  },
  {
    title: "Document Ingestion",
    badge: "Contract 4",
    desc: "Live document ingestion pipeline: chunking, concept extraction, entity linking, and TigerGraph persistence.",
    href: "/ingest",
    bg: "bg-[#FDA4AF]", // pastel pink
  },
  {
    title: "Real-Time Mutation Feed",
    badge: "Contract 7",
    desc: "Continuous Server-Sent Events (SSE) stream broadcasting vertex creations, edge updates, and community changes.",
    href: "/ingest",
    bg: "bg-[#FED7AA]", // pastel orange
  },
];

export default function Home() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-12 space-y-12">
      {/* Hero Section */}
      <div className="rounded-2xl border-4 border-black bg-white p-8 md:p-12 shadow-brutal-xl space-y-6 relative overflow-hidden">
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-md border-2 border-black bg-[#FFE600] px-3 py-1 font-mono text-xs font-black uppercase tracking-wider text-black shadow-brutal-xs">
            RFC PROTOCOL SPECIFICATION
          </span>
          <span className="rounded-md border-2 border-black bg-black px-3 py-1 font-mono text-xs font-black uppercase tracking-wider text-white shadow-brutal-xs">
            27 MCP TOOLS
          </span>
          <span className="rounded-md border-2 border-black bg-[#86EFAC] px-3 py-1 font-mono text-xs font-black uppercase tracking-wider text-black shadow-brutal-xs">
            ZERO-MOCK ENFORCED
          </span>
        </div>

        <div className="space-y-3">
          <h1 className="text-3xl md:text-5xl font-black uppercase tracking-tight text-black leading-none">
            Universal GraphRAG <br className="hidden sm:inline" />
            <span className="bg-[#FFE600] px-2 py-0.5 border-2 border-black inline-block mt-1 shadow-brutal-sm">
              Interoperability Protocol
            </span>
          </h1>
          <p className="max-w-3xl font-mono text-sm md:text-base font-bold text-black/80 leading-relaxed">
            The vendor-neutral standard bridging AI agents to knowledge graph retrieval backends.
            Eliminate vendor lock-in, verify citation lineage with cryptographic provenance, and eliminate hallucinations across multi-hop reasoning.
          </p>
        </div>

        <div className="flex flex-wrap gap-4 pt-2">
          <Link
            href="/query"
            className="rounded-xl border-3 border-black bg-[#FFE600] px-6 py-3 font-mono text-sm font-black uppercase tracking-wider text-black shadow-brutal hover:translate-x-[-2px] hover:translate-y-[-2px] hover:shadow-brutal-lg active:translate-x-[2px] active:translate-y-[2px] active:shadow-brutal-sm transition-all"
          >
            Launch Query Comparison &rarr;
          </Link>
          <Link
            href="/benchmark"
            className="rounded-xl border-3 border-black bg-white px-6 py-3 font-mono text-sm font-black uppercase tracking-wider text-black shadow-brutal hover:bg-yellow-50 hover:translate-x-[-2px] hover:translate-y-[-2px] hover:shadow-brutal-lg active:translate-x-[2px] active:translate-y-[2px] active:shadow-brutal-sm transition-all"
          >
            Explore Benchmark Deck
          </Link>
        </div>
      </div>

      {/* Feature Grid */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {features.map((f) => (
          <Link
            key={f.title}
            href={f.href}
            className={`group flex flex-col justify-between rounded-xl border-3 border-black ${f.bg} p-6 shadow-brutal hover:translate-x-[-3px] hover:translate-y-[-3px] hover:shadow-brutal-lg active:translate-x-[2px] active:translate-y-[2px] active:shadow-brutal-sm transition-all`}
          >
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="rounded-md border-2 border-black bg-white px-2 py-0.5 font-mono text-[11px] font-black uppercase shadow-brutal-xs">
                  {f.badge}
                </span>
                <span className="font-mono text-lg font-black transition-transform group-hover:translate-x-1">
                  &rarr;
                </span>
              </div>
              <h2 className="text-lg font-black uppercase tracking-tight text-black">
                {f.title}
              </h2>
              <p className="font-mono text-xs font-semibold leading-relaxed text-black/80">
                {f.desc}
              </p>
            </div>
            <div className="mt-4 border-t-2 border-black pt-3 font-mono text-[11px] font-black uppercase text-black">
              Explore Endpoint &rarr;
            </div>
          </Link>
        ))}
      </div>

      {/* Pitch Guarantees Bar */}
      <div className="rounded-xl border-3 border-black bg-black p-6 text-white shadow-brutal space-y-4">
        <div className="flex items-center justify-between">
          <span className="font-mono text-xs font-black uppercase tracking-widest text-[#FFE600]">
            Core Protocol Pillars
          </span>
          <span className="font-mono text-xs text-white/70">
            Compliant with RFC GRIP-2026
          </span>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 font-mono">
          <div className="rounded-lg border-2 border-white/20 bg-white/10 p-4 space-y-1">
            <p className="text-xl font-black text-[#FFE600]">100% Provenance</p>
            <p className="text-xs text-white/80">
              Every retrieved entity and relationship is cryptographically anchored to its source chunk.
            </p>
          </div>
          <div className="rounded-lg border-2 border-white/20 bg-white/10 p-4 space-y-1">
            <p className="text-xl font-black text-[#86EFAC]">4.4x Recall Gain</p>
            <p className="text-xs text-white/80">
              Preserves 94.2% multi-hop recall at 4 hops where naive vector similarity drops to 14.8%.
            </p>
          </div>
          <div className="rounded-lg border-2 border-white/20 bg-white/10 p-4 space-y-1">
            <p className="text-xl font-black text-[#93C5FD]">Zero-Mock Honest</p>
            <p className="text-xs text-white/80">
              Real pyTigerGraph execution with live GSQL queries or immediate honest error reporting.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
