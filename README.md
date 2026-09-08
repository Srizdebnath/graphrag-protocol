# GraphRAG Protocol

**Universal GraphRAG Interoperability Protocol** — standard contracts + MCP server + adapters so *any agent can query any GraphRAG backend uniformly*.

Every GraphRAG engine (TigerGraph, Neo4j, LightRAG, LlamaIndex, FalkorDB, Microsoft GraphRAG) reinvents retrieval, subgraph serialization, provenance, and evaluation with incompatible interfaces. This protocol fills the missing middle layer between **GQL** (graph query standard at the bottom) and **MCP** (agent connectivity standard at the top): a uniform retrieval contract any backend can implement and any agent can call.

## Quick Start

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install the package (with dev dependencies)
pip install -e ".[dev]"

# 3. Copy the env template and fill in your backend credentials
cp .env.example .env
# E.g. TIGERGRAPH_HOST, TIGERGRAPH_GSQL_SECRET, GOOGLE_API_KEY

# 4. Inspect the protocol types
python -c "from mcp_server.protocol import SubgraphContext, RetrievalRequest; print('protocol OK')"

# 5. Start the MCP server (stdio transport)
graphrag-server
# or python -m mcp_server.server
```

Requires Python 3.10+.

## The 10 Contracts

| # | Contract | What it standardizes |
|---|----------|----------------------|
| 1 | **Retrieval** | Standard request envelope + 7 operations (`local_search`, `global_search`, `hybrid_search`, `entity_lookup`, `path_search`, `neighborhood`, `community_members`) |
| 2 | **Subgraph Context** | Uniform response: entities, relationships, paths, communities, text chunks |
| 3 | **Schema Discovery** | Backend-agnostic schema introspection for LLM planning |
| 4 | **Construction** | Document → knowledge-graph ingestion pipeline |
| 5 | **Provenance** | Citation & audit trail, incl. entities *visited but not cited* |
| 6 | **Federation** | Query multiple backends + result merging |
| 7 | **Streaming** | Real-time graph change events |
| 8 | **Prompt Formatting** | Context → LLM-ready, token-bounded text |
| 9 | **Evaluation** | Standard, backend-comparable metrics |
| 10 | **Authorization** | Per-operation permission model |

## Repo Layout

```
graphrag-protocol/
├── SPEC.md                      # Full protocol specification
├── schemas/                     # JSON Schema definitions (language-agnostic)
│   ├── retrieval-request.json   # Contract 1
│   ├── subgraph-context.json    # Contract 2
│   ├── graph-schema.json        # Contract 3
│   └── provenance.json          # Contract 5
├── mcp_server/                  # Reference implementation
│   ├── protocol.py              # Canonical Pydantic v2 models
│   ├── contracts/base.py        # Abstract retrieval contract (7 ops)
│   ├── adapters/base.py         # Abstract backend adapter
│   ├── formatters/base.py       # Abstract context formatter
│   └── server.py                # MCP server entrypoint (graphrag-server)
├── pyproject.toml
└── requirements.txt
```

## License

MIT