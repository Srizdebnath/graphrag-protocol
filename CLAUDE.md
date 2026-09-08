# graphrag-protocol — Project Instructions

> Universal GraphRAG Interoperability Protocol. 10 contracts. MCP server. Reference adapters. Hackathon-winning demo.

---

## What This Is

`graphrag-protocol` is a standard interface specification + reference MCP server that lets ANY agent query ANY GraphRAG backend uniformly. It fills the missing middle layer between GQL (graph query standard at the bottom) and MCP (agent connectivity standard at the top).

**The ecosystem problem:** Every GraphRAG engine (TigerGraph, Neo4j, LightRAG, LlamaIndex, FalkorDB, Microsoft GraphRAG) reinvents retrieval, subgraph serialization, provenance, and evaluation with incompatible interfaces. Switching backends means rewriting your retrieval layer. This protocol fixes that.

**Hackathon goal:** Build the protocol + reference implementation + a working 3-pipeline demo (LLM-only, Basic RAG, GraphRAG) that proves token reduction and accuracy gains, with an interactive Next.js dashboard.

**Lasting goal:** A protocol that becomes the "JDBC for GraphRAG" — adopted across vendors, frameworks, and agent systems.

---

## Quick Start

```bash
# 1. Clone and enter
git clone https://github.com/YOUR_USERNAME/graphrag-protocol.git
cd graphrag-protocol

# 2. Python environment
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 3. TigerGraph Cloud (Savanna)
#    Your workspace is already running on TigerGraph Cloud.
#    Copy your connection details from the Savanna console into .env
#    (see Environment Variables below)

# 4. Load schema + sample data
python hackathon/scripts/build_kg.py

# 5. Start MCP server
python -m mcp_server.server

# 6. Frontend (Next.js)
cd frontend
npm install
npm run dev
# Open http://localhost:3000

# 7. Run benchmark
python hackathon/scripts/run_benchmark.py
```

---

## Environment Variables

Create `.env` in project root:

```bash
# LLM (same model across ALL pipelines — hackathon rule)
GOOGLE_API_KEY=your_gemini_api_key_here
LLM_MODEL=gemini-3.8-flash
# Use gemini-3.8-flash for speed (default), gemini-3.8-pro for complex answers if needed

# TigerGraph Cloud (Savanna)
#    Get these from your Savanna workspace console:
#    Workspace Host (General → Workspace → Host) and Database Secrets
TIGERGRAPH_HOST=https://tg-<workspace-id>.tg-<org-id>.i.tgcloud.io
TIGERGRAPH_PORT=443
TIGERGRAPH_GSQL_SECRET=your_secret_here
TIGERGRAPH_GRAPH_NAME=GraphragProtocol
TIGERGRAPH_USE_SSL=true
TIGERGRAPH_WORKSPACE_ID=<workspace-uuid>

# Neo4j (reference adapter, optional)
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=change_me

# Evaluation
BERTSCORE_MODEL=roberta-large
EVAL_OUTPUT_DIR=./hackathon/results

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws
```

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **Protocol spec** | JSON Schema + Python dataclasses | Schema-first, language-agnostic |
| **MCP server** | Python + `mcp` SDK + `pydantic` | Official MCP SDK, type-safe contracts |
| **TigerGraph adapter** | `pyTigerGraph` | Official Python client |
| **LLM** | Google Gemini Flash/Pro | Free tier, fast, hackathon-friendly |
| **Vector store** | ChromaDB (for Basic RAG pipeline) | Simple, local, no infra |
| **Evaluation** | `bert-score` + custom LLM judge | Hackathon evaluation requirements |
| **Frontend** | Next.js 14 + TypeScript + Tailwind | Dashboard, query panel, graph viz |
| **Graph visualization** | `@vis.js/network` or `react-force-graph` | Animated graph traversal |
| **Charts** | `recharts` | Token/latency/cost comparison charts |
| **Deployment** | Docker Compose (Neo4j only) + TigerGraph Cloud | TigerGraph on Savanna, Neo4j local for reference adapter |

---

## Project Structure

