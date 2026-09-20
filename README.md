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

**TigerGraph (Savanna) is the primary backend.** The adapter
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


## The 15 Contracts

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
| 11 | **Semantic Similarity** | Cosine (vector) + Jaccard (lexical) similarity between entities or text | `contracts/similarity.py` — done |
| 12 | **Temporal Query** | Date-range filtering on any subgraph retrieval result | `contracts/temporal.py` — done |
| 13 | **Explanation** | Natural-language "why retrieved" narratives per entity, LLM-polished | `contracts/explanation.py` — done |
| 14 | **Diff** | Structural delta between two SubgraphContexts or two queries | `contracts/diff.py` — done |
| 15 | **Aggregate** | OLAP-style `count`, `group_by`, `top_n`, `stats_summary` over the graph | `contracts/aggregate.py` — done |

JSON Schemas for Contracts 1–10 live in `schemas/`; `tests/test_schemas.py`
fails if any schema drifts from its Pydantic model.

## MCP Tool Surface (42 tools)

### Original 27 tools
| Tool | Contract | Description |
|------|----------|-------------|
| `graphrag_search` | 1 | Auto-routed search (local/global/hybrid/entity) |
| `graphrag_local_search` | 1 | Keyword-graph subgraph search |
| `graphrag_global_search` | 1 | Community-summary synthesis |
| `graphrag_hybrid_search` | 1 | Vector + graph score fusion |
| `graphrag_entity` | 1 | Single entity lookup + context |
| `graphrag_path` | 1 | Shortest paths between entities |
| `graphrag_neighborhood` | 1 | Expand around an entity |
| `graphrag_community` | 1 | Community members + summary |
| `graphrag_schema` | 3 | Full graph schema |
| `graphrag_entity_types` | 3 | Vertex type list |
| `graphrag_relationship_types` | 3 | Edge type list |
| `graphrag_sample` | 3 | Sample entities of a type |
| `graphrag_provenance` | 5 | Citation trace for an entity |
| `graphrag_trajectory` | 5 | Traversal log |
| `graphrag_sources` | 5 | Source documents for an entity |
| `graphrag_audit` | 5 | Provenance completeness audit |
| `graphrag_format` | 8 | Format a SubgraphContext for LLM consumption |
| `graphrag_status` | — | Backend health + statistics |
| `graphrag_config` | — | Protocol configuration |
| `graphrag_list_backends` | 6 | List registered backends |
| `graphrag_ingest` | 4 | Document → knowledge graph (admin) |
| `graphrag_delete_document` | 4 | Delete a document vertex (admin) |
| `graphrag_federated_search` | 6 | Fan-out + merge across graphs |
| `graphrag_entity_link` | 6 | Cross-graph entity resolution |
| `graphrag_events` | 7 | Recent streaming events |
| `graphrag_evaluate` | 9 | Retrieval + answer quality evaluation |
| `graphrag_authorize` | 10 | Permission check |

### New 15 tools (v0.2.0)
| Tool | Contract | Description |
|------|----------|-------------|
| `graphrag_similarity` | 11 | Cosine/Jaccard similarity between two texts |
| `graphrag_entity_similarity` | 11 | Entity-to-entity similarity by id |
| `graphrag_batch_similarity` | 11 | Rank candidates by similarity to anchor |
| `graphrag_temporal_search` | 12 | Search + date-range filter |
| `graphrag_explain` | 13 | Why-retrieved narrative per entity |
| `graphrag_explain_path` | 13 | Path reasoning narrative |
| `graphrag_diff` | 14 | Structural delta between two contexts |
| `graphrag_diff_queries` | 14 | Run two queries and diff their results |
| `graphrag_count` | 15 | Count entities by type ± filters |
| `graphrag_group_by` | 15 | Group entities by attribute |
| `graphrag_top_n` | 15 | Top-N entities ranked by attribute |
| `graphrag_stats_summary` | 15 | Full graph statistics summary |
| `graphrag_job_status` | 4-ext | Async ingestion job status |
| `graphrag_register_backend` | 6-ext | Register a new federated backend |
| `graphrag_audit_log` | 10-ext | Immutable mutation audit log |

## Repo Layout

```
graphrag-protocol/
├── SPEC.md                      # Full protocol specification
├── MCP_SERVER_AUDIT.md          # Audit report + upgrade roadmap
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
│   ├── contracts/               # 15 contracts: retrieval, schema, provenance,
│   │   ├── retrieval.py         #   construction, federation, streaming, evaluation,
│   │   ├── schema_discovery.py  #   authorization, similarity, temporal, explanation,
│   │   ├── provenance.py        #   diff, aggregate
│   │   ├── construction.py
│   │   ├── federation.py
│   │   ├── streaming.py
│   │   ├── evaluation.py
│   │   ├── authorization.py
│   │   ├── similarity.py        # NEW: Contract 11
│   │   ├── temporal.py          # NEW: Contract 12
│   │   ├── explanation.py       # NEW: Contract 13
│   │   ├── diff.py              # NEW: Contract 14
│   │   └── aggregate.py         # NEW: Contract 15
│   ├── adapters/                # TigerGraph (real) + labeled in-memory demo adapter
│   ├── formatters/              # Contract 8: Markdown / structured, token-bounded
│   ├── pipelines.py             # Shared 3-pipeline runner (server + eval harness)
│   ├── mcp_server.py            # MCP stdio server (42 tools, v0.2.0)
│   └── server.py                # FastAPI dashboard server (+ SSE event feed)
├── frontend/                    # Next.js 14 dashboard (query lab, graph, benchmark, ingest & stream)
├── hackathon/                   # TigerGraph dataset, GSQL loaders, evaluation harness
├── scripts/                     # Live smoke tests (construction, connection)
├── tests/
│   ├── test_contracts.py        # Contracts 1, 3, 5 hermetic tests
│   ├── test_new_contracts.py    # Contracts 11-15 hermetic tests (NEW)
│   ├── test_mcp_server.py       # 42-tool MCP server hermetic tests
│   ├── test_formatters.py       # Contract 8 formatter tests
│   ├── test_schemas.py          # JSON schema drift detection
│   ├── test_server.py           # FastAPI server tests
│   └── test_tigergraph_adapter.py # TigerGraph adapter integration tests
└── pyproject.toml
```


## License

MIT