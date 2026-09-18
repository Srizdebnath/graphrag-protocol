# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**GraphRAG Protocol** — a backend-agnostic protocol for talking to any GraphRAG system through 10 standardized contracts (see `SPEC.md`). One MCP server + one HTTP server expose the same contracts over different transports; adapters translate the protocol to concrete backends (TigerGraph live, in-memory demo for degradation).

**Current state (P0 complete, verified against the live backend):**

- Real MCP stdio server (`mcp_server.mcp_server`) exposing **20 tools** backed by the contracts layer — verified end-to-end with a real MCP client handshake (list_tools → call_tool → live TigerGraph stats: ~49.6k vertices / ~79k edges).
- Real HTTP demo server (`mcp_server.server`) running the 3-pipeline hackathon comparison with real retrieval and real Gemini answers; `extraction_only` labeling when no LLM key is set; `null` eval fields until a real eval harness runs.
- TigerGraph adapter is real (pyTigerGraph + compiled GSQL, idempotent `CREATE OR REPLACE` installs, degradation fallbacks). `test_tigergraph_adapter.py` hits the live backend when creds exist (marked `integration`).
- No mocks in the retrieval path. The only intentionally synthetic component is `DemoGraphRAGAdapter` (in-memory fallback for zero-config runs) — it is clearly labeled and used only when TigerGraph is unconfigured/unhealthy.

## Commands

```bash
# Setup (Python 3.14 venv at .venv already present in dev)
pip install -e '.[dev,server,tigergraph,llm]'
cp .env.example .env   # then fill TIGERGRAPH_* and GOOGLE_API_KEY

# Tests (default run is hermetic: no live backend, no network)
pytest                                    # 50 tests, seconds
pytest -m integration                     # live TigerGraph adapter tests (needs creds)

# Lint
ruff check mcp_server/ hackathon/ tests/

# Run the MCP server (stdio — this is what MCP clients launch)
graphrag-mcp                              # or: python -m mcp_server.mcp_server

# Run the HTTP demo server (binds 127.0.0.1:8000 by default)
graphrag-server                           # or: python -m mcp_server.server

# Frontend (Next.js 15, http://localhost:3000)
cd frontend && npm run build && npm run dev
```

## Architecture

### Backend (`mcp_server/`)

```
mcp_server/
├── protocol.py                 # Pydantic contract models (Contracts 1,2,3,5)
│                               #   SubgraphContext, Provenance, RetrievalMetrics,
│                               #   GraphSchema (vertex_types/edge_types!), EntityType(.type!)
├── contracts/
│   ├── retrieval.py            # Contract 1: 7 operations + auto-routing search()
│   ├── schema_discovery.py     # Contract 3: cached introspection
│   ├── provenance.py           # Contract 5: trace_citation / trajectory / audit
│   └── construction.py         # Contract 4 (ingestion)
├── adapters/
│   ├── base.py                 # BaseGraphRAGAdapter ABC
│   ├── tigergraph_adapter.py   # LIVE backend (pyTigerGraph, GSQL in tigergraph_queries.py)
│   └── fallback_adapter.py     # DemoGraphRAGAdapter — in-memory degradation target
├── formatters/                 # Contract 8: MarkdownFormatter / StructuredFormatter
│                               #   (format_context(context, max_tokens) — token-bounded)
├── mcp_server.py               # MCP stdio server — 20 tools (graphrag-mcp)
└── server.py                   # FastAPI demo server (graphrag-server)
```

**Layering rule:** tools → contracts (`RetrievalContract`, ...) → adapters. Never call adapter methods from tools directly; the contracts own validation, defaults, and normalization into `SubgraphContext`.

### The two servers

| | MCP server (`mcp_server/mcp_server.py`) | HTTP demo (`mcp_server/server.py`) |
|---|---|---|
| Transport | stdio (JSON-RPC via `mcp` SDK v2) | FastAPI on `DEMO_HOST:DEMO_PORT` (default **127.0.0.1**:8000) |
| Consumers | Claude Desktop/Code, LangGraph, CrewAI | Next.js dashboard (`frontend/`) |
| Endpoints/tools | 20 `graphrag_*` tools | `/health` `/query` `/benchmark/results` `/schema` `/graph/visualize` |
| Answers | raw protocol envelopes (optional `formatted`) | 3-pipeline comparison (see below) |

**Adapter selection (both servers):** try `TigerGraphAdapter.health_check()`; on failure/absent creds log to **stderr** and use `DemoGraphRAGAdapter`. Never print to stdout inside MCP tool code — stdout is the MCP framing channel.

### The 20 MCP tools

Retrieval (8): `graphrag_search` (auto-routes local/global/hybrid/entity), `graphrag_local_search`, `graphrag_global_search`, `graphrag_hybrid_search`, `graphrag_entity`, `graphrag_path`, `graphrag_neighborhood`, `graphrag_community`.

Schema (4): `graphrag_schema`, `graphrag_entity_types`, `graphrag_relationship_types`, `graphrag_sample`.

Provenance (4): `graphrag_provenance`, `graphrag_trajectory`, `graphrag_sources`, `graphrag_audit`.

Formatting (1): `graphrag_format` — reformat a returned `SubgraphContext` envelope to token-bounded Markdown/structured text (`format_text`: none|markdown|structured; `max_tokens`).

Admin (3): `graphrag_status`, `graphrag_config` (non-secret config only), `graphrag_list_backends`. Tool functions return `json.dumps(...)` strings; every retrieval payload is the full protocol envelope `{protocol, operation, query, results, provenance, metrics[, formatted]}`.

### The 3-pipeline hackathon comparison (`/query`)

