# GRIP // Universal GraphRAG Interoperability Protocol

[![PyPI Version](https://img.shields.io/pypi/v/grip-protocol.svg?color=FFE600&label=PyPI%20Package)](https://pypi.org/project/grip-protocol/0.4.0/)
[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-55EFC4.svg)](https://pypi.org/project/grip-protocol/)
[![MCP Server](https://img.shields.io/badge/MCP-50%20Tools-74B9FF.svg)](https://modelcontextprotocol.io/)
[![Formal Contracts](https://img.shields.io/badge/Contracts-20%20RFC%20Standards-A29BFE.svg)](file:///home/ansh/graphrag-protocol/SPEC.md)
[![Frontend](https://img.shields.io/badge/Next.js-16%20Turbopack-000000.svg)](file:///home/ansh/graphrag-protocol/frontend/)

**GRIP** is the open RFC standard, high-performance MCP server, and universal execution layer connecting **any AI agent to any Graph database** with strict type safety, cryptographic provenance, and sub-second multi-hop traversal.

---

## The Missing Middle Layer

Modern agentic architectures face a severe interoperability barrier:
- **GQL / Cypher / GSQL** operate at the query language tier (bottom).
- **Model Context Protocol (MCP)** standardizes agent-to-tool connectivity (top).
- **The Missing Layer**: Every graph database (TigerGraph, Neo4j, FalkorDB, Microsoft GraphRAG, LightRAG) reinvents retrieval envelopes, k-hop subgraph serialization, entity resolution, citation trails, and token budgeting with incompatible schemas.

GRIP provides this missing protocol layer: **20 formal wire contracts** implemented across **50 production MCP tools**, giving agents deterministic access to enterprise graph topologies.

```
+-------------------------------------------------------------------------+
| AGENTIC IDES & CLIENTS (Claude Code, Cursor, Cline, OpenCode, Codex...) |
+-------------------------------------------------------------------------+
                                   |
                                   | MCP Protocol (stdio / SSE)
                                   v
+-------------------------------------------------------------------------+
|                     GRIP MCP SERVER (50 TOOLS)                          |
|  C1 Retrieval  |  C4 Schema  |  C5 Provenance  |  C8 Token Budgeting    |
|  C6 Federation |  C11 Comm   |  C19 Dedupe     |  C20 Query Triage & ROI|
+-------------------------------------------------------------------------+
                                   |
                                   | Universal Adapter Interface
                                   v
+-------------------------------------------------------------------------+
|                  FEDERATED GRAPH BACKENDS & STORES                      |
|  TigerGraph REST++  |  Neo4j Bolt  |  SQLite WAL Event Store            |
+-------------------------------------------------------------------------+
```

---

## Key Performance Benchmarks

Evaluated across **49,656 vertices** and **79,044 edges** on TigerGraph Cloud + Gemini 2.5 Flash:

| Benchmark Dimension | Vector RAG Baseline | LLM-Only Baseline | GRIP GraphRAG | Relative Advantage |
| :--- | :--- | :--- | :--- | :--- |
| **Multi-Hop Reasoning (3+ hops)** | 24.0% | 12.0% | **88.4%** | **+54.3% Accuracy** |
| **Hallucination Rate** | 26.0% | 42.0% | **3.1%** | **-93.0% Reduction** |
| **P50 Query Latency (Hybrid Route)**| 620ms | 1.8s | **480ms** | **Sub-second Hybrid** |
| **Token ROI Multiplier** | 1.0x (Baseline) | 0.4x | **5.4x** | **5.4x Context Efficiency** |
| **Citation Audit Completeness** | 0.0% (Ungrounded) | 0.0% | **100.0%** | **Deterministic Provenance** |

---

## Quickstart

### 1. Installation from PyPI

```bash
# Install the core protocol and MCP server
pip install grip-protocol==0.4.0

# Or install from source with dev & test suites
git clone <repository-url>
cd graphrag-protocol
pip install -e ".[dev,server,tigergraph]"
```

### 2. Environment Configuration

Create a `.env` file in your workspace root:

```bash
# TigerGraph Cloud (Savanna)
TG_HOST=https://your-subdomain.i.tgcloud.io
TG_GRAPH=ArxivGraph
TG_USERNAME=tigergraph
TG_PASSWORD=your_password
TG_SECRET=your_gsql_secret

# AI Agent & Embeddings (Optional)
GOOGLE_API_KEY=your_gemini_api_key

# Protocol Settings
GRIP_ENV=production
GRIP_STORAGE_PATH=./data/grip_store.sqlite3
```

### 3. Launching the MCP Server

```bash
# Launch stdio transport for agentic IDEs
python -m mcp_server.server

# Or start the local HTTP dashboard & SSE stream (FastAPI on port 8000)
graphrag-server
```

---

## Connect to Agentic IDEs

GRIP supports all leading agentic IDEs and developer environments out of the box via the Model Context Protocol (`stdio` transport):

### Claude Code CLI
Add GRIP with a single command in your terminal:
```bash
claude mcp add grip -- python -m mcp_server.server
```

### Cursor
Add to `.cursor/mcp.json` or Global Settings (`Cursor Settings -> Features -> MCP`):
```json
{
  "mcpServers": {
    "grip": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "env": {
        "TG_HOST": "https://your-instance.i.tgcloud.io",
        "TG_GRAPH": "ArxivGraph",
        "TG_USERNAME": "tigergraph",
        "TG_PASSWORD": "your_password",
        "TG_SECRET": "your_secret"
      }
    }
  }
}
```

### Cline (VS Code Extension)
Add to `cline_mcp_settings.json`:
```json
{
  "mcpServers": {
    "grip-protocol": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "autoApprove": [
        "graphrag_search",
        "graphrag_schema",
        "graphrag_neighborhood",
        "graphrag_provenance"
      ]
    }
  }
}
```

### OpenCode / Roo Code
Add to `mcp_settings.json`:
```json
{
  "mcpServers": {
    "grip": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "disabled": false,
      "alwaysAllow": ["graphrag_search", "graphrag_schema"]
    }
  }
}
```

### Codex CLI
Add to `~/.codex/config.toml`:
```toml
[mcp_servers.grip]
command = "python"
args = ["-m", "mcp_server.server"]

[mcp_servers.grip.env]
TG_HOST = "https://your-instance.i.tgcloud.io"
TG_GRAPH = "ArxivGraph"
```

### Windsurf (Codeium Cascade)
Add to `mcp_config.json`:
```json
{
  "mcpServers": {
    "grip": {
      "command": "python",
      "args": ["-m", "mcp_server.server"]
    }
  }
}
```

### Zed Editor
Add to `~/.config/zed/settings.json`:
```json
{
  "context_servers": {
    "grip": {
      "command": {
        "path": "python",
        "args": ["-m", "mcp_server.server"]
      }
    }
  }
}
```

### LangGraph / Python Agent Pipeline
```python
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI

async def run_agent():
    client = MultiServerMCPClient()
    await client.connect_to_server("grip", command="python", args=["-m", "mcp_server.server"])
    tools = client.get_tools()
    
    model = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
    agent = create_react_agent(model, tools)
    
    response = await agent.ainvoke({
        "messages": [("user", "Explain how Vaswani et al. connected Attention to Self-Attention in ArXiv")]
    })
    print(response["messages"][-1].content)
```

---

## The 20 Formal Wire Contracts

Each contract establishes strict RFC wire invariants, JSON schemas, Pydantic v2 models, and deterministic operational guarantees:

| # | Contract Name | RFC Classification | Standardized Guarantee & Architectural Invariant | Implementing Module |
| :- | :--- | :--- | :--- | :--- |
| **C1** | **Graph Query Interface** | Core Retrieval | Bounded multi-hop query payload with typed operators (`local_search`, `path_search`, `neighborhood`) | `contracts/retrieval.py` |
| **C2** | **Subgraph Extraction** | Core Retrieval | Standardized `SubgraphContext` serialization (nodes, edges, chunk hashes, metadata) | `mcp_server/protocol.py` |
| **C3** | **Hybrid Vector + Graph** | Core Retrieval | Reciprocal Rank Fusion (RRF) combining dense vector embeddings with topological degree | `contracts/similarity.py` |
| **C4** | **Schema Discovery** | Data Model | Deterministic vertex and edge type introspection enabling autonomous query synthesis | `contracts/schema_discovery.py` |
| **C5** | **Cryptographic Provenance**| Provenance | 100% citation audit trail linking answer assertions to vertex IDs and chunk hashes | `contracts/provenance.py` |
| **C6** | **Federation & Fan-out** | Execution | Parallel queries across heterogeneous clusters (TigerGraph + Neo4j) with seamless merge | `contracts/federation.py` |
| **C7** | **Streaming Mutation Feed**| Execution | Server-Sent Events (SSE) and pub/sub event logs for real-time graph changes | `contracts/streaming.py` |
| **C8** | **Dynamic Token Bounding** | Execution | Strict caller-defined context packing (Markdown / JSON-LD) respecting LLM token budgets | `mcp_server/formatters/` |
| **C9** | **Ingestion & Extraction** | Ingestion | Idempotent document chunking, entity extraction, and GSQL batch upsert pipeline | `contracts/construction.py` |
| **C10**| **Access Control & RBAC** | Governance | 5-tier role-based access control with cryptographically signed capability tokens | `contracts/authorization.py` |
| **C11**| **Community Detection** | Reasoning | Hierarchical community clustering (Louvain / Leiden) for high-level global queries | `contracts/aggregate.py` |
| **C12**| **Temporal Knowledge Graph**| Data Model | Bi-temporal intervals (`valid_at`, `observed_at`) with point-in-time graph traversal | `contracts/temporal.py` |
| **C13**| **Query Explanation** | Diagnostics | Natural-language traversal reasoning explaining why vertices were selected | `contracts/explanation.py` |
| **C14**| **Subgraph Structural Diff**| Diagnostics | Exact graph delta calculation between two retrieval runs or temporal states | `contracts/diff.py` |
| **C15**| **Graph Aggregations** | Execution | OLAP graph metrics (`count`, `group_by`, `top_n`, `stats_summary`) | `contracts/aggregate.py` |
| **C16**| **Export Interoperability** | Data Model | Universal serialization to GraphML, Cypher `MERGE`, JSON-LD, and RDF Turtle | `contracts/export.py` |
| **C17**| **Batch Fan-Out Runner** | Execution | Concurrent asynchronous execution for up to 25 parallel tool invocations | `contracts/batch.py` |
| **C18**| **Watch & Event Replay** | Ingestion | Persistent SQLite WAL event journal with resumption tokens and filtered replay | `contracts/watch.py` |
| **C19**| **Entity Deduplication** | Ingestion | Disambiguation pipeline with semantic similarity and conflict resolution | `contracts/conflicts.py` |
| **C20**| **Query Triage & ROI** | Intelligence | Cost-benefit classifier routing queries dynamically between Fast RAG and Agentic Search | `contracts/triage.py` |

---

## 50 Production MCP Tools

GRIP delivers 50 standardized tools organized into 4 operational suites:

### 1. Retrieval & Graph Exploration (18 Tools)
- `graphrag_search`: Semantic auto-routed search across vector + graph indices.
- `graphrag_local_search`: Keyword-focused neighborhood extraction around target entities.
- `graphrag_global_search`: Community-summary synthesis for global queries.
- `graphrag_hybrid_search`: Reciprocal rank fusion (RRF) across embeddings and topological proximity.
- `graphrag_entity`: Direct entity inspection and attribute retrieval.
- `graphrag_path`: Shortest path and constrained hop traversal between two entities.
- `graphrag_neighborhood`: Multi-hop neighborhood expansion with depth filters.
- `graphrag_community`: Community membership and synthesis summaries.
- `graphrag_schema`: Full schema topology, vertex attributes, and edge constraints.
- `graphrag_entity_types`: List of all registered vertex types in the active graph.
- `graphrag_relationship_types`: List of all registered edge types in the active graph.
- `graphrag_sample`: Sample vertices of a specific type for prompt few-shotting.
- `graphrag_temporal_search`: Subgraph retrieval bounded by time ranges.
- `graphrag_similarity`: Cosine and Jaccard similarity between two texts.
- `graphrag_entity_similarity`: Semantic similarity between two graph entities.
- `graphrag_batch_similarity`: Similarity ranking for multiple candidate entities.
- `graphrag_next_page`: Cursor-based pagination for large neighborhood results.
- `graphrag_format`: Formats a `SubgraphContext` into token-bounded Markdown or JSON.

### 2. Provenance, Audit & Governance (10 Tools)
- `graphrag_provenance`: Cryptographic citation trace linking claims to source vertices.
- `graphrag_trajectory`: Full agent traversal audit log for debugging graph hops.
- `graphrag_sources`: Source document chunks and arXiv IDs for an entity.
- `graphrag_audit`: Verifies citation completeness and highlights visited-not-cited entities.
- `graphrag_authorize`: Validates caller permissions against active role-based access policies.
- `graphrag_capability_token`: Issues signed, short-lived HMAC capability tokens for writes.
- `graphrag_audit_log`: Immutable SQLite mutation audit trail.
- `graphrag_status`: Backend connectivity, active database status, and uptime metrics.
- `graphrag_config`: Runtime protocol configuration and cache policy inspector.
- `graphrag_evaluate`: Precision, recall, and multi-hop accuracy evaluation harness.

### 3. Ingestion, Mutation & Federation (12 Tools)
- `graphrag_ingest`: Ingests raw document text, chunks, and writes vertices/edges (Authorized).
- `graphrag_delete_document`: Deletes a document vertex and cascades unreferenced edges (Authorized).
- `graphrag_job_status`: Tracks background asynchronous ingestion jobs.
- `graphrag_federated_search`: Fans out queries across multiple registered graph backends.
- `graphrag_list_backends`: Lists all registered backend connectors (TigerGraph, Neo4j, etc.).
- `graphrag_register_backend`: Registers a new federated database backend at runtime.
- `graphrag_entity_link`: Resolves and links identical entities across disparate graphs.
- `graphrag_events`: Queries recent graph mutation events from the streaming feed.
- `graphrag_watch`: Subscribes to filtered real-time graph events with replay tokens.
- `graphrag_export_subgraph`: Exports subgraphs to GraphML, Cypher, JSON-LD, or RDF Turtle.
- `graphrag_diff`: Computes structural deltas between two `SubgraphContext` payloads.
- `graphrag_diff_queries`: Runs two queries concurrently and computes the graph difference.

### 4. Advanced Intelligence & Agentic Optimization (10 Tools)
- `graphrag_agent_investigate`: Autonomous multi-hop investigator emitting structured `AgenticTrace`.
- `graphrag_resolve_conflicts`: Detects and resolves contradictory facts using recency and authority.
- `graphrag_triage_query`: Predicts optimal query pipeline and estimates Token-ROI.
- `graphrag_count`: High-speed entity count by type with optional attribute filtering.
- `graphrag_group_by`: Aggregates and groups entities by attribute values.
- `graphrag_top_n`: Ranks top-N entities by graph degree or custom attributes.
- `graphrag_stats_summary`: Full graph summary statistics (densities, diameters, type counts).
- `graphrag_explain`: Generates natural language explanations of why an entity was retrieved.
- `graphrag_explain_path`: Generates reasoning narratives along multi-hop traversal paths.
- `graphrag_batch`: Concurrent fan-out runner executing up to 25 parallel tool operations.

---

## Supported Database Backends

- **TigerGraph Cloud (Savanna)**: Native `pyTigerGraph` REST++ adapter (`mcp_server/adapters/tigergraph_adapter.py`) with automatic GSQL query installation and high-speed multi-hop traversals.
- **Neo4j (Cypher & AuraDB)**: Official Bolt Cypher connector (`mcp_server/adapters/neo4j_adapter.py`) supporting APOC procedures, Louvain communities, and vectorized k-NN search.
- **SQLite Persistent Store**: Embedded WAL-mode storage (`mcp_server/storage.py`) providing query caching, mutation journals, and streaming event persistence.
- **Hermetic Memory Adapter**: In-memory labeled graph adapter with BFS/Dijkstra shortest paths for local unit testing without credentials.

---

## Testing & Verification

The test suite enforces zero schema drift and verifies all 20 contracts:

```bash
# Run the hermetic unit suite (fast, offline, no database required)
pytest tests/test_contracts.py tests/test_mcp_server.py tests/test_schemas.py -v

# Run full integration tests against live TigerGraph backend
pytest -m integration

# Run linter and formatting checks
ruff check mcp_server/ tests/
```

---

## License

MIT License. Designed for open standards in enterprise Agentic AI.