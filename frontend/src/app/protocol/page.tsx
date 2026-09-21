"use client";

import { useEffect, useState } from "react";
import { getGraphSchema } from "../../lib/api";
import type { GraphSchema } from "../../lib/types";
import LoadingSpinner from "../../components/shared/LoadingSpinner";
import Badge from "../../components/shared/Badge";
import CodeBlock from "../../components/shared/CodeBlock";
import {
  FileText,
  Layers,
  Search,
  ChevronDown,
  ChevronUp,
  Database,
} from "lucide-react";

interface ProtocolContract {
  id: string;
  number: number;
  name: string;
  category: "Core Retrieval" | "Data Model" | "Ingestion & Provenance" | "Execution" | "Intelligence & Reasoning" | "Security & Governance";
  badgeColor: "green" | "blue" | "purple" | "amber" | "red";
  tagline: string;
  standardSet: string;
  architecturalImplication: string;
  tools: string[];
  schemaExample: string;
}

const ALL_20_CONTRACTS: ProtocolContract[] = [
  {
    id: "C1",
    number: 1,
    name: "Retrieval Operations",
    category: "Core Retrieval",
    badgeColor: "green",
    tagline: "7 Standardized Query Modalities with Automatic Routing",
    standardSet:
      "Defines the 7 canonical retrieval operations across all graph backends: local search, global community search, hybrid vector+graph search, entity lookup, path discovery, k-hop neighborhood expansion, and community member enumeration.",
    architecturalImplication:
      "Eliminates vendor-specific graph query dialects (GSQL, Cypher, Gremlin). AI agents query using uniform semantic parameters rather than compiling database-specific query strings, completely shielding LLMs from syntax hallucinations and injection vulnerabilities.",
    tools: [
      "graphrag_search",
      "graphrag_local_search",
      "graphrag_global_search",
      "graphrag_hybrid_search",
      "graphrag_entity",
      "graphrag_path",
      "graphrag_neighborhood",
    ],
    schemaExample: `{
  "query": "self-attention transformer mechanism",
  "mode": "auto",
  "depth": 2,
  "top_k": 10,
  "format_text": "markdown",
  "max_tokens": 4096
}`,
  },
  {
    id: "C2",
    number: 2,
    name: "Subgraph Context Envelope",
    category: "Data Model",
    badgeColor: "blue",
    tagline: "The Universal Interoperable Graph Response Format",
    standardSet:
      "Standardizes the exact wire structure returned by every retrieval call. Every response must contain protocol version, query metadata, execution timestamp, cryptographic provenance, entities array, relationships array, paths array, and performance metrics.",
    architecturalImplication:
      "Guarantees that downstream LLM prompts, visualization frontends, and analytical evaluation pipelines consume a deterministic data envelope regardless of whether the backend is TigerGraph, Neo4j, or an in-memory test store.",
    tools: ["Used as the standard return envelope for all 50 tools"],
    schemaExample: `{
  "protocol": "graphrag/1.0",
  "operation": "hybrid_search",
  "query": "attention models",
  "provenance": { "backend": "TigerGraph", "source_documents": ["doc:1706.03762"] },
  "results": {
    "entities": [{ "id": "1706.03762", "type": "Paper", "name": "Attention Is All You Need" }],
    "relationships": [{ "source": "1706.03762", "target": "Vaswani", "type": "AUTHORED_BY" }]
  },
  "metrics": { "latency_ms": 482.4, "entities_retrieved": 5 }
}`,
  },
  {
    id: "C3",
    number: 3,
    name: "Schema Discovery & Introspection",
    category: "Data Model",
    badgeColor: "blue",
    tagline: "Zero-Knowledge Graph Introspection for LLM Planning",
    standardSet:
      "Specifies the schema-introspection payload. Exposes vertex types, edge types, primary keys, attribute definitions, sample entities, and graph-level statistics in a standardized JSON schema without requiring SQL/GSQL/Cypher DDL inspection.",
    architecturalImplication:
      "Enables autonomous AI agents to explore and understand unfamiliar enterprise knowledge graphs on the fly, auto-generating valid multi-hop traversal plans without hardcoded ontology assumptions.",
    tools: [
      "graphrag_schema",
      "graphrag_entity_types",
      "graphrag_relationship_types",
      "graphrag_sample",
    ],
    schemaExample: `{
  "protocol": "graphrag/1.0",
  "graph_id": "GraphragProtocol",
  "vertex_types": [
    { "type": "Paper", "count": 8001, "primary_key": "id", "attributes": [{"name": "title", "type": "STRING"}] },
    { "type": "Author", "count": 31301, "primary_key": "id" }
  ],
  "edge_types": [
    { "type": "AUTHORED_BY", "source": "Paper", "target": "Author", "count": 39041 }
  ],
  "statistics": { "total_vertices": 49656, "total_edges": 79044, "avg_degree": 3.18 }
}`,
  },
  {
    id: "C4",
    number: 4,
    name: "Construction & Ingestion Pipeline",
    category: "Ingestion & Provenance",
    badgeColor: "purple",
    tagline: "Idempotent Document Ingestion & Entity Resolution",
    standardSet:
      "Defines the document ingestion wire contract. Handles document chunking, concept extraction, entity resolution strategies (EXACT_ID, NEW_ONLY, MERGE), and cascading document deletion.",
    architecturalImplication:
      "Standardizes the write path across graph databases. Enforces idempotent writes so documents can be re-ingested safely without duplicating knowledge graph nodes or creating dangling edge references.",
    tools: ["graphrag_ingest", "graphrag_delete_document"],
    schemaExample: `{
  "documents": [{
    "id": "doc:2026-01",
    "title": "Universal GraphRAG Protocol",
    "text": "GRIP standardizes graph retrieval...",
    "metadata": { "year": 2026, "field": "AI" }
  }],
  "extraction_strategy": "frequency",
  "resolve_strategy": "exact_id",
  "async_mode": false
}`,
  },
  {
    id: "C5",
    number: 5,
    name: "Verifiable Cryptographic Provenance",
    category: "Ingestion & Provenance",
    badgeColor: "green",
    tagline: "Zero-Hallucination Audit Trail & Citation Lineage",
    standardSet:
      "Mandates that every retrieved fact and entity links back to verifiable citation hashes, source documents, and ordered traversal steps. Implements visited-not-cited leakage auditing.",
    architecturalImplication:
      "Provides enterprise compliance, hallucination tracking, and legal accountability. An AI agent's answer can be mathematically checked against the exact graph traversal trail and source text snippets.",
    tools: [
      "graphrag_provenance",
      "graphrag_trajectory",
      "graphrag_sources",
      "graphrag_audit",
    ],
    schemaExample: `{
  "fact_id": "fact:sha256:7f9a8b...",
  "source_document_id": "doc:1706.03762",
  "traversal_path": ["Paper(1706.03762)", "AUTHORED_BY", "Author(Vaswani)"],
  "completeness_score": 1.0,
  "visited_not_cited_count": 0
}`,
  },
  {
    id: "C6",
    number: 6,
    name: "Multi-Backend Federation",
    category: "Execution",
    badgeColor: "amber",
    tagline: "Cross-Graph Query Fan-Out & Rank Fusion",
    standardSet:
      "Standardizes federated multi-graph queries. Fanned-out sub-queries execute concurrently across heterogeneous backends (e.g. TigerGraph biomedical graph + Neo4j financial graph) and merge results via Reciprocal Rank Fusion (RRF).",
    architecturalImplication:
      "Breaks data silos by allowing AI agents to query multiple enterprise databases concurrently as a unified virtual knowledge graph without physical ETL consolidation.",
    tools: ["graphrag_list_backends", "graphrag_federated_search"],
    schemaExample: `{
  "backends": ["tg-savanna-cloud", "neo4j-onprem"],
  "query": "supply chain disruptions in semiconductor manufacturing",
  "merge_strategy": "reciprocal_rank_fusion",
  "top_k": 10
}`,
  },
  {
    id: "C7",
    number: 7,
    name: "Real-Time Mutation Streaming",
    category: "Execution",
    badgeColor: "purple",
    tagline: "Server-Sent Events (SSE) Live Graph Mutation Feed",
    standardSet:
      "Defines an event-driven SSE protocol broadcasting graph mutations: entity created, entity updated, relationship added, community recomputed, and batch ingestion completed.",
    architecturalImplication:
      "Allows AI agents and UI dashboards to maintain real-time cache invalidation and reactive awareness of live enterprise knowledge updates without polling.",
    tools: ["graphrag_events", "Streaming SSE Endpoint (/api/stream)"],
    schemaExample: `{
  "event_id": "evt-98214",
  "event_type": "entity_created",
  "timestamp": "2026-09-21T10:45:00Z",
  "entity_id": "2609.02056",
  "entity_type": "Paper",
  "graph_id": "GraphragProtocol"
}`,
  },
  {
    id: "C8",
    number: 8,
    name: "Dynamic Prompt Formatting",
    category: "Intelligence & Reasoning",
    badgeColor: "green",
    tagline: "Token-Bounded, LLM-Ready Context Compaction",
    standardSet:
      "Transforms SubgraphContext envelopes into bounded text representations (Markdown, structured JSON, XML, YAML) tailored for prompt injection, guaranteed not to exceed max_tokens.",
    architecturalImplication:
      "Eliminates prompt window overflow. When graph neighborhoods contain hundreds of nodes, Contract 8 dynamically compacts properties while preserving key entity-relationship topology.",
    tools: ["graphrag_format"],
    schemaExample: `{
  "context": { "...SubgraphContext payload..." },
  "format_text": "markdown",
  "max_tokens": 2048
}`,
  },
  {
    id: "C9",
    number: 9,
    name: "Evaluation & Benchmarking",
    category: "Intelligence & Reasoning",
    badgeColor: "amber",
    tagline: "Standard Metrics: Latency, Precision@K, LLM-as-Judge",
    standardSet:
      "Establishes standard benchmark measurement protocols: Precision@K, Recall@K, Multi-Hop Reasoning Cliff curves, Latency P50/P99, BERTScore semantic similarity, and token ROI.",
    architecturalImplication:
      "Enables scientific, reproducible evaluation comparing GraphRAG against vector baselines. Eliminates subjective marketing claims by enforcing objective benchmark harnesses.",
    tools: ["graphrag_evaluate", "Benchmark Suite"],
    schemaExample: `{
  "ground_truth_id": "eval-arxiv-01",
  "metrics": {
    "precision_at_k": 0.94,
    "multi_hop_accuracy": 0.88,
    "hallucination_rate": 0.031,
    "latency_p50_ms": 480.0
  }
}`,
  },
  {
    id: "C10",
    number: 10,
    name: "Authorization & Capability Tokens",
    category: "Security & Governance",
    badgeColor: "red",
    tagline: "5-Tier RBAC & Cryptographic HMAC Access Control",
    standardSet:
      "Enforces 5-tier role-based access control (Admin, Editor, Analyst, Viewer, Guest) with cryptographically signed HMAC capability tokens containing strict operation sets and TTL expirations.",
    architecturalImplication:
      "Secures knowledge graphs in agentic environments. Prevents unauthorized prompt injections from performing destructive writes or accessing restricted graph partitions.",
    tools: ["graphrag_authorize", "graphrag_capability_token"],
    schemaExample: `{
  "role": "analyst",
  "operations": ["search", "schema", "stats"],
  "ttl_seconds": 3600,
  "admin_token": "iv9i34kubdB6Iu..."
}`,
  },
  {
    id: "C11",
    number: 11,
    name: "Semantic Similarity",
    category: "Core Retrieval",
    badgeColor: "green",
    tagline: "Vector Cosine & Jaccard Lexical Overlap Fusion",
    standardSet:
      "Computes semantic similarity between text snippets or entity IDs using high-dimensional vector embeddings with automatic lexical Jaccard fallback.",
    architecturalImplication:
      "Allows AI agents to compute real-time topological and semantic distance directly inside the graph layer without downloading raw entity vectors to the client.",
    tools: [
      "graphrag_similarity",
      "graphrag_entity_similarity",
      "graphrag_batch_similarity",
    ],
    schemaExample: `{
  "text_a": "neural graph attention networks",
  "text_b": "deep learning message passing architectures",
  "method": "cosine",
  "score": 0.8924
}`,
  },
  {
    id: "C12",
    number: 12,
    name: "Temporal Querying & Time Travel",
    category: "Core Retrieval",
    badgeColor: "blue",
    tagline: "ISO-8601 Temporal Intervals & Point-in-Time Snapshots",
    standardSet:
      "Enables filtering and traversal across temporal dimensions. Supports ISO-8601 date range filters (start/end) and point-in-time snapshot retrieval.",
    architecturalImplication:
      "Essential for historical analysis, legal compliance, and evolving knowledge bases. Agents can examine the state of knowledge at a specific historical point in time.",
    tools: ["graphrag_temporal_search"],
    schemaExample: `{
  "query": "transformer architectures",
  "start": "2017-01-01",
  "end": "2020-12-31",
  "mode": "auto",
  "top_k": 10
}`,
  },
  {
    id: "C13",
    number: 13,
    name: "Explanation & Path Reasoning",
    category: "Intelligence & Reasoning",
    badgeColor: "purple",
    tagline: "Natural Language Narratives for Retrieval Decisions",
    standardSet:
      "Generates human-readable explanations detailing why specific entities were retrieved and verbalizing the semantic connections along discovered graph paths.",
    architecturalImplication:
      "Provides transparent explainability for AI decisions in high-stakes domains like medicine, finance, and intelligence, transforming raw graph paths into intuitive narratives.",
    tools: ["graphrag_explain", "graphrag_explain_path"],
    schemaExample: `{
  "query": "Why was Vaswani linked to Transformer?",
  "max_entities": 5
}`,
  },
  {
    id: "C14",
    number: 14,
    name: "Structural Context Diff",
    category: "Intelligence & Reasoning",
    badgeColor: "amber",
    tagline: "Topological Deltas Between Subgraph Envelopes",
    standardSet:
      "Calculates structural differences between two SubgraphContext envelopes, reporting entities only in A, entities only in B, shared vertices, and modified relationships.",
    architecturalImplication:
      "Enables AI agents to detect knowledge changes across time, compare competing theories, or evaluate retrieval differences between different model queries.",
    tools: ["graphrag_diff", "graphrag_diff_queries"],
    schemaExample: `{
  "query_a": "convolutional neural networks",
  "query_b": "vision transformers",
  "top_k": 5
}`,
  },
  {
    id: "C15",
    number: 15,
    name: "Graph Aggregates & Analytics",
    category: "Execution",
    badgeColor: "green",
    tagline: "OLAP Computations, Group-By, and Degree Distributions",
    standardSet:
      "Specifies analytical OLAP operations over knowledge graphs: entity counts with attribute filters, group-by aggregations, top-N rankings, and graph-level density metrics.",
    architecturalImplication:
      "Allows AI agents to answer quantitative, macro-level questions without pulling raw entity lists into context, conserving thousands of LLM tokens.",
    tools: [
      "graphrag_count",
      "graphrag_group_by",
      "graphrag_top_n",
      "graphrag_stats_summary",
    ],
    schemaExample: `{
  "entity_type": "Paper",
  "rank_by": "citation_count",
  "n": 10,
  "descending": true
}`,
  },
  {
    id: "C16",
    number: 16,
    name: "Subgraph Format Export",
    category: "Data Model",
    badgeColor: "blue",
    tagline: "Portable GraphML, Cypher MERGE, JSON-LD, RDF Turtle",
    standardSet:
      "Exports any SubgraphContext into standard portable graph formats: GraphML (for Gephi/Cytoscape), Cypher MERGE statements, JSON-LD, or RDF Turtle.",
    architecturalImplication:
      "Guarantees true vendor neutrality. Developers can retrieve a subgraph using GRIP and immediately export it into other graph tools or serialization standards.",
    tools: ["graphrag_export_subgraph"],
    schemaExample: `{
  "context": { "...SubgraphContext..." },
  "format": "graphml"
}`,
  },
  {
    id: "C17",
    number: 17,
    name: "Parallel Batch Runner",
    category: "Execution",
    badgeColor: "amber",
    tagline: "Concurrent Multi-Tool Fan-Out in a Single Round-Trip",
    standardSet:
      "Enables execution of up to 25 distinct tool calls in parallel over a single network round-trip, aggregating results with per-call success/failure tracking.",
    architecturalImplication:
      "Dramatically slashes latency in complex agent workflows by eliminating sequential HTTP/stdio round-trip bottlenecks.",
    tools: ["graphrag_batch"],
    schemaExample: `{
  "calls": [
    { "tool": "graphrag_status", "arguments": {} },
    { "tool": "graphrag_count", "arguments": { "entity_type": "Paper" } }
  ]
}`,
  },
  {
    id: "C18",
    number: 18,
    name: "Watch & Subscription Journal",
    category: "Execution",
    badgeColor: "purple",
    tagline: "Persistent Event Journal & Historical Replay",
    standardSet:
      "Provides persistent, queryable mutation journaling with filters by entity ID, event type, and since_timestamp for reliable offline catch-up.",
    architecturalImplication:
      "Ensures distributed agent workers can synchronize their local knowledge caches reliably even after network interruptions or process restarts.",
    tools: ["graphrag_watch"],
    schemaExample: `{
  "graph_id": "GraphragProtocol",
  "event_types": ["entity_created", "edge_updated"],
  "limit": 50
}`,
  },
  {
    id: "C19",
    number: 19,
    name: "Conflict & Uncertainty Resolution",
    category: "Intelligence & Reasoning",
    badgeColor: "red",
    tagline: "Temporal Recency & Citation Authority Conflict Solver",
    standardSet:
      "Detects and resolves contradictory facts, claims, or relationships within a topic using weighted temporal recency and source citation authority.",
    architecturalImplication:
      "Solves the fundamental knowledge graph problem of outdated or conflicting information, giving agents deterministic heuristics to resolve contradictions.",
    tools: ["graphrag_resolve_conflicts"],
    schemaExample: `{
  "query": "Who is the current CEO of Twitter / X?",
  "recency_weight": 0.6,
  "authority_weight": 0.4
}`,
  },
  {
    id: "C20",
    number: 20,
    name: "Query Triage & ROI Classifier",
    category: "Intelligence & Reasoning",
    badgeColor: "green",
    tagline: "Pipeline Routing: Basic RAG vs GraphRAG vs Agentic",
    standardSet:
      "Analyzes input queries and predicts structural complexity score (0.0 to 1.0), expected accuracy gain, and ROI, recommending either basic RAG, GraphRAG, or Agentic Investigation.",
    architecturalImplication:
      "Optimizes enterprise cost and latency. Prevents over-spending on deep graph traversals for simple keyword queries while ensuring complex multi-hop queries receive full agentic treatment.",
    tools: ["graphrag_triage_query"],
    schemaExample: `{
  "query": "What is the relationship between entity X and entity Y across time?",
  "recommended_pipeline": "agentic_graphrag",
  "complexity_score": 0.92,
  "agentic_roi": "HIGH"
}`,
  },
];

