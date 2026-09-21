"use client";

import { useState } from "react";
import CodeBlock from "../../components/shared/CodeBlock";
import Badge from "../../components/shared/Badge";
import { BookOpen, Search } from "lucide-react";

interface DocSection {
  id: string;
  title: string;
  category: string;
}

const SECTIONS: DocSection[] = [
  { id: "overview", title: "1. Overview & Architecture", category: "Introduction" },
  { id: "quickstart", title: "2. Installation & Quickstart", category: "Getting Started" },
  { id: "cli-reference", title: "3. CLI Command Reference", category: "Reference" },
  { id: "tool-surface", title: "4. Complete 50-Tool Surface", category: "MCP Server" },
  { id: "transports", title: "5. Transport Modes (stdio, HTTP, SSE)", category: "MCP Server" },
  { id: "backends", title: "6. Backends (TigerGraph, Neo4j, SQLite)", category: "Adapters" },
  { id: "agent-harness", title: "7. Autonomous Agentic Harness", category: "Agentic AI" },
  { id: "security-rbac", title: "8. RBAC & HMAC Capability Tokens", category: "Security" },
  { id: "benchmarking", title: "9. Benchmarking & Metrics", category: "Evaluation" },
  { id: "deployment", title: "10. Production Deployment & Docker", category: "DevOps" },
];