```
graphrag-protocol/
│
├── CLAUDE.md                              # THIS FILE — project instructions
├── README.md                              # Public-facing documentation
├── SPEC.md                                # Full protocol specification (10 contracts)
├── LICENSE                                # MIT
│
├── pyproject.toml                         # Python package config
├── requirements.txt                       # Python dependencies
├── .env.example                           # Environment variable template
├── docker-compose.yml                     # Neo4j only (TigerGraph is on Savanna Cloud)
│
│
├── schemas/                               # JSON Schema definitions (language-agnostic)
│   ├── retrieval-request.json             # Contract 1: Standard query format
│   ├── subgraph-context.json              # Contract 2: Standard response format
│   ├── provenance.json                    # Contract 5: Citation/audit trail
│   ├── graph-schema.json                  # Contract 3: Schema introspection response
│   ├── ingestion-config.json              # Contract 4: Document ingestion config
│   ├── federation-config.json             # Contract 6: Multi-backend config
│   ├── stream-event.json                  # Contract 7: Graph change events
│   ├── prompt-format-config.json          # Contract 8: LLM formatting config
│   ├── evaluation-report.json             # Contract 9: Metrics report
│   └── access-policy.json                 # Contract 10: Authorization model
│
│
├── mcp_server/                            # Reference MCP server implementation
│   ├── __init__.py
│   ├── server.py                          # Main MCP server (16 tools)
│   ├── protocol.py                        # Protocol contract definitions (Pydantic)
│   │
│   ├── contracts/                         # Contract implementations
│   │   ├── __init__.py
│   │   ├── base.py                        # Abstract contract interface
│   │   ├── retrieval.py                   # C1: 7 retrieval operations
│   │   ├── schema_discovery.py            # C3: Schema introspection
│   │   ├── construction.py                # C4: KG building from documents
│   │   ├── provenance.py                  # C5: Citation tracing
│   │   ├── federation.py                  # C6: Multi-backend queries
│   │   ├── streaming.py                   # C7: Real-time graph updates
│   │   ├── prompt_format.py               # C8: Context → LLM text
│   │   ├── evaluation.py                  # C9: Standard metrics
│   │   └── access_control.py              # C10: Permissions
│   │
│   ├── adapters/                          # Pluggable backend adapters
│   │   ├── __init__.py
│   │   ├── base.py                        # Abstract BaseGraphRAGAdapter
│   │   ├── tigergraph_adapter.py          # TigerGraph (primary, hackathon)
│   │   ├── neo4j_adapter.py               # Neo4j (reference, optional)
│   │   ├── lightrag_adapter.py            # LightRAG (reference, optional)
│   │   └── vector_adapter.py              # ChromaDB (for Basic RAG pipeline)
│   │
│   ├── formatters/                        # Contract 8: Context formatters
│   │   ├── __init__.py
│   │   ├── base.py                        # Abstract BaseFormatter
│   │   ├── markdown_formatter.py          # Markdown with inline citations
│   │   ├── structured_formatter.py        # JSON-structured context
│   │   ├── xml_formatter.py              # XML for structured prompts
│   │   └── yaml_formatter.py             # YAML compact format
│   │
│   └── evaluators/                        # Contract 9: Evaluation
│       ├── __init__.py
│       ├── retrieval_eval.py              # Token count, latency, precision@k
│       ├── answer_eval.py                 # LLM-as-Judge + BERTScore
│       ├── cost_eval.py                   # Token/cost tracking per query
│       └── cross_backend_eval.py          # Multi-backend comparison
│
│
├── eval/                                  # Evaluation harness
│   ├── __init__.py
│   ├── benchmark.py                       # Main benchmark runner
│   ├── metrics.py                         # Standard metric calculations
│   ├── dataset.py                         # Dataset loader
│   ├── queries.py                         # Benchmark query definitions
│   └── reports/                           # Generated reports (gitignored)
│
│
├── hackathon/                             # Hackathon submission code
│   ├── pipeline_1_llm_only.py             # LLM-only baseline
│   ├── pipeline_2_basic_rag.py            # ChromaDB + Gemini
│   ├── pipeline_3_graphrag.py             # TigerGraph via protocol
│   │
│   ├── scripts/
│   │   ├── download_papers.py             # Fetch arXiv papers
│   │   ├── build_kg.py                    # Build KG in TigerGraph
│   │   ├── run_benchmark.py               # Run 3-pipeline comparison
│   │   └── generate_report.py             # Generate final metrics report
│   │
│   ├── data/
│   │   ├── papers/                        # Downloaded arXiv papers (JSON)
│   │   ├── kg/                            # Pre-built KG snapshots
│   │   └── queries/
│   │       ├── single_hop.json            # Single-fact queries (RAG-friendly)
│   │       ├── multi_hop.json             # Multi-hop queries (GraphRAG wins)
│   │       ├── global.json                # Global synthesis queries
│   │       ├── comparison.json            # Comparison queries
│   │       └── reference_answers.json     # Reference answers for evaluation
│   │
│   └── results/                           # Generated results (gitignored)
│
│
├── frontend/                              # Next.js dashboard
│   ├── package.json
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── postcss.config.js
│   │
│   ├── public/
│   │   └── favicon.ico
│   │
│   └── src/
│       ├── app/
│       │   ├── layout.tsx                 # Root layout
│       │   ├── page.tsx                   # Landing / overview page
│       │   ├── globals.css                # Global styles
│       │   │
│       │   ├── query/
│       │   │   └── page.tsx               # Side-by-side query comparison
│       │   │
│       │   ├── benchmark/
│       │   │   └── page.tsx               # Full benchmark results
│       │   │
│       │   ├── protocol/
│       │   │   └── page.tsx               # Protocol explorer / schema viewer
│       │   │
│       │   └── graph/
│       │       └── page.tsx               # Interactive graph visualization
│       │
│       ├── components/
│       │   ├── layout/
│       │   │   ├── Navbar.tsx              # Navigation bar
│       │   │   ├── Sidebar.tsx             # Side navigation
│       │   │   └── Footer.tsx             # Footer
│       │   │
│       │   ├── query/
│       │   │   ├── QueryPanel.tsx          # Query input + 3-pipeline results
│       │   │   ├── PipelineResult.tsx      # Single pipeline result card
│       │   │   ├── TokenComparison.tsx     # Token usage comparison chart
│       │   │   └── LatencyChart.tsx        # Response latency chart
│       │   │
│       │   ├── benchmark/
│       │   │   ├── BenchmarkTable.tsx      # Results table
│       │   │   ├── MetricsSummary.tsx      # Summary statistics
│       │   │   ├── AccuracyRadar.tsx       # Radar chart (accuracy, tokens, etc.)
│       │   │   └── CostAccumulation.tsx    # Cumulative cost savings chart
│       │   │
│       │   ├── graph/
│       │   │   ├── GraphVisualization.tsx  # D3.js/vis.js graph view
│       │   │   ├── EntityDetails.tsx       # Entity detail panel
│       │   │   └── TraversalTimeline.tsx   # Step-by-step traversal view
│       │   │
│       │   ├── protocol/
│       │   │   ├── SchemaViewer.tsx        # Graph schema explorer
│       │   │   ├── ContractDoc.tsx         # Contract documentation viewer
│       │   │   └── AdapterList.tsx         # Available adapters list
│       │   │
│       │   └── shared/
│       │       ├── LoadingSpinner.tsx      # Loading indicator
│       │       ├── ErrorBoundary.tsx       # Error handling
│       │       ├── Badge.tsx              # Status badges
│       │       └── Card.tsx               # Reusable card component
│       │
│       ├── lib/
│       │   ├── api.ts                     # API client (fetch wrapper)
│       │   ├── types.ts                   # TypeScript types (mirrors protocol schemas)
│       │   ├── hooks/
│       │   │   ├── useQuery.ts            # Query hook (3-pipeline comparison)
│       │   │   ├── useBenchmark.ts        # Benchmark results hook
│       │   │   └── useGraph.ts            # Graph data hook
│       │   └── utils/
│       │       ├── format.ts             # Number/date formatting
│       │       └── colors.ts             # Pipeline color scheme
│       │
│       └── styles/
│           └── components.css             # Component-specific styles
│
│
├── examples/                              # Usage examples
│   ├── quickstart.py                      # 5-minute protocol demo
│   ├── multi_backend.py                   # Federation across backends
│   └── custom_adapter.py                  # Building your own adapter
│
│
└── docs/                                  # Additional documentation
    ├── architecture.md                    # Architecture deep-dive
    ├── adapter-guide.md                   # How to build a new adapter
    ├── evaluation-methodology.md          # How metrics are calculated
    └── api-reference.md                   # API reference for MCP tools
```

