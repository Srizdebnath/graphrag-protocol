# CLAUDE.md

Guidance for AI coding agents (and humans) working in this repository.
Last validated against the code on the `dev` branch — if this file and the
code disagree, **the code wins**; fix this file in the same commit.

## 0. Non-negotiables

1. **Zero-Mock Policy.** No placeholder/stub/fake/mock implementations of any
   protocol contract, retrieval operation, server endpoint, or benchmark
   number. Every feature must run against a real backend (TigerGraph, or the
   clearly-labeled in-memory demo adapter for local development) and produce
   real measured output. A feature that cannot run yet is listed as "not
   implemented" in this file — it is never faked.
2. **Never fabricate.** No invented answers, scores, latencies, token counts,
   or evaluation results. If the LLM is unavailable, responses are labeled
   `extraction_only`. If evaluation has not run, metrics are `null`. Every
   answer carries `answer_source` / provenance so an auditor can tell.
3. **Secrets never enter git.** `.env` is git-ignored; only `.env.example`
   (empty values) is tracked. If a secret ever lands in the history, rotate
   it immediately and see `SECURITY.md`.
4. **Degrade, never crash, never lie.** Backend unavailable → demo adapter +
   honest labeling. LLM error → labeled fallback. Query error → empty but
   valid `SubgraphContext` with `metrics.degradation_note` set.
5. **Contracts are the API.** All retrieval goes through
   `mcp_server/contracts/` (validation + normalization), all responses are
   `mcp_server/protocol.py` models. Do not bypass the contracts layer.

## 1. What this repository is

An implementation of the **GraphRAG Interoperability Protocol** (see
`SPEC.md`): a backend-agnostic contract layer so that any agent (MCP client,
LangGraph, CrewAI, custom) can query any GraphRAG backend through one
uniform interface with mandatory provenance.

- `mcp_server/protocol.py` — Pydantic models for all 10 contracts
  (`SubgraphContext`, `GraphSchema`, `Provenance`, `RetrievalMetrics`, …).
- `mcp_server/contracts/` — the contract layer (validation, defaults,
  auto-routing, normalization) over any adapter.
- `mcp_server/adapters/` — backend adapters implementing
  `BaseGraphRAGAdapter` (TigerGraph = real cloud backend; Demo = in-memory
  reference for tests/offline dev).
- `mcp_server/mcp_server.py` — **MCP server** (17 tools, stdio) — the
  protocol surface for AI agents.
- `mcp_server/server.py` — **HTTP demo server** (FastAPI) for the Next.js
  dashboard: 3-pipeline comparison + benchmark + schema/visualize.
- `mcp_server/formatters/` — Contract 8: token-bounded Markdown / structured
  serialization of a `SubgraphContext` for LLM prompts.
- `frontend/` — Next.js 15 dashboard (query lab, graph viz, benchmark).
- `hackathon/` — TigerGraph-specific: dataset generation, GSQL loaders,
  evaluation harness, static demo data.
- `schemas/` — JSON Schema files for the wire contracts.
- `tests/` — pytest suite (unit + `integration`-marked live-backend tests).

The hackathon context: a TigerGraph Cloud workspace (`GraphragProtocol`
graph, Paper/Author/Concept vertices, ~50k vertices / ~79k edges) loaded
from arXiv metadata, with embeddings via `gemini-embedding-001`.

## 2. Verified current state (what actually exists and runs)