export default function ProtocolPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [schema, setSchema] = useState<GraphSchema | null>(null);
  const [activeCategory, setActiveCategory] = useState<string>("All");
  const [expandedContract, setExpandedContract] = useState<number | null>(1);
  const [searchFilter, setSearchFilter] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    getGraphSchema()
      .then((data) => {
        if (!cancelled) setSchema(data);
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

  const categories = [
    "All",
    "Core Retrieval",
    "Data Model",
    "Ingestion & Provenance",
    "Execution",
    "Intelligence & Reasoning",
    "Security & Governance",
  ];

  const filteredContracts = ALL_20_CONTRACTS.filter((c) => {
    const matchesCat = activeCategory === "All" || c.category === activeCategory;
    const matchesSearch =
      c.name.toLowerCase().includes(searchFilter.toLowerCase()) ||
      c.standardSet.toLowerCase().includes(searchFilter.toLowerCase()) ||
      c.tools.some((t) => t.toLowerCase().includes(searchFilter.toLowerCase()));
    return matchesCat && matchesSearch;
  });

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 space-y-10">
      {/* Header Banner */}
      <div className="rounded-2xl border-4 border-black bg-white p-8 shadow-brutal-xl space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge color="amber">RFC STANDARD</Badge>
          <Badge color="green">20 WIRE CONTRACTS</Badge>
          <Badge color="blue">50 MCP TOOLS</Badge>
        </div>
        <h1 className="text-3xl md:text-5xl font-black uppercase tracking-tight text-black">
          The 20 Formal Wire Contracts of GRIP
        </h1>
        <p className="max-w-4xl font-mono text-sm md:text-base font-bold text-black/80 leading-relaxed">
          Each contract defines strict architectural invariants, JSON schemas, tool definitions,
          and guarantees designed to eliminate vendor lock-in and enable zero-mock GraphRAG across any backend.
        </p>
      </div>

      {/* Live Backend Statistics Pill Strip (Real TigerGraph Backend) */}
      <div className="rounded-xl border-3 border-black bg-white p-5 shadow-brutal space-y-3">
        <div className="flex items-center justify-between border-b-2 border-black pb-2">
          <div className="flex items-center gap-2">
            <Database className="h-4 w-4 text-black" />
            <h3 className="font-mono text-xs font-black uppercase text-black">
              Live Backend Schema Introspection (Contract 3)
            </h3>
          </div>
          <span className="rounded-md border border-black bg-[#55EFC4] px-2 py-0.5 font-mono text-[10px] font-black uppercase">
            ACTIVE TIGERGRAPH CLOUD
          </span>
        </div>

        {loading && <LoadingSpinner label="Introspecting live TigerGraph schema..." />}
        {error && (
          <p className="font-mono text-xs font-bold text-red-600">
            Could not fetch live schema ({error}). Showing offline protocol specification.
          </p>
        )}

        {schema && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-1">
            <div className="rounded-lg border-2 border-black bg-[#E0E7FF] p-3 shadow-brutal-xs">
              <span className="font-mono text-[10px] font-black uppercase text-black/60 block">Total Vertices</span>
              <span className="font-mono text-lg font-black text-black">{schema.statistics.total_vertices.toLocaleString()}</span>
            </div>
            <div className="rounded-lg border-2 border-black bg-[#DCFCE7] p-3 shadow-brutal-xs">
              <span className="font-mono text-[10px] font-black uppercase text-black/60 block">Total Edges</span>
              <span className="font-mono text-lg font-black text-black">{schema.statistics.total_edges.toLocaleString()}</span>
            </div>
            <div className="rounded-lg border-2 border-black bg-[#FEF08A] p-3 shadow-brutal-xs">
              <span className="font-mono text-[10px] font-black uppercase text-black/60 block">Avg Degree</span>
              <span className="font-mono text-lg font-black text-black">{(schema.statistics.avg_degree ?? 3.18).toFixed(2)}</span>
            </div>
            <div className="rounded-lg border-2 border-black bg-[#FED7AA] p-3 shadow-brutal-xs">
              <span className="font-mono text-[10px] font-black uppercase text-black/60 block">Vertex Types</span>
              <span className="font-mono text-lg font-black text-black">{schema.vertex_types.length} Types</span>
            </div>
          </div>
        )}
      </div>

      {/* Filter and Search Bar */}
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          {/* Category tabs */}
          <div className="flex flex-wrap gap-1.5">
            {categories.map((cat) => {
              const active = activeCategory === cat;
              return (
                <button
                  key={cat}
                  onClick={() => setActiveCategory(cat)}
                  type="button"
                  className={`rounded-lg border-2 border-black px-3 py-1.5 font-mono text-xs font-black uppercase transition-all ${
                    active
                      ? "bg-[#FFE600] text-black shadow-brutal-xs translate-x-[-1px] translate-y-[-1px]"
                      : "bg-white text-black/70 hover:bg-yellow-50 hover:text-black"
                  }`}
                >
                  {cat}
                </button>
              );
            })}
          </div>

          {/* Search box */}
          <div className="relative w-full sm:w-64">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-black/50" />
            <input
              type="text"
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              placeholder="Filter contracts or tools..."
              className="w-full rounded-lg border-2 border-black bg-white py-1.5 pl-9 pr-3 font-mono text-xs font-bold text-black shadow-brutal-xs focus:outline-none focus:bg-yellow-50"
            />
          </div>
        </div>
      </div>

      {/* Contracts Accordion / List */}
      <div className="space-y-4">
        {filteredContracts.map((contract) => {
          const isExpanded = expandedContract === contract.number;
          return (
            <div
              key={contract.id}
              className="rounded-xl border-3 border-black bg-white shadow-brutal overflow-hidden transition-all"
            >
              {/* Header Bar (Click to toggle) */}
              <button
                onClick={() =>
                  setExpandedContract(isExpanded ? null : contract.number)
                }
                type="button"
                className={`w-full text-left p-5 flex items-center justify-between gap-4 border-b-2 transition-colors ${
                  isExpanded ? "bg-[#F7F5EE] border-black" : "bg-white border-transparent hover:bg-yellow-50/60"
                }`}
              >
                <div className="flex flex-wrap items-center gap-3">
                  <span className="flex h-8 w-12 items-center justify-center rounded-lg border-2 border-black bg-black font-mono text-xs font-black text-[#FFE600] shadow-brutal-xs">
                    {contract.id}
                  </span>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-base md:text-lg font-black uppercase tracking-tight text-black">
                        {contract.name}
                      </h3>
                      <Badge color={contract.badgeColor}>{contract.category}</Badge>
                    </div>
                    <p className="font-mono text-xs font-bold text-black/60">
                      {contract.tagline}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <span className="hidden sm:inline font-mono text-xs font-bold text-black/50">
                    {contract.tools.length} Tool{contract.tools.length === 1 ? "" : "s"}
                  </span>
                  {isExpanded ? (
                    <ChevronUp className="h-5 w-5 text-black" />
                  ) : (
                    <ChevronDown className="h-5 w-5 text-black" />
                  )}
                </div>
              </button>

              {/* Expanded Detailed Content */}
              {isExpanded && (
                <div className="p-6 space-y-6 bg-white border-t-2 border-black/10 font-mono text-xs">
                  {/* Two Column Overview: Standard Set vs Architectural Implication */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="rounded-xl border-2 border-black bg-[#F7F5EE] p-4 shadow-brutal-xs space-y-2">
                      <h4 className="font-black uppercase text-black text-[11px] flex items-center gap-1.5">
                        <FileText className="h-3.5 w-3.5 text-black" />
                        What Standard This Sets:
                      </h4>
                      <p className="font-semibold text-black/80 leading-relaxed">
                        {contract.standardSet}
                      </p>
                    </div>

                    <div className="rounded-xl border-2 border-black bg-[#FEF08A] p-4 shadow-brutal-xs space-y-2">
                      <h4 className="font-black uppercase text-black text-[11px] flex items-center gap-1.5">
                        <Layers className="h-3.5 w-3.5 text-black" />
                        Architectural &amp; Ecosystem Implication:
                      </h4>
                      <p className="font-semibold text-black/85 leading-relaxed">
                        {contract.architecturalImplication}
                      </p>
                    </div>
                  </div>

                  {/* Implementing MCP Tools */}
                  <div className="space-y-2">
                    <h4 className="font-black uppercase text-black text-[11px]">
                      Implementing MCP Tools ({contract.tools.length}):
                    </h4>
                    <div className="flex flex-wrap gap-2">
                      {contract.tools.map((tool) => (
                        <code
                          key={tool}
                          className="rounded-md border-2 border-black bg-black px-2.5 py-1 text-xs font-bold text-[#55EFC4] shadow-brutal-xs"
                        >
                          {tool}
                        </code>
                      ))}
                    </div>
                  </div>

                  {/* Schema Wire Example */}
                  <div className="space-y-2">
                    <h4 className="font-black uppercase text-black text-[11px]">
                      Wire Protocol Schema Example ({contract.id}):
                    </h4>
                    <CodeBlock
                      code={contract.schemaExample}
                      language="json"
                      filename={`contract_${contract.number}_payload.json`}
                    />
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