---

## Phases

### Phase 1: Protocol Foundation (Days 1-3)

**Goal:** Protocol spec written, TigerGraph running, core Python types defined.

#### Tasks

- [ ] **1.1** Write `SPEC.md` with all 10 contracts, examples, and rationale
- [ ] **1.2** Create all JSON schemas in `schemas/` (start with `retrieval-request.json`, `subgraph-context.json`, `provenance.json`)
- [ ] **1.3** Set up TigerGraph Cloud connection:
  - Log into your Savanna workspace at console.tigergraphcloud.com
  - Copy workspace URL, graph name, and credentials into `.env`
  - Test connection with `pyTigerGraph`:
  ```python
  from pyTigerGraph import TigerGraphConnection
  conn = TigerGraphConnection(
      host='your-savanna-url.tigergraphcloud.com',
      graphname='graphrag_hackathon',
      username='tigergraph',
      password='your_password',
      use_ssl=True
  )
  print(conn.getVertexTypes())  # Should list vertex types
  ```
- [ ] **1.4** Create `mcp_server/protocol.py` — Pydantic models for all 10 contracts
- [ ] **1.5** Create `mcp_server/contracts/base.py` — Abstract contract interface
- [ ] **1.6** Create `mcp_server/adapters/base.py` — Abstract `BaseGraphRAGAdapter` with all 7 retrieval operations + schema + construction + provenance
- [ ] **1.7** Set up `pyproject.toml` with all dependencies
- [ ] **1.8** Create `.env.example` with all required variables

#### Verification
- `python -c "from mcp_server.protocol import *; print('Protocol types OK')"` passes
- TigerGraph GSQL shell is accessible
- All JSON schemas validate against example payloads

---

### Phase 2: Core Contracts + TigerGraph Adapter (Days 4-7)

**Goal:** Retrieval, schema, provenance contracts working. TigerGraph adapter functional.

#### Tasks

- [ ] **2.1** Implement `mcp_server/contracts/retrieval.py` — All 7 operations:
  - `local_search(query, entity_hints, depth, top_k, filters)`
  - `global_search(query, community_level, top_communities)`
  - `hybrid_search(query, vector_weight, graph_weight, top_k, depth)`
  - `entity_lookup(entity_id, entity_name, entity_type, depth)`
  - `path_search(source, target, max_hops)`
  - `neighborhood(entity_id, depth, edge_types)`
  - `community_members(community_id, include_summary)`

- [ ] **2.2** Implement `mcp_server/contracts/schema_discovery.py`:
  - `get_schema(graph_id)` → vertex types, edge types, attributes, counts
  - `get_entity_types()` → all entity types with stats
  - `get_relationship_types()` → all relationship types
  - `get_sample_entities(entity_type, count)` → sample data for LLM context
  - `get_statistics()` → total vertices, edges, density, components

- [ ] **2.3** Implement `mcp_server/contracts/provenance.py`:
  - `trace_citation(fact_id)` → full citation chain
  - `get_traversal_trajectory(query_id)` → visited + cited entities
  - `get_source_documents(entity_id)` → source documents for entity
  - `audit_provenance_completeness(query_id)` → trajectory completeness score

- [ ] **2.4** Implement `mcp_server/adapters/tigergraph_adapter.py`:
  - Map TigerGraph's REST++ API to protocol's standard operations
  - Use `pyTigerGraph` for connection, query execution, schema access
  - Implement `vectorSearch()` integration for hybrid search
  - Implement community detection integration
  - Handle TigerGraph's accumulator-based results → standard SubgraphContext

- [ ] **2.5** Implement `mcp_server/formatters/markdown_formatter.py`:
  - Convert SubgraphContext → Markdown with inline citations
  - Include entities, relationships, paths, communities
  - Add token count and retrieval metadata footer

- [ ] **2.6** Implement `mcp_server/formatters/structured_formatter.py`:
  - Convert SubgraphContext → clean JSON for programmatic use
  - Maintain all provenance metadata

- [ ] **2.7** Write `examples/quickstart.py`:
  ```python
  from mcp_server.adapters.tigergraph_adapter import TigerGraphAdapter
  from mcp_server.contracts.retrieval import RetrievalContract
  from mcp_server.formatters.markdown_formatter import MarkdownFormatter
  
  adapter = TigerGraphAdapter(host="localhost", graph="graphrag_hackathon")
  contract = RetrievalContract(adapter)
  
  context = contract.local_search(
      query="What drugs interact with metformin?",
      entity_hints=["metformin"],
      depth=2,
      top_k=5
  )
  
  formatter = MarkdownFormatter()
  print(formatter.format_context(context))
  ```