| Component | Status | Notes |
|---|---|---|
| Protocol models (10 contracts) | **done** | `mcp_server/protocol.py`, Pydantic v2, exportable JSON Schema |
| Retrieval contract (7 ops + auto-routing) | **done** | `contracts/retrieval.py`; `search(mode='auto')` classifies global/entity/hybrid |
| Schema discovery contract | **done** | `contracts/schema_discovery.py` (TTL-cached) |
| Provenance contract | **done** | `contracts/provenance.py` (trace, trajectory, sources, audit) |
| Construction contract | **not implemented** | Document→KG ingestion does not exist; `IngestionConfig` is model-only |
| Federation contract | **not implemented** | `FederationConfig` is model-only; no fan-out/merge code |
| Streaming contract | **not implemented** | `StreamEvent` is model-only; no subscriptions |
| Authorization contract | **not implemented** | `AccessPolicy` is model-only; servers enforce nothing yet |
| Evaluation contract | **not implemented** | `EvaluationReport` is model-only; benchmark endpoints return measured pipeline metrics with `null` judge/bertscore fields |
| TigerGraph adapter | **done, real** | pyTigerGraph REST++ + compiled GSQL (`CREATE OR REPLACE` install-once), Gemini embeddings w/ keyword degradation |
| Demo adapter | **done** | In-memory reference adapter; clearly-labeled demo backend, never presented as TigerGraph |
| MCP server | **done, real** | `mcp_server/mcp_server.py`; 17 tools over stdio (mcp SDK ≥2) — see §4 |
| HTTP demo server | **done, real** | FastAPI: `/health /query /benchmark/results /schema /graph/visualize`; real retrieval + real Gemini answers, `answer_source` honesty field; CORS restricted to localhost:3000 |
| Formatters (Contract 8) | **done** | Markdown + structured, token-budgeted |
| Frontend | **done (demo)** | Next.js 15 + Recharts; types match the demo server contract (`judge_pass`/`bertscore_f1` nullable) |
| Hackathon scripts | **done** | KG check, loaders, evaluation harness (needs live workspace) |
| Tests | **50 unit passing** | 11 `integration`-marked tests skip without live creds; run all with `pytest -m integration` |

Not implemented anywhere in this repo (do not assume otherwise):
ingestion, federation, streaming, authorization enforcement, and a real
evaluation harness output. The corresponding protocol *models* exist so the
wire contract is stable for when they land.

## 3. Commands

```bash
# Environment (uv venv at .venv, Python 3.14)
source .venv/bin/activate
pip install -e '.[server,tigergraph,llm,dev]'   # or just `pip install -e .` for the core

# Tests (unit only, hermetic; integration tests self-skip without creds)
pytest                       # default: -m 'not integration' (configured in pyproject)
pytest -m integration        # live TigerGraph/LLM tests (requires .env creds)

# Lint / types
ruff check mcp_server/ hackathon/ tests/
mypy mcp_server/

# MCP server (what MCP clients launch; stdio transport)
.venv/bin/python -m mcp_server.mcp_server    # or `graphrag-mcp` once installed

# HTTP demo server (dashboard backend; binds 127.0.0.1 by default)
.venv/bin/python -m mcp_server.server        # or `graphrag-server`; DEMO_HOST/DEMO_PORT to override

# Frontend
cd frontend && npm install && npm run dev

# Hackathon data scripts (need live .env; no evaluate.py exists — evaluation
# currently runs via the demo server's /benchmark/results endpoint)
.venv/bin/python hackathon/scripts/check_kg.py
```

MCP client config (e.g. Claude Desktop / Claude Code):

```json
{
  "mcpServers": {
    "graphrag-protocol": {
      "command": "/home/ansh/graphrag-protocol/.venv/bin/python",
      "args": ["-m", "mcp_server.mcp_server"],
      "env": { "TIGERGRAPH_HOST": "your-host.tgcloud.io", "TIGERGRAPH_GSQL_SECRET": "<secret>" }
    }
  }
}
```
## 4. The MCP server (`mcp_server/mcp_server.py`)

