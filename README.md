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

# 5. Start the MCP server (stdio transport — what agents launch)
python -m mcp_server.mcp_server      # or the `graphrag-mcp` entrypoint

# 6. Start the HTTP dashboard server (FastAPI, binds 127.0.0.1:8000)
python -m mcp_server.server          # or the `graphrag-server` entrypoint
```

Requires Python 3.10+. Optional extras: `pip install -e ".[server,tigergraph,llm]"`.

## Backends

**TigerGraph (Savanna) is the only backend this project targets.** The adapter
(`mcp_server/adapters/tigergraph_adapter.py`) talks to a live workspace over
pyTigerGraph REST++ and installs its GSQL queries idempotently on first use.
`mcp_server/adapters/fallback_adapter.py` is a clearly-labeled in-memory adapter
for tests and offline development — it is read-only, never presented as
TigerGraph, and never used to fabricate an answer.

## Ingesting documents (Contract 4)

Writes are real TigerGraph upserts and every counter in the report is measured
from the backend (`getVertexCount` before/after, existence probes per entity):

```bash
# Self-test: ingest a document, read it back, delete it again
.venv/bin/python scripts/smoke_construction.py
```

Write operations (ingest / update / delete) require the admin token
(Contract 10, `GRAPHRAG_ADMIN_TOKEN`); without it they fail closed with 403.
Ingestion also publishes Contract 7 events at the mutation point, which the
dashboard consumes over SSE at `/stream/events`.

## Running the tests

```bash
pytest                    # hermetic unit suite (no creds, no network)
pytest -m integration     # live TigerGraph + Gemini tests (self-skip without creds)
ruff check mcp_server/ hackathon/ tests/
```


## The 10 Contracts

| # | Contract | What it standardizes | Implementation |
|---|----------|----------------------|----------------|
| 1 | **Retrieval** | Standard request envelope + 7 operations (`local_search`, `global_search`, `hybrid_search`, `entity_lookup`, `path_search`, `neighborhood`, `community_members`) | `contracts/retrieval.py` — done, real |
| 2 | **Subgraph Context** | Uniform response: entities, relationships, paths, communities, text chunks | `protocol.py` — done, real |
| 3 | **Schema Discovery** | Backend-agnostic schema introspection for LLM planning | `contracts/schema_discovery.py` — done, real |
| 4 | **Construction** | Document → knowledge-graph ingestion pipeline | `contracts/construction.py` — done, real writes |
| 5 | **Provenance** | Citation & audit trail, incl. entities *visited but not cited* | `contracts/provenance.py` — done, real |
| 6 | **Federation** | Query multiple graphs + transparent result merging | `contracts/federation.py` — done, real fan-out |
| 7 | **Streaming** | Real-time graph change events | `contracts/streaming.py` — done, real pub/sub + SSE |
| 8 | **Prompt Formatting** | Context → LLM-ready, token-bounded text | `formatters/` — done (`PromptFormatConfig` model + schema) |
| 9 | **Evaluation** | Standard, backend-comparable metrics | `contracts/evaluation.py` — done; judge/BERTScore `null` when unavailable |
| 10 | **Authorization** | Per-operation permission model | `contracts/authorization.py` — done, enforced on writes |

JSON Schemas for all 10 contracts live in `schemas/`; `tests/test_schemas.py`
fails if any schema drifts from its Pydantic model.

## Repo Layout

```
graphrag-protocol/
├── SPEC.md                      # Full protocol specification
├── schemas/                     # JSON Schema definitions (language-agnostic)
│   ├── retrieval-request.json   # Contract 1
│   ├── subgraph-context.json    # Contract 2
│   ├── graph-schema.json        # Contract 3
│   ├── ingestion-config.json    # Contract 4 (+ IngestionReport, Triple)
│   ├── provenance.json          # Contract 5
│   ├── federation-config.json   # Contract 6
│   ├── stream-event.json        # Contract 7
│   ├── prompt-format-config.json# Contract 8
│   ├── evaluation-report.json   # Contract 9
│   └── access-policy.json       # Contract 10
├── mcp_server/                  # Reference implementation
│   ├── protocol.py              # Canonical Pydantic v2 models (contracts 1-5, 8)
│   ├── protocol_extensions.py   # Models for contracts 4, 6, 7, 9, 10
│   ├── contracts/               # Contract layer: retrieval, schema, provenance,
│   │                            # construction, federation, streaming, evaluation, authorization
│   ├── adapters/                # TigerGraph (real) + labeled in-memory demo adapter
│   ├── formatters/              # Contract 8: Markdown / structured, token-bounded
│   ├── pipelines.py             # Shared 3-pipeline runner (server + eval harness)
│   ├── mcp_server.py            # MCP stdio server (27 tools)
│   └── server.py                # FastAPI dashboard server (+ SSE event feed)
├── frontend/                    # Next.js 14 dashboard (query lab, graph, benchmark, ingest & stream)
├── hackathon/                   # TigerGraph dataset, GSQL loaders, evaluation harness
├── scripts/                     # Live smoke tests (construction, connection)
├── tests/                       # Hermetic unit suite + `integration` live tests
└── pyproject.toml
```


## License

MIT