#### Verification
- TigerGraph adapter connects and returns data for all 7 operations
- Markdown formatter produces readable output with citations
- `examples/quickstart.py` runs end-to-end

---

### Phase 3: MCP Server (Days 8-9)

**Goal:** Full MCP server with 16 tools, testable with LangGraph/CrewAI.

#### Tasks

- [ ] **3.1** Implement `mcp_server/server.py` with all 16 tools:
  ```python
  # Retrieval tools (7)
  "graphrag_search"         # Unified search (auto-routes to local/global/hybrid)
  "graphrag_entity"         # Entity lookup
  "graphrag_path"           # Path search
  "graphrag_neighborhood"   # Neighborhood expansion
  "graphrag_community"      # Community members + summary
  "graphrag_schema"         # Schema discovery
  "graphrag_sample"         # Sample entities for context
  
  # Construction tools (2)
  "graphrag_ingest"         # Ingest documents into KG
  "graphrag_extract"        # Extract entities from text
  
  # Federation tools (1)
  "graphrag_federated"      # Search across multiple backends
  
  # Evaluation tools (2)
  "graphrag_evaluate"       # Run standard metrics on query/answer
  "graphrag_benchmark"      # Compare backends on same queries
  
  # Provenance tools (1)
  "graphrag_provenance"     # Trace full citation chain
  
  # Admin tools (3)
  "graphrag_status"         # Backend health + stats
  "graphrag_config"         # Get/set retrieval config
  "graphrag_list_backends"  # List registered backends
  ```

- [ ] **3.2** Add MCP server configuration (stdio + HTTP/SSE transports)
- [ ] **3.3** Add multi-profile support (different TigerGraph connections)
- [ ] **3.4** Write unit tests for all 16 tools

#### Verification
- MCP server starts and lists all 16 tools
- Can connect via stdio transport
- Can connect via HTTP/SSE transport
- LangGraph agent can discover and call tools

---

### Phase 4: Dataset + Knowledge Graph (Days 10-12)

**Goal:** arXiv paper dataset acquired, knowledge graph built in TigerGraph.

#### Tasks

- [ ] **4.1** Write `hackathon/scripts/download_papers.py`:
  - Fetch 500-1000 NLP/AI papers from arXiv API
  - Focus areas: attention mechanisms, transformers, graph neural networks, RAG, knowledge graphs, entity resolution
  - Extract: title, authors, abstract, categories, submission date, DOI
  - Fetch citation data from Semantic Scholar API
  - Save as JSONL to `hackathon/data/papers/`
  - Target: ~2-3M tokens total

- [ ] **4.2** Define graph schema in TigerGraph:
  ```gsql
  -- Entity types
  CREATE VERTEX Paper(PRIMARY_ID id STRING, title STRING, abstract STRING, 
                      categories STRING, submit_date DATETIME, token_count INT)
  CREATE VERTEX Author(PRIMARY_ID id STRING, name STRING, affiliation STRING)
  CREATE VERTEX Institution(PRIMARY_ID id STRING, name STRING, country STRING)
  CREATE VERTEX Method(PRIMARY_ID id STRING, name STRING, description STRING)
  CREATE VERTEX Dataset(PRIMARY_ID id STRING, name STRING, domain STRING)
  CREATE VERTEX Concept(PRIMARY_ID id STRING, name STRING, category STRING)
  
  -- Relationship types
  CREATE DIRECTED EDGE CITES(FROM Paper, TO Paper, year INT)
  CREATE DIRECTED EDGE AUTHORED_BY(FROM Paper, TO Author, position INT)
  CREATE DIRECTED EDGE AFFILIATED_WITH(FROM Author, TO Institution)
  CREATE DIRECTED EDGE USES_METHOD(FROM Paper, TO Method)
  CREATE DIRECTED EDGE BENCHMARKS_ON(FROM Paper, TO Dataset)
  CREATE DIRECTED EDGE MENTIONS_CONCEPT(FROM Paper, TO Concept)
  CREATE DIRECTED EDGE EXTENDS(FROM Paper, TO Paper, relationship STRING)
  ```

- [ ] **4.3** Write `hackathon/scripts/build_kg.py`:
  - Load papers from JSONL
  - Extract methods, datasets, concepts from abstracts (regex + LLM)
  - Resolve author names → unique Author vertices
  - Build citation edges from Semantic Scholar data
  - Create concept edges via keyword extraction
  - Generate embeddings for Paper abstracts (for vector search)
  - Load everything into TigerGraph via REST++ API

- [ ] **4.4** Write `hackathon/scripts/download_papers.py` continuation — generate benchmark queries:
  - `single_hop.json`: 20 queries solvable with 1-hop traversal (e.g., "Who authored paper X?")
  - `multi_hop.json`: 20 queries requiring 2-3 hops (e.g., "What methods are used by papers citing paper X?")
  - `global.json`: 10 queries requiring community-level synthesis (e.g., "What are the main research trends in NLP?")
  - `comparison.json`: 10 queries requiring comparison (e.g., "How do Transformer and GNN approaches differ?")
  - `reference_answers.json`: Reference answers for all 60 queries

#### Verification
- TigerGraph has 500+ Paper vertices, 1000+ Author vertices, edges populated
- Vector embeddings are searchable via `vectorSearch()`
- All 60 benchmark queries have reference answers
- `build_kg.py` runs end-to-end in <30 minutes

---

### Phase 5: Three Pipelines (Days 13-15)

**Goal:** Three working pipelines producing answers for the same queries.

#### Tasks