Built on the **mcp SDK v2** (`MCPServer` from `mcp.server.mcpserver`; the old
`FastMCP` name no longer exists in v2 — don't reintroduce it). Stdio is the
only transport enabled. Selection logic: TigerGraph if configured *and*
healthy, else demo adapter; both go through the same contracts layer.

| Tool | Backed by | Purpose |
|---|---|---|
| `graphrag_search` | RetrievalContract.search | auto-routing NL query (local/global/hybrid/entity) |
| `graphrag_entity` | RetrievalContract.entity_lookup | entity by id/name + neighborhood |
| `graphrag_path` | RetrievalContract.path_search | paths between two entities |
| `graphrag_neighborhood` | RetrievalContract.neighborhood | depth-bounded expansion |
| `graphrag_community` | RetrievalContract.community_members | community members + summary |
| `graphrag_schema` | SchemaDiscoveryContract | full GraphSchema introspection |
| `graphrag_entity_types` | SchemaDiscoveryContract | vertex types + counts |
| `graphrag_relationship_types` | SchemaDiscoveryContract | edge types + endpoints |
| `graphrag_sample` | SchemaDiscoveryContract | sample entities per type |
| `graphrag_provenance` | ProvenanceContract.trace_citation | citation/audit chain |
| `graphrag_trajectory` | ProvenanceContract.get_traversal_trajectory | replay traversal steps |
| `graphrag_sources` | ProvenanceContract.get_source_documents | source docs per entity |
| `graphrag_audit` | ProvenanceContract.audit_provenance_completeness | cited-vs-examined score |
| `graphrag_format` | Contract 8 formatters | re-format an envelope to Markdown/structured text |
| `graphrag_status` | adapter.health_check + stats | backend identity + graph stats |
| `graphrag_config` | env | non-secret effective config |
| `graphrag_list_backends` | adapters | available + active backend |

Rules for tools: thin wrappers over contracts (no business logic), args via
type hints, return JSON strings, never print to stdout (stderr only — stdout
is the MCP framing channel).

## 5. Key implementation notes & gotchas

- **Env truth:** `LLM_MODEL=gemini-3.8-flash` (same model across all three
  pipelines — hackathon rule; verified to exist via `client.models.list()`).
  New 3.x models intermittently return **503 UNAVAILABLE under high demand** —
  the demo server retries 3× with backoff, then serves a labeled
  `extraction_only` answer. Embeddings: `EMBED_MODEL=gemini-embedding-001`,
  `EMBED_DIM=512`. Never assume a model name is invalid — list the catalog
  first.
- **TigerGraph:** queries are installed idempotently (`CREATE OR REPLACE`)
  on first use; first call in a fresh workspace pays GSQL compilation cost
  (tens of seconds). Edge types are `AUTHORED_BY`, `MENTIONS`, `CITES`.
- **Vector status caveat:** TigerGraph's `/vector/status` endpoint can report
  an attribute as NOT indexed even when `show index` confirms it is (seen on
  `PaperEmb`); treat it as advisory only, and trust actual query behavior.
- **Backend selection happens twice** (MCP server and demo server are
  separate processes with their own `_adapter()`); they can theoretically
  disagree if health flips between launches.
- **Secrets hygiene:** use `git ls-files | grep -iE '\.env|secret|key|pem'`
  before committing anything env-shaped. `.env.example` must stay value-empty.
- **TLS:** verification is on everywhere; `TIGERGRAPH_TLS_VERIFY=false` exists
  only as an explicit escape hatch in `check_kg.py` for broken cert chains.

## 6. Honest-behavior ledger (mock vs real vs degraded)

| Surface | Real when | Degraded behavior (labeled) |
|---|---|---|
| TigerGraph retrieval | creds present + workspace healthy | demo adapter (in-memory) |
| Hybrid search embeddings | `GOOGLE_API_KEY` set | keyword-only graph search |
| Demo-server answers | `GOOGLE_API_KEY` set | `answer_source: extraction_only` |
| Benchmark judge/bertscore | eval harness run | `null` fields (never invented) |
| Demo adapter | local dev/tests | always labeled `demo` |

Any new feature must land in this table.

## 7. Git conventions

- Branch: `dev` is the working branch (default); PRs `dev → main` for
  milestones. Never commit straight to `main`.
- Commit style: Conventional Commits —
  `feat(mcp): add provenance audit tool`, `fix(server): bind demo server to
  localhost`, `docs: align CLAUDE.md with code`, `chore(deps): ...`,
  `security: ...`. Subject ≤ 72 chars, imperative mood.
- One logical change per commit; run `ruff check` + `pytest` before pushing.
- Keep `CLAUDE.md`, `README.md`, and `SPEC.md` aligned with reality in the
  same PR that changes behavior.

## 8. When touching a module, read first

- `mcp_server/protocol.py` — before ANY change to models/wire shapes; keep
  the JSON Schemas in `schemas/` and `frontend/src/lib/types.ts` in sync.
- `mcp_server/adapters/tigergraph_queries.py` — before changing GSQL; the
  adapter maps its outputs by output key name, so renames break silently.
- `mcp_server/contracts/retrieval.py` — before adding an operation; also add
  the MCP tool + this file's §4 row in the same commit.
- `frontend/src/lib/api.ts` — endpoint contract with the demo server.
- `.env.example` — any new env var, documented and value-empty.

## 9. Definition of done (for any new feature)

1. Implemented against a real backend path (no `NotImplementedError`, no
   hard-coded outputs, no TODO placeholders).
2. Contract-layered (validation + normalization), provenance attached.
3. Unit tests added; live-backend coverage marked `integration` and
   self-skipping without creds.
4. `ruff check` clean; `pytest` green.
5. §2 table (and §4 if MCP) updated in the same commit.