export default function DocsPage() {
  const [activeSection, setActiveSection] = useState<string>("overview");
  const [searchQuery, setSearchQuery] = useState<string>("");

  const filteredSections = SECTIONS.filter(
    (s) =>
      s.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.category.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 space-y-8">
      {/* Docs Header Banner */}
      <div className="rounded-2xl border-4 border-black bg-white p-8 shadow-brutal-xl space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge color="green">SPECIFICATION v0.4.0</Badge>
          <Badge color="amber">RFC STANDARD</Badge>
          <Badge color="purple">20 WIRE CONTRACTS</Badge>
        </div>
        <h1 className="text-3xl md:text-5xl font-black uppercase tracking-tight text-black">
          GRIP Protocol Documentation
        </h1>
        <p className="max-w-3xl font-mono text-sm md:text-base font-bold text-black/80 leading-relaxed">
          The comprehensive developer and architecture documentation for the Universal
          GraphRAG Interoperability Protocol.
        </p>

        {/* Search bar */}
        <div className="relative max-w-md pt-2">
          <Search className="absolute left-3.5 top-5 h-4 w-4 text-black/60" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search documentation (e.g. tools, transports, tigergraph)..."
            className="w-full rounded-xl border-3 border-black bg-[#F7F5EE] py-2.5 pl-10 pr-4 font-mono text-xs font-bold text-black placeholder:text-black/50 shadow-brutal-xs focus:outline-none focus:bg-white transition-all"
          />
        </div>
      </div>

      {/* Main Content Layout: Sidebar + Main Document */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Sticky Sidebar Navigation */}
        <div className="lg:col-span-3 sticky top-24 space-y-4">
          <div className="rounded-xl border-3 border-black bg-white p-4 shadow-brutal">
            <h3 className="font-mono text-xs font-black uppercase text-black border-b-2 border-black pb-2 mb-3 flex items-center gap-1.5">
              <BookOpen className="h-4 w-4" /> Table of Contents
            </h3>
            <nav className="space-y-1">
              {filteredSections.map((sec) => {
                const active = activeSection === sec.id;
                return (
                  <button
                    key={sec.id}
                    onClick={() => {
                      setActiveSection(sec.id);
                      document.getElementById(sec.id)?.scrollIntoView({ behavior: "smooth" });
                    }}
                    type="button"
                    className={`w-full text-left rounded-lg border-2 px-3 py-2 font-mono text-xs font-bold transition-all ${
                      active
                        ? "border-black bg-[#FFE600] text-black shadow-brutal-xs font-black translate-x-1"
                        : "border-transparent text-black/70 hover:bg-yellow-50 hover:text-black"
                    }`}
                  >
                    {sec.title}
                  </button>
                );
              })}
            </nav>
          </div>

          <div className="rounded-xl border-3 border-black bg-[#55EFC4] p-4 shadow-brutal space-y-2">
            <h4 className="font-mono text-xs font-black uppercase text-black">
              Connect to IDEs
            </h4>
            <p className="font-mono text-[11px] font-bold text-black/80">
              Need Claude Code, Cursor, or Cline configuration files?
            </p>
            <a
              href="/connect"
              className="inline-flex items-center gap-1 font-mono text-xs font-black uppercase text-black underline hover:no-underline"
            >
              Go to Setup Guides &rarr;
            </a>
          </div>
        </div>

        {/* Main Document Body */}
        <div className="lg:col-span-9 space-y-12">
          {/* SECTION 1: Overview & Architecture */}
          <section id="overview" className="rounded-2xl border-4 border-black bg-white p-8 shadow-brutal space-y-6">
            <div className="flex items-center gap-2">
              <span className="rounded bg-black px-2 py-0.5 font-mono text-xs font-black text-[#FFE600]">
                SECTION 01
              </span>
              <h2 className="text-2xl font-black uppercase tracking-tight text-black">
                Overview &amp; Architecture
              </h2>
            </div>

            <p className="font-mono text-xs md:text-sm font-bold text-black/80 leading-relaxed">
              <strong>GRIP (GraphRAG Interoperability Protocol)</strong> establishes the vendor-neutral wire protocol
              and tool surface for Graph-Augmented Retrieval Generation.
            </p>

            <div className="rounded-xl border-3 border-black bg-[#F7F5EE] p-5 shadow-brutal-xs space-y-4">
              <h3 className="font-mono text-sm font-black uppercase text-black">
                The Missing Middle Layer Problem
              </h3>
              <p className="font-mono text-xs font-semibold text-black/75 leading-relaxed">
                Prior to GRIP, every knowledge graph database (TigerGraph, Neo4j, Amazon Neptune, Memgraph) required proprietary query languages (GSQL, Cypher, openCypher, Gremlin) and bespoke RAG pipelines.
                LLMs were forced to generate complex graph query strings, leading to syntax hallucination, injection risks, and tight vendor lock-in.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-center font-mono text-xs">
                <div className="rounded-lg border-2 border-black bg-white p-3 shadow-brutal-xs">
                  <span className="font-black text-red-600 block mb-1">Top Layer</span>
                  <span className="font-bold">AI Agent / LLM</span>
                  <span className="block text-[10px] text-black/60">MCP Client Interface</span>
                </div>
                <div className="rounded-lg border-2 border-black bg-[#FFE600] p-3 shadow-brutal-xs">
                  <span className="font-black text-black block mb-1">GRIP Middle Layer</span>
                  <span className="font-black">20 Standard Contracts</span>
                  <span className="block text-[10px] text-black/70">50 Uniform MCP Tools</span>
                </div>
                <div className="rounded-lg border-2 border-black bg-white p-3 shadow-brutal-xs">
                  <span className="font-black text-blue-600 block mb-1">Bottom Layer</span>
                  <span className="font-bold">Any Graph Backend</span>
                  <span className="block text-[10px] text-black/60">TigerGraph, Neo4j, etc.</span>
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <h3 className="font-mono text-sm font-black uppercase text-black">
                Architectural Guarantees
              </h3>
              <ul className="list-disc list-inside font-mono text-xs font-bold text-black/80 space-y-1.5">
                <li><strong>Live Database Execution</strong>: 100% of tools execute directly against connected enterprise graph engines without stubbed responses.</li>
                <li><strong>Cryptographic Provenance (Contract 5)</strong>: Every answer is tied to source vertex IDs and chunk hashes.</li>
                <li><strong>Dynamic Token Bounding (Contract 8)</strong>: Output text fits strictly within caller&apos;s token budget.</li>
                <li><strong>Multi-Backend Federation (Contract 6)</strong>: Single queries fan out across hybrid TigerGraph + Neo4j clusters.</li>
              </ul>
            </div>
          </section>

          {/* SECTION 2: Installation & Quickstart */}
          <section id="quickstart" className="rounded-2xl border-4 border-black bg-white p-8 shadow-brutal space-y-6">
            <div className="flex items-center gap-2">
              <span className="rounded bg-black px-2 py-0.5 font-mono text-xs font-black text-[#55EFC4]">
                SECTION 02
              </span>
              <h2 className="text-2xl font-black uppercase tracking-tight text-black">
                Installation &amp; Quickstart
              </h2>
            </div>

            <p className="font-mono text-xs md:text-sm font-bold text-black/80 leading-relaxed">
              GRIP is distributed as a lightweight Python package with optional backend extras.
            </p>

            <div className="space-y-4">
              <h3 className="font-mono text-sm font-black uppercase text-black">
                1. Install via pip or pipx
              </h3>
              <CodeBlock
                code={`# Core package (standard MCP tools + in-memory store)
pip install -U grip-protocol

# With TigerGraph Cloud adapter & Gemini LLM support (Recommended)
pip install "grip-protocol[tigergraph,llm]"

# Global CLI installation via pipx
pipx install "grip-protocol[all]"`}
                language="bash"
                filename="terminal"
              />

              <h3 className="font-mono text-sm font-black uppercase text-black">
                2. Configure Environment Variables
              </h3>
              <CodeBlock
                code={`# .env file in your working directory
TIGERGRAPH_HOST="https://your-graph-endpoint.i.tgcloud.io"
TIGERGRAPH_USERNAME="tigergraph"
TIGERGRAPH_PASSWORD="your_password"
TIGERGRAPH_SECRET="your_secret_alias"
TIGERGRAPH_GRAPH_NAME="GraphragProtocol"
GOOGLE_API_KEY="AIzaSy..."
LLM_MODEL="gemini-2.5-flash"`}
                language="bash"
                filename=".env"
              />

              <h3 className="font-mono text-sm font-black uppercase text-black">
                3. Verify Installation via CLI
              </h3>
              <CodeBlock
                code={`# Check health of active backend
grip --help

# Launch in stdio transport mode (default for IDE agents)
grip --transport stdio`}
                language="bash"
                filename="terminal"
              />
            </div>
          </section>

          {/* SECTION 3: CLI Reference */}
          <section id="cli-reference" className="rounded-2xl border-4 border-black bg-white p-8 shadow-brutal space-y-6">
            <div className="flex items-center gap-2">
              <span className="rounded bg-black px-2 py-0.5 font-mono text-xs font-black text-[#74B9FF]">
                SECTION 03
              </span>
              <h2 className="text-2xl font-black uppercase tracking-tight text-black">
                CLI Command Reference
              </h2>
            </div>

            <p className="font-mono text-xs md:text-sm font-bold text-black/80 leading-relaxed">
              `grip-protocol` registers multiple binary entry points for convenience:
              <code>grip</code>, <code>grip-mcp</code>, <code>grip-server</code>, <code>graphrag-mcp</code>.
            </p>

            <div className="overflow-x-auto">
              <table className="w-full border-2 border-black font-mono text-xs">
                <thead className="bg-[#FFE600] text-black">
                  <tr className="border-b-2 border-black">
                    <th className="p-2.5 text-left font-black">Flag</th>
                    <th className="p-2.5 text-left font-black">Values</th>
                    <th className="p-2.5 text-left font-black">Description</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-black/20 bg-white">
                  <tr>
                    <td className="p-2.5 font-bold">--transport</td>
                    <td className="p-2.5 font-semibold"><code>stdio | streamable-http | sse</code></td>
                    <td className="p-2.5 text-black/70">MCP communication transport. Default: <code>stdio</code>.</td>
                  </tr>
                  <tr>
                    <td className="p-2.5 font-bold">--host</td>
                    <td className="p-2.5 font-semibold"><code>IP address (e.g. 0.0.0.0)</code></td>
                    <td className="p-2.5 text-black/70">Bind address for HTTP or SSE server. Default: <code>127.0.0.1</code>.</td>
                  </tr>
                  <tr>
                    <td className="p-2.5 font-bold">--port</td>
                    <td className="p-2.5 font-semibold"><code>Port number (e.g. 8000)</code></td>
                    <td className="p-2.5 text-black/70">Port for HTTP or SSE server. Default: <code>8000</code>.</td>
                  </tr>
                  <tr>
                    <td className="p-2.5 font-bold">--help</td>
                    <td className="p-2.5 font-semibold"><code>-h, --help</code></td>
                    <td className="p-2.5 text-black/70">Display usage summary and exit.</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          {/* SECTION 4: 50-Tool Reference */}
          <section id="tool-surface" className="rounded-2xl border-4 border-black bg-white p-8 shadow-brutal space-y-6">
            <div className="flex items-center gap-2">
              <span className="rounded bg-black px-2 py-0.5 font-mono text-xs font-black text-[#A29BFE]">
                SECTION 04
              </span>
              <h2 className="text-2xl font-black uppercase tracking-tight text-black">
                Complete 50-Tool MCP Surface
              </h2>
            </div>

            <p className="font-mono text-xs md:text-sm font-bold text-black/80 leading-relaxed">
              Every tool returns valid JSON strings conforming to the official RFC wire specifications. Below is the full tool catalog:
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Category 1 */}
              <div className="rounded-xl border-2 border-black bg-[#F7F5EE] p-4 shadow-brutal-xs space-y-2">
                <span className="rounded bg-black px-2 py-0.5 font-mono text-[10px] font-black text-[#FFE600]">
                  CONTRACT 1: RETRIEVAL (7 TOOLS)
                </span>
                <ul className="font-mono text-xs space-y-1 font-semibold text-black/80">
                  <li><code>graphrag_search</code> — Auto-routed hybrid search</li>
                  <li><code>graphrag_local_search</code> — Multi-hop entity expansion</li>
                  <li><code>graphrag_global_search</code> — Community summary search</li>
                  <li><code>graphrag_hybrid_search</code> — Vector + topology fusion</li>
                  <li><code>graphrag_entity</code> — Entity lookup by ID or name</li>
                  <li><code>graphrag_path</code> — Shortest path discovery</li>
                  <li><code>graphrag_neighborhood</code> — K-hop neighbor subgraph</li>
                </ul>
              </div>

              {/* Category 2 */}
              <div className="rounded-xl border-2 border-black bg-[#F7F5EE] p-4 shadow-brutal-xs space-y-2">
                <span className="rounded bg-black px-2 py-0.5 font-mono text-[10px] font-black text-[#55EFC4]">
                  CONTRACT 3: SCHEMA (4 TOOLS)
                </span>
                <ul className="font-mono text-xs space-y-1 font-semibold text-black/80">
                  <li><code>graphrag_schema</code> — Complete vertex &amp; edge types</li>
                  <li><code>graphrag_entity_types</code> — Vertex types with counts</li>
                  <li><code>graphrag_relationship_types</code> — Edge definitions</li>
                  <li><code>graphrag_sample</code> — Sample entities for LLM context</li>
                </ul>
              </div>

              {/* Category 3 */}
              <div className="rounded-xl border-2 border-black bg-[#F7F5EE] p-4 shadow-brutal-xs space-y-2">
                <span className="rounded bg-black px-2 py-0.5 font-mono text-[10px] font-black text-[#74B9FF]">
                  CONTRACT 4: CONSTRUCTION (2 TOOLS)
                </span>
                <ul className="font-mono text-xs space-y-1 font-semibold text-black/80">
                  <li><code>graphrag_ingest</code> — Document ingestion pipeline</li>
                  <li><code>graphrag_delete_document</code> — Cascade reference deletion</li>
                </ul>
              </div>

              {/* Category 4 */}
              <div className="rounded-xl border-2 border-black bg-[#F7F5EE] p-4 shadow-brutal-xs space-y-2">
                <span className="rounded bg-black px-2 py-0.5 font-mono text-[10px] font-black text-[#FF7675]">
                  CONTRACT 5: PROVENANCE (4 TOOLS)
                </span>
                <ul className="font-mono text-xs space-y-1 font-semibold text-black/80">
                  <li><code>graphrag_provenance</code> — Cryptographic citation trace</li>
                  <li><code>graphrag_trajectory</code> — Ordered traversal step replay</li>
                  <li><code>graphrag_sources</code> — Deduplicated supporting documents</li>
                  <li><code>graphrag_audit</code> — Visited-not-cited leak audit</li>
                </ul>
              </div>

              {/* Category 5 */}
              <div className="rounded-xl border-2 border-black bg-[#F7F5EE] p-4 shadow-brutal-xs space-y-2">
                <span className="rounded bg-black px-2 py-0.5 font-mono text-[10px] font-black text-[#FAB1A0]">
                  CONTRACT 11-15: ANALYTICS &amp; AGGREGATES
                </span>
                <ul className="font-mono text-xs space-y-1 font-semibold text-black/80">
                  <li><code>graphrag_similarity</code> — Cosine embedding &amp; Jaccard</li>
                  <li><code>graphrag_temporal_search</code> — Date range filtered search</li>
                  <li><code>graphrag_explain</code> — Natural language why-retrieved</li>
                  <li><code>graphrag_diff</code> — SubgraphContext delta comparison</li>
                  <li><code>graphrag_count</code> — Entity count with attribute filters</li>
                  <li><code>graphrag_group_by</code> — Group entities by property</li>
                  <li><code>graphrag_top_n</code> — Top-N ranked by numeric property</li>
                  <li><code>graphrag_stats_summary</code> — Graph-level density &amp; degree</li>
                </ul>
              </div>

              {/* Category 6 */}
              <div className="rounded-xl border-2 border-black bg-[#F7F5EE] p-4 shadow-brutal-xs space-y-2">
                <span className="rounded bg-black px-2 py-0.5 font-mono text-[10px] font-black text-[#A29BFE]">
                  CONTRACT 16-20: ADVANCED PROTOCOL
                </span>
                <ul className="font-mono text-xs space-y-1 font-semibold text-black/80">
                  <li><code>graphrag_export_subgraph</code> — GraphML / Cypher / JSON-LD</li>
                  <li><code>graphrag_batch</code> — Parallel execution up to 25 calls</li>
                  <li><code>graphrag_watch</code> — Event journal &amp; mutation stream</li>
                  <li><code>graphrag_resolve_conflicts</code> — Temporal contradiction resolver</li>
                  <li><code>graphrag_triage_query</code> — RAG vs GraphRAG ROI classifier</li>
                  <li><code>graphrag_agent_investigate</code> — Multi-step reasoning agent</li>
                </ul>
              </div>
            </div>
          </section>

          {/* SECTION 5: Transport Modes */}
          <section id="transports" className="rounded-2xl border-4 border-black bg-white p-8 shadow-brutal space-y-6">
            <div className="flex items-center gap-2">
              <span className="rounded bg-black px-2 py-0.5 font-mono text-xs font-black text-[#FFE600]">
                SECTION 05
              </span>
              <h2 className="text-2xl font-black uppercase tracking-tight text-black">
                Transport Protocols (stdio, HTTP, SSE)
              </h2>
            </div>

            <p className="font-mono text-xs md:text-sm font-bold text-black/80 leading-relaxed">
              GRIP implements all three official Model Context Protocol transports:
            </p>

            <div className="space-y-4">
              <div className="rounded-xl border-2 border-black bg-[#F7F5EE] p-4 shadow-brutal-xs space-y-2">
                <h4 className="font-mono text-xs font-black uppercase text-black">
                  1. stdio Transport (Standard Input/Output)
                </h4>
                <p className="font-mono text-xs font-semibold text-black/75">
                  Best for local desktop agents like Claude Code, Cursor, Windsurf, and Zed. The agent spawns the `grip` process and communicates over pipes.
                </p>
                <CodeBlock code="grip --transport stdio" language="bash" />
              </div>

              <div className="rounded-xl border-2 border-black bg-[#F7F5EE] p-4 shadow-brutal-xs space-y-2">
                <h4 className="font-mono text-xs font-black uppercase text-black">
                  2. Streamable HTTP Transport
                </h4>
                <p className="font-mono text-xs font-semibold text-black/75">
                  Modern HTTP transport for remote microservices, multi-tenant agent gateways, and cloud deployment.
                </p>
                <CodeBlock code="grip --transport streamable-http --host 0.0.0.0 --port 8000" language="bash" />
              </div>

              <div className="rounded-xl border-2 border-black bg-[#F7F5EE] p-4 shadow-brutal-xs space-y-2">
                <h4 className="font-mono text-xs font-black uppercase text-black">
                  3. SSE (Server-Sent Events) Transport
                </h4>
                <p className="font-mono text-xs font-semibold text-black/75">
                  HTTP with a continuous server-push event stream for real-time graph mutations and streaming traversal events (Contract 7).
                </p>
                <CodeBlock code="grip --transport sse --host 0.0.0.0 --port 8000" language="bash" />
              </div>
            </div>
          </section>

          {/* SECTION 6: Backends */}
          <section id="backends" className="rounded-2xl border-4 border-black bg-white p-8 shadow-brutal space-y-6">
            <div className="flex items-center gap-2">
              <span className="rounded bg-black px-2 py-0.5 font-mono text-xs font-black text-[#55EFC4]">
                SECTION 06
              </span>
              <h2 className="text-2xl font-black uppercase tracking-tight text-black">
                Supported Graph Backends
              </h2>
            </div>

            <p className="font-mono text-xs md:text-sm font-bold text-black/80 leading-relaxed">
              GRIP uses a pluggable adapter architecture (`BaseGraphRAGAdapter`) supporting both production graph databases and local lightweight stores:
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="rounded-xl border-2 border-black bg-white p-4 shadow-brutal-xs space-y-2">
                <div className="flex items-center justify-between">
                  <h4 className="font-mono text-xs font-black uppercase text-black">TigerGraph Cloud (Savanna)</h4>
                  <Badge color="green">Primary</Badge>
                </div>
                <p className="font-mono text-xs font-semibold text-black/75">
                  Native REST++ precompiled queries for multi-hop traversals, Jaccard similarity, and vector similarity search on 512-dim embedding vertices.
                </p>
              </div>

              <div className="rounded-xl border-2 border-black bg-white p-4 shadow-brutal-xs space-y-2">
                <div className="flex items-center justify-between">
                  <h4 className="font-mono text-xs font-black uppercase text-black">Neo4j (Cypher)</h4>
                  <Badge color="blue">Supported</Badge>
                </div>
                <p className="font-mono text-xs font-semibold text-black/75">
                  Bolt driver adapter compiling Contract 1 retrieval and Contract 3 schema introspection into parameterized Cypher queries.
                </p>
              </div>

              <div className="rounded-xl border-2 border-black bg-white p-4 shadow-brutal-xs space-y-2">
                <div className="flex items-center justify-between">
                  <h4 className="font-mono text-xs font-black uppercase text-black">SQLite WAL Store</h4>
                  <Badge color="amber">Embedded</Badge>
                </div>
                <p className="font-mono text-xs font-semibold text-black/75">
                  Zero-dependency local persistence for metadata, job status, capability tokens, and mutation event journaling.
                </p>
              </div>

              <div className="rounded-xl border-2 border-black bg-white p-4 shadow-brutal-xs space-y-2">
                <div className="flex items-center justify-between">
                  <h4 className="font-mono text-xs font-black uppercase text-black">In-Memory Demo Adapter</h4>
                  <Badge color="purple">Testing</Badge>
                </div>
                <p className="font-mono text-xs font-semibold text-black/75">
                  Instant offline testing adapter pre-loaded with sample ArXiv knowledge subgraphs for hermetic test suites.
                </p>
              </div>
            </div>
          </section>

          {/* SECTION 7: Autonomous Agentic Harness */}
          <section id="agent-harness" className="rounded-2xl border-4 border-black bg-white p-8 shadow-brutal space-y-6">
            <div className="flex items-center gap-2">
              <span className="rounded bg-black px-2 py-0.5 font-mono text-xs font-black text-[#A29BFE]">
                SECTION 07
              </span>
              <h2 className="text-2xl font-black uppercase tracking-tight text-black">
                Autonomous Agentic Harness
              </h2>
            </div>

            <p className="font-mono text-xs md:text-sm font-bold text-black/80 leading-relaxed">
              `graphrag_agent_investigate` runs an autonomous multi-step reasoning loop powered by Gemini 2.5 Flash and Automatic Function Calling (AFC).
            </p>

            <div className="rounded-xl border-2 border-black bg-[#F7F5EE] p-5 shadow-brutal-xs space-y-3">
              <h4 className="font-mono text-xs font-black uppercase text-black">
                Agentic Investigation Trajectory
              </h4>
              <ol className="list-decimal list-inside font-mono text-xs font-bold text-black/80 space-y-1.5">
                <li><strong>Hypothesis Formulation</strong>: Identifies seed entities and queries schema structure.</li>
                <li><strong>Targeted Expansion</strong>: Traverses high-confidence relationships across up to 10 hops.</li>
                <li><strong>Conflict Resolution</strong>: Evaluates contradictions using Contract 19 recency and citation weights.</li>
                <li><strong>Extractive Synthesis</strong>: Formulates final grounded answer strictly backed by visited provenance paths.</li>
              </ol>
            </div>
          </section>

          {/* Quick link to Protocol */}
          <div className="rounded-2xl border-4 border-black bg-[#FFE600] p-8 shadow-brutal-xl flex flex-col sm:flex-row items-center justify-between gap-4">
            <div>
              <h3 className="text-xl font-black uppercase text-black">
                Explore All 20 Wire Contracts in Detail
              </h3>
              <p className="font-mono text-xs font-bold text-black/75">
                Review JSON schemas, architectural guarantees, and standards for all 20 contracts.
              </p>
            </div>
            <a
              href="/protocol"
              className="rounded-xl border-3 border-black bg-black px-6 py-3 font-mono text-sm font-black uppercase text-white shadow-brutal hover:bg-neutral-800 transition-all"
            >
              Protocol Explorer &rarr;
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