- [ ] **5.1** Write `hackathon/pipeline_1_llm_only.py`:
  ```python
  def pipeline_1_llm_only(query: str, model: str = "gemini-2.0-flash") -> dict:
      """Pipeline 1: No retrieval. Pure LLM. Worst-case baseline."""
      response = call_gemini(query, model=model)
      return {
          "answer": response.text,
          "tokens": response.usage,
          "latency_ms": response.latency,
          "retrieval_method": "none"
      }
  ```

- [ ] **5.2** Write `hackathon/pipeline_2_basic_rag.py`:
  ```python
  def pipeline_2_basic_rag(query: str, model: str = "gemini-2.0-flash") -> dict:
      """Pipeline 2: Vector similarity search + LLM. Industry standard."""
      # Embed query
      query_embedding = embed(query)
      
      # Retrieve top-k chunks from ChromaDB
      results = chroma_db.query(query_embedding, top_k=10)
      
      # Format context
      context = format_chunks(results)
      
      # Generate answer
      prompt = f"Context:\n{context}\n\nQuestion: {query}\nAnswer:"
      response = call_gemini(prompt, model=model)
      
      return {
          "answer": response.text,
          "tokens": response.usage,
          "latency_ms": response.latency,
          "retrieval_method": "vector_similarity",
          "context_tokens": count_tokens(context)
      }
  ```

- [ ] **5.3** Write `hackathon/pipeline_3_graphrag.py`:
  ```python
  def pipeline_3_graphrag(query: str, model: str = "gemini-2.0-flash") -> dict:
      """Pipeline 3: GraphRAG via protocol. TigerGraph backend."""
      # Use protocol to search
      adapter = TigerGraphAdapter(...)
      contract = RetrievalContract(adapter)
      
      # Auto-route: detect query type, choose retrieval mode
      if is_global_query(query):
          context = contract.global_search(query)
      elif is_entity_query(query):
          context = contract.local_search(query, depth=2)
      else:
          context = contract.hybrid_search(query)
      
      # Format with citations
      formatter = MarkdownFormatter()
      formatted_context = formatter.format_context(context)
      
      # Generate answer
      prompt = f"Context:\n{formatted_context}\n\nQuestion: {query}\nAnswer:"
      response = call_gemini(prompt, model=model)
      
      return {
          "answer": response.text,
          "tokens": response.usage,
          "latency_ms": response.latency,
          "retrieval_method": "graphrag",
          "context_tokens": count_tokens(formatted_context),
          "provenance": context.provenance,
          "entities_used": len(context.results.entities),
          "graph_hops": context.metrics.graph_hops_traversed
      }
  ```

- [ ] **5.4** Write `hackathon/scripts/run_benchmark.py`:
  - Load all 60 queries
  - Run each query through all 3 pipelines
  - Record: answer, tokens, latency, cost
  - Run LLM-as-Judge evaluation (PASS/FAIL + reason)
  - Compute BERTScore F1
  - Save results to `hackathon/results/`
  - Generate summary statistics

- [ ] **5.5** Implement evaluation in `mcp_server/evaluators/`:
  - `retrieval_eval.py`: Token count, latency, precision@k, coverage
  - `answer_eval.py`: LLM-as-Judge (Gemini evaluates answers), BERTScore
  - `cost_eval.py`: Cost per query, session accumulation, savings vs RAG
  - `cross_backend_eval.py`: Backend comparison metrics

#### Verification
- All 3 pipelines produce answers for all 60 queries
- LLM-as-Judge evaluates all answers (>=90% pass rate target)
- BERTScore computed for all answers
- Results saved in structured format

---

### Phase 6: Frontend Dashboard (Days 16-20)

**Goal:** Next.js dashboard with query comparison, benchmark results, and graph visualization.

#### Tasks

- [ ] **6.1** Initialize Next.js project:
  ```bash
  cd frontend
  npx create-next-app@latest . --typescript --tailwind --app --src-dir
  npm install recharts @vis.js/network react-force-graph-2d
  ```