1. `pipeline_1_llm_only` — Gemini, no retrieval.
2. `pipeline_2_basic_rag` — `local_search(top_k=5, depth=1)` context → Gemini.
3. `pipeline_3_graphrag` — `search(mode=auto)` graph-aware context → Gemini.

Each response carries honest, measured fields: `tokens_total` (actual prompt chars/4), `latency_ms` (generation wall time), `retrieval_method`, `answer_source` (`llm` or `extraction_only`), `model` (null for extraction-only), plus provenance for pipelines 2/3. `/benchmark/results` runs real queries from `hackathon/data/queries/` through the same pipelines and reports `evaluation.judge_pass / bertscore_f1` as **null** until the real eval harness (P1) exists — the dashboard renders these as "N/A" / 0%.

## Environment variables

Copy `.env.example` → `.env`. Never commit real values.

| Var | Notes |
|---|---|
| `TIGERGRAPH_HOST/PORT/USERNAME/GSQL_SECRET/GRAPH_NAME/WORKSPACE_ID` | Savanna cloud workspace. **The GSQL secret was leaked in git history once — rotate it in the Savanna console** (DB admins → secrets). |
| `GOOGLE_API_KEY`, `LLM_MODEL` | Hackathon rule: the SAME model across all pipelines. Valid IDs: `gemini-2.5-flash`, `gemini-2.5-pro` (no `gemini-3.8-flash`). |
| `EMBED_MODEL`, `EMBED_DIM` | TigerGraph vector attributes: `gemini-embedding-001`, dim 512. |
| `DEMO_HOST`, `DEMO_PORT` | HTTP bind; defaults `127.0.0.1:8000`. Do not expose 0.0.0.0 without auth. |
| `TIGERGRAPH_TLS_VERIFY` | Only set `false` for known-broken cert chains (corporate proxies). |

CORS on the demo server is restricted to `localhost:3000` origins.

## Testing

- Default `pytest` is **hermetic**: the TigerGraph test module is marked `integration` (deselected by `addopts` in `pyproject.toml`) and self-skips without creds.
- MCP tests (`tests/test_mcp_server.py`) seed `mcp_server.mcp_server.STATE` with `DemoGraphRAGAdapter` and exercise tools through `MCPServer.call_tool` — no network.
- HTTP tests (`tests/test_server.py`) monkeypatch `mcp_server.server._ADAPTER`/`_RETRIEVAL`/`_LLM_AVAILABLE=False` and assert honest labeling (`extraction_only`, null evals).
- Live smoke (validated 2026-09-18): a minimal MCP client — `mcp.client.stdio.stdio_client` launching `python -m mcp_server.mcp_server` (see `.mcp.json` for the same launch config) — initializes, lists 20 tools, and `graphrag_status` returns live TigerGraph stats.

## Critical domain knowledge & gotchas

- **`mcp` SDK is v2**: `FastMCP` was renamed — import `MCPServer` from `mcp.server.mcpserver`; `mcp.types` field names are snake_case (`server_info`, not `serverInfo`). Don't pin `mcp<2`.
- **Python protocol field names differ from SPEC.md/TS**: `GraphSchema` uses `vertex_types`/`edge_types` (TS uses `entity_types`/`relationship_types`); `EntityType` key field is `.type` (not `.name`); `Provenance` has `source_documents/traversal_log/visited_not_cited/...` (no `completeness_score` field — completeness is computed by `ProvenanceContract.audit_provenance_completeness`); `GraphStatistics` reports `avg_degree`/`connected_components`. The Next.js `lib/types.ts` mirrors the SPEC/JSON-schema shape; the demo server bridges where needed.
- **Contract auto-routing**: `RetrievalContract.search()` classifies the query then dispatches; per-operation kwargs are filtered (e.g. `top_k` is dropped for `entity` mode). Fix added 2026-09-18 — keep the filtering when adding new operations.
- **TigerGraph queries** live in `mcp_server/adapters/tigergraph_queries.py` and install idempotently on first use. Vector readiness is polled (`PaperEmb` populated or not); without it `hybrid_search` degrades to keyword+graph.
- **Write diagnostics to stderr** in both servers. MCP stdout must stay framing-clean.
- **Demo adapter ids**: `paper:attention`, `paper:bert`, `concept:transformer` — used by tests and zero-config runs.
- **Hackathon scoring**: same LLM everywhere; latency/tokens are measured, never invented; the `evaluation` fields of `/benchmark/results` are intentional nulls until the real eval harness (P1) exists — do not fabricate judge/bertscore values.

## Security posture ( enforced )

- `.env` is git-ignored (verify: `git check-ignore .env` → exits 0). `.env.example` contains placeholders only.
- Demo server binds localhost; CORS pinned to dev origins; request bodies are size- and pattern-validated (Pydantic).
- TLS verification stays on by default everywhere (`TIGERGRAPH_TLS_VERIFY` escape hatch documented).
- No secrets in tool output: `graphrag_config` exposes non-secret config only.

## Roadmap

- **P0 (done)**: real MCP server (20 tools), honest HTTP server, secret scrub, packaging extras, hermetic test suite, contract auto-routing bugfix, localhost/CORS/TLS hardening, `verify=False` removed.
- **P1 (next)**: real evaluation harness (SPEC Contract 9): run all 50 hackathon queries × 3 pipelines through Gemini judge + BERTScore (`pip install -e '.[eval]'`), persist to `hackathon/results/`, feed `/benchmark/results` and the dashboard with real numbers instead of nulls.
- **P2 (later)**: additional adapters (Neo4j, LightRAG) implementing `BaseGraphRAGAdapter`; Contracts 6/7/10 (federation, streaming, authorization); composite/registry pattern for multi-backend fan-out.