- [ ] **6.2** Set up API client (`src/lib/api.ts`):
  ```typescript
  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
  
  export async function runQuery(query: string, mode: 'all' | 'rag' | 'graphrag' = 'all') {
    const res = await fetch(`${API_URL}/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, mode })
    })
    return res.json()
  }
  
  export async function getBenchmarkResults() {
    const res = await fetch(`${API_URL}/benchmark/results`)
    return res.json()
  }
  
  export async function getGraphSchema() {
    const res = await fetch(`${API_URL}/schema`)
    return res.json()
  }
  
  export async function getGraphVisualization(entityId?: string) {
    const res = await fetch(`${API_URL}/graph/visualize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ entity_id: entityId })
    })
    return res.json()
  }
  ```

- [ ] **6.3** Define TypeScript types (`src/lib/types.ts`) mirroring protocol schemas:
  ```typescript
  interface SubgraphContext {
    protocol: string
    operation: string
    query: { text: string; entity_hints?: string[]; depth: number; top_k: number }
    results: {
      entities: Entity[]
      relationships: Relationship[]
      paths: Path[]
      communities: Community[]
      text_chunks: TextChunk[]
    }
    provenance: Provenance
    metrics: RetrievalMetrics
  }
  
  interface PipelineResult {
    answer: string
    tokens: TokenUsage
    latency_ms: number
    retrieval_method: string
    context_tokens?: number
    provenance?: Provenance
  }
  
  interface BenchmarkResult {
    query_id: string
    query: string
    pipeline_1: PipelineResult
    pipeline_2: PipelineResult
    pipeline_3: PipelineResult
    evaluation: {
      judge_pass: boolean
      judge_reason: string
      bertscore_f1: number
    }
  }
  ```

- [ ] **6.4** Build Query Page (`src/app/query/page.tsx`):
  - Query input bar at top
  - Three result cards side by side (Pipeline 1, 2, 3)
  - Each card shows: answer, tokens used, latency, cost
  - Token comparison bar chart below
  - Latency comparison chart
  - "Query type" indicator (single-hop, multi-hop, global)

- [ ] **6.5** Build Benchmark Page (`src/app/benchmark/page.tsx`):
  - Summary statistics cards (total queries, avg token reduction, avg accuracy)
  - Full results table (sortable by query type, token reduction, accuracy)
  - Radar chart: accuracy, tokens, latency, provenance completeness
  - Cost accumulation line chart (savings over N queries)
  - Per-query-type breakdown (single-hop vs multi-hop vs global)

- [ ] **6.6** Build Graph Visualization Page (`src/app/graph/page.tsx`):
  - Interactive graph view using vis.js or react-force-graph
  - Nodes = entities, edges = relationships
  - Click entity → show details panel
  - "Animate traversal" button → step-by-step hop animation
  - Color-code by entity type
  - Size nodes by degree/centrality
  - Show query path highlighted

- [ ] **6.7** Build Protocol Explorer Page (`src/app/protocol/page.tsx`):
  - Graph schema viewer (vertex types, edge types, attributes)
  - Contract documentation viewer (renders SPEC.md sections)
  - Available adapters list with status indicators
  - Sample request/response for each contract

- [ ] **6.8** Build shared components:
  - `Navbar.tsx` — navigation between pages
  - `PipelineResult.tsx` — reusable result card
  - `TokenComparison.tsx` — bar chart component
  - `AccuracyRadar.tsx` — radar chart component
  - `LoadingSpinner.tsx`, `ErrorBoundary.tsx`

- [ ] **6.9** Add D3.js graph traversal animation:
  - Step-by-step node highlighting
  - Edge highlighting as traversal progresses
  - Info panel showing current entity/relationship
  - Play/pause/step controls

#### Verification
- All 4 pages render correctly
- Query page shows live results from all 3 pipelines
- Benchmark page displays evaluation results
- Graph visualization is interactive and animated
- No TypeScript errors, all components pass lint

---

### Phase 7: Remaining Contracts (Days 21-23)

**Goal:** All 10 contracts implemented. Protocol is complete.

#### Tasks

- [ ] **7.1** Implement `mcp_server/contracts/construction.py`:
  - `ingest(documents, schema, extraction_config)` → chunk → extract → resolve → populate
  - `extract_entities(chunks, ontology)` → entity-relationship triples
  - `resolve_entities(extracted, existing_graph, strategy)` → deduplicated triples
  - `update(document_id, content, strategy)` → incremental graph update

- [ ] **7.2** Implement `mcp_server/contracts/federation.py`:
  - `register_backend(name, adapter, weight)` → add backend
  - `federated_search(query, backends, merge_strategy, top_k)` → merged results
  - `cross_graph_entity_link(entity_name, backends)` → linked entities across backends
  - Merge strategies: reciprocal rank fusion, score fusion, entity dedup

- [ ] **7.3** Implement `mcp_server/contracts/streaming.py`:
  - `subscribe(event_types, filter_fn)` → async iterator of graph events
  - `publish_update(event)` → publish change
  - Event types: entity_created, edge_updated, community_recomputed

- [ ] **7.4** Implement `mcp_server/contracts/evaluation.py`:
  - `evaluate_retrieval(query, context, reference)` → RetrievalMetrics
  - `evaluate_answer(query, answer, reference, context)` → AnswerMetrics
  - `cross_backend_benchmark(queries, backends, references)` → BenchmarkReport

- [ ] **7.5** Implement `mcp_server/contracts/access_control.py`:
  - `check_permission(operation, graph_id, user_id, resource_filter)` → PermissionResult
  - `get_allowed_operations(user_id, graph_id)` → list of allowed operations

- [ ] **7.6** Implement reference adapters (even if not running):
  - `mcp_server/adapters/neo4j_adapter.py` — Neo4j via `neo4j` Python driver
  - `mcp_server/adapters/lightrag_adapter.py` — LightRAG via its API

- [ ] **7.7** Implement remaining formatters:
  - `mcp_server/formatters/xml_formatter.py`
  - `mcp_server/formatters/yaml_formatter.py`

- [ ] **7.8** Write `examples/multi_backend.py`:
  ```python
  from mcp_server.contracts.federation import FederationContract
  from mcp_server.adapters.tigergraph_adapter import TigerGraphAdapter
  from mcp_server.adapters.vector_adapter import VectorAdapter
  
  # Register multiple backends
  federation = FederationContract()
  federation.register_backend("tigergraph", TigerGraphAdapter(...))
  federation.register_backend("chromadb", VectorAdapter(...))
  
  # Federated search across both
  results = federation.federated_search(
      "What are the latest RAG techniques?",
      merge_strategy="reciprocal_rank_fusion"
  )
  ```

- [ ] **7.9** Write `examples/custom_adapter.py` showing how to build a new adapter

#### Verification
- All 10 contracts have implementations
- Neo4j and LightRAG adapters are structurally complete (even if not connected)
- Federation example shows multi-backend search
- Custom adapter example is clear and copy-pasteable

---

### Phase 8: Documentation + Demo (Days 24-28)

**Goal:** Complete documentation, demo video, polished submission.

#### Tasks

- [ ] **8.1** Write `README.md`:
  - Protocol overview with architecture diagram (Mermaid)
  - Quick start guide
  - Why this matters (the ecosystem problem)
  - The 10 contracts (brief descriptions)
  - Hackathon results summary
  - How to build an adapter
  - Contributing guidelines

- [ ] **8.2** Finalize `SPEC.md`:
  - Complete protocol specification
  - All 10 contracts with full API docs
  - JSON schema examples for every type
  - Rationale for each design decision

- [ ] **8.3** Write `docs/architecture.md`:
  - Deep-dive architecture diagram
  - Data flow for each operation
  - Adapter pattern explanation
  - MCP server architecture

- [ ] **8.4** Write `docs/adapter-guide.md`:
  - Step-by-step guide to building a new adapter
  - Required methods
  - Testing your adapter
  - Submitting upstream

- [ ] **8.5** Write `docs/evaluation-methodology.md`:
  - How metrics are calculated
  - LLM-as-Judge prompt template
  - BERTScore configuration
  - Cost calculation methodology

- [ ] **8.6** Record demo video (3-5 minutes):
  - 0:00-0:30 — Protocol overview (architecture diagram)
  - 0:30-1:30 — Live query comparison (all 3 pipelines)
  - 1:30-2:30 — Benchmark results dashboard
  - 2:30-3:30 — Graph traversal animation
  - 3:30-4:30 — Cross-backend federation demo
  - 4:30-5:00 — Closing: what this enables

- [ ] **8.7** Create architecture diagram (Mermaid or draw.io):
  ```mermaid
  graph TB
      subgraph "Agent Layer"
          A1[LangGraph] --> MCP
          A2[CrewAI] --> MCP
          A3[Custom Agent] --> MCP
      end
      
      subgraph "MCP Layer"
          MCP[GraphRAG MCP Server]
          MCP --> T1[graphrag_search]
          MCP --> T2[graphrag_entity]
          MCP --> T3[graphrag_path]
          MCP --> T4[...16 tools]
      end
      
      subgraph "Protocol Layer"
          T1 --> P[GraphRAG Protocol]
          P --> C1[Retrieval Contract]
          P --> C2[Provenance Contract]
          P --> C3[Schema Contract]
          P --> C4[...10 contracts]
      end
      
      subgraph "Adapter Layer"
          C1 --> AD1[TigerGraph Adapter]
          C1 --> AD2[Neo4j Adapter]
          C1 --> AD3[LightRAG Adapter]
      end
      
      subgraph "Database Layer"
          AD1 --> DB1[(TigerGraph)]
          AD2 --> DB2[(Neo4j)]
          AD3 --> DB3[(LightRAG)]
      end
  ```

- [ ] **8.8** Final testing:
  - Run full benchmark suite
  - Verify all 3 pipelines work
  - Verify dashboard displays correctly
  - Verify MCP server tools work
  - Fix any remaining bugs

- [ ] **8.9** Polish:
  - Clean up code
  - Add docstrings
  - Remove debug prints
  - Ensure all imports are clean
  - Add `.gitignore` entries for results/, .env, __pycache__

#### Verification
- README.md is comprehensive and accurate
- SPEC.md covers all 10 contracts
- Architecture diagram renders correctly
- Demo video is uploaded
- All tests pass
- No lint errors

---

## Key Technical Patterns

### Adapter Pattern

Every backend adapter implements `BaseGraphRAGAdapter`:

```python
from abc import ABC, abstractmethod
from mcp_server.protocol import SubgraphContext, GraphSchema, Provenance

class BaseGraphRAGAdapter(ABC):
    """All GraphRAG backends must implement this interface."""
    
    @abstractmethod
    def local_search(self, query: str, entity_hints: list[str] = None,
                     depth: int = 2, top_k: int = 10, 
                     filters: dict = None) -> SubgraphContext: ...
    
    @abstractmethod
    def global_search(self, query: str, community_level: int = 2,
                      top_communities: int = 10) -> SubgraphContext: ...
    
    @abstractmethod
    def hybrid_search(self, query: str, vector_weight: float = 0.5,
                      graph_weight: float = 0.5, top_k: int = 10,
                      depth: int = 2) -> SubgraphContext: ...
    
    @abstractmethod
    def entity_lookup(self, entity_id: str = None, entity_name: str = None,
                      entity_type: str = None, depth: int = 1) -> SubgraphContext: ...
    
    @abstractmethod
    def path_search(self, source: str, target: str,
                    max_hops: int = 4) -> SubgraphContext: ...
    
    @abstractmethod
    def neighborhood(self, entity_id: str, depth: int = 2,
                     edge_types: list[str] = None) -> SubgraphContext: ...
    
    @abstractmethod
    def community_members(self, community_id: str,
                          include_summary: bool = True) -> SubgraphContext: ...
    
    @abstractmethod
    def get_schema(self, graph_id: str = None) -> GraphSchema: ...
    
    @abstractmethod
    def get_provenance(self, context: SubgraphContext) -> Provenance: ...
    
    @abstractmethod
    def health_check(self) -> dict: ...
```

### Pydantic Protocol Models

All protocol types are Pydantic models for validation and serialization:

```python
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

class RetrievalMode(str, Enum):
    LOCAL = "local_search"
    GLOBAL = "global_search"
    HYBRID = "hybrid_search"
    ENTITY = "entity_lookup"
    PATH = "path_search"
    NEIGHBORHOOD = "neighborhood"
    COMMUNITY = "community_members"

class RetrievalRequest(BaseModel):
    protocol: str = "graphrag/1.0"
    operation: RetrievalMode
    query: str
    entity_hints: list[str] = Field(default_factory=list)
    depth: int = Field(default=2, ge=1, le=10)
    top_k: int = Field(default=10, ge=1, le=100)
    filters: Optional[dict] = None
    backend: Optional[str] = None

class Entity(BaseModel):
    id: str
    type: str
    name: str
    properties: dict = Field(default_factory=dict)
    relevance_score: float = Field(ge=0.0, le=1.0)
    source_chunks: list[str] = Field(default_factory=list)

class Relationship(BaseModel):
    id: str
    source: str
    target: str
    type: str
    weight: float = Field(ge=0.0, le=1.0)
    properties: dict = Field(default_factory=dict)
    evidence: list[dict] = Field(default_factory=list)

class SubgraphContext(BaseModel):
    protocol: str = "graphrag/1.0"
    operation: str
    query: dict
    results: dict  # {entities, relationships, paths, communities, text_chunks}
    provenance: dict
    metrics: dict
```

### Formatter Pattern

Formatters convert SubgraphContext → LLM-ready text:

```python
from abc import ABC, abstractmethod

class BaseFormatter(ABC):
    @abstractmethod
    def format_context(self, context: SubgraphContext, 
                       max_tokens: int = 4096,
                       include_citations: bool = True) -> str: ...
    
    @abstractmethod
    def format_entity(self, entity: Entity) -> str: ...
    
    @abstractmethod
    def format_relationship(self, relationship: Relationship) -> str: ...
```

---

## Commands Reference

### Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Run MCP server (stdio transport)
python -m mcp_server.server

# Run MCP server (HTTP transport)
python -m mcp_server.server --transport http --port 8000

# Run tests
pytest tests/ -v

# Run linter
ruff check mcp_server/ hackathon/ eval/

# Run type checker
mypy mcp_server/

# Format code
ruff format mcp_server/ hackathon/ eval/
```

### TigerGraph Cloud (Savanna)

```bash
# Test connection to your Savanna workspace
python -c "
from pyTigerGraph import TigerGraphConnection
conn = TigerGraphConnection(
    host='your-savanna-workspace-url.tigergraphcloud.com',
    graphname='graphrag_hackathon',
    username='tigergraph',
    password='your_password',
    use_ssl=True
)
print('Connected!')
print(conn.getVertexCount('Paper'))
"

# Load schema + data into Savanna
python hackathon/scripts/build_kg.py

# Run GSQL queries via pyTigerGraph (recommended over CLI)
python -c "
from pyTigerGraph import TigerGraphConnection
conn = TigerGraphConnection(
    host='your-savanna-workspace-url.tigergraphcloud.com',
    graphname='graphrag_hackathon',
    username='tigergraph',
    password='your_password',
    use_ssl=True
)
result = conn.runInstalledQuery('your_query_name', {'param': 'value'})
print(result)
"

# Access GSQL via Savanna web console
# Open your Savanna workspace URL in browser → Query tab → GSQL Shell
```

### Dataset

```bash
# Download papers
python hackathon/scripts/download_papers.py --count 1000 --categories cs.AI,cs.CL,cs.LG

# Build knowledge graph
python hackathon/scripts/build_kg.py

# Run benchmark
python hackathon/scripts/run_benchmark.py --queries 60 --pipelines all

# Generate report
python hackathon/scripts/generate_report.py --input hackathon/results/ --output hackathon/results/report.md
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Development server
npm run dev

# Build for production
npm run build

# Start production server
npm start

# Lint
npm run lint
```

### Docker

```bash
# No Docker needed for TigerGraph — it's on Savanna Cloud.
# Docker is only used if you want to run Neo4j locally for the reference adapter:

# Optional: Start Neo4j for reference adapter testing
docker compose up -d neo4j
# Neo4j browser: http://localhost:7474
```

---

## Evaluation Criteria Alignment

| Hackathon Criterion | Weight | How We Win It |
|---|---|---|
| **Token Reduction** | 30% | Protocol forces efficient subgraph serialization. TigerGraph adapter targets >60% reduction vs Basic RAG. Standard context format ensures no wasted tokens. |
| **Answer Accuracy** | 30% | Provenance contract ensures full citation chain. LLM-as-Judge pass >=90%. BERTScore F1 >=0.55 rescaled. |
| **Performance** | 20% | TigerGraph in-memory MPP + protocol's targeted retrieval. Target <2s per query. |
| **Engineering & Storytelling** | 20% | 10-contract protocol spec + working MCP server + Next.js dashboard + D3.js graph viz + demo video. The engineering IS the story. |

---

## Common Pitfalls

1. **TigerGraph Cloud cold start** — Savanna workspaces may take 30-60s to wake up from sleep. Check workspace status in console before querying.
2. **GSQL syntax** — Use V3 syntax (`SYNTAX v3`) for new queries. V1 is legacy.
3. **pyTigerGraph connection** — For Savanna, use port 443 with `use_ssl=True`. Don't use port 9000 (that's local Docker).
4. **Token counting** — Count tokens BEFORE sending to LLM, not after. Use `tiktoken` or model-specific tokenizer.
5. **BERTScore baseline** — Must use `rescale_with_baseline=True` with `roberta-large` for hackathon metrics.
6. **Same LLM** — ALL three pipelines MUST use the same model. Violating this = disqualification.
7. **Query type detection** — Don't hardcode routing. Use the protocol's `graphrag_search` tool which auto-routes.
8. **Frontend API calls** — Use the `NEXT_PUBLIC_` prefix for env vars in Next.js client-side code.
9. **Graph visualization** — Don't render the full graph. Filter to query-relevant subgraph (max 100 nodes).
10. **Provenance completeness** — Track visited-not-cited entities. This is a novel contribution per IJCAI 2026.
11. **Savanna workspace URL** — Your hostname includes the region suffix (e.g., `xxx.us-west-2.aws.cloud.tigergraph.com`). Copy it exactly from the console.

---

## After the Hackathon

This protocol should live on. Post-hackathon roadmap:

1. **Publish SPEC.md as a standalone RFC** — Open for community review
2. **Submit PRs to TigerGraph** — Integrate protocol as official interface for `tigergraph-mcp`
3. **Submit PRs to LlamaIndex** — PropertyGraphStore adapter implementing the protocol
4. **Submit PRs to LangChain** — `langchain-graphrag` package using protocol
5. **Build a protocol registry** — graphrag-protocol.org with adapter listings
6. **Write a paper** — "GraphRAG Protocol: A Standard Interface for Graph-Augmented Retrieval"
7. **Propose as MCP extension** — Official MCP tools for GraphRAG via AI Interoperability Consortium
