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

- `mcp_server/protocol.py` — Pydantic models for the core contracts
  (`RetrievalRequest`, `SubgraphContext`, `GraphSchema`, `Provenance`, …).
- `mcp_server/protocol_extensions.py` — Pydantic models for Contracts 4, 6, 7,
  9, 10 (`IngestionConfig`/`IngestionReport`/`Triple`, `FederationConfig`,
  `StreamEvent`, `EvaluationReport`, `AccessPolicy`).
- `mcp_server/contracts/` — the contract layer (validation, defaults,
  auto-routing, normalization) over any adapter: `retrieval`,
  `schema_discovery`, `provenance`, `construction`, `federation`, `streaming`,
  `evaluation`, `authorization`.
- `mcp_server/adapters/` — backend adapters implementing
  `BaseGraphRAGAdapter`: **TigerGraph = the only real backend**; the in-memory
  fallback is a clearly-labeled read-only demo adapter for tests/offline dev.
- `mcp_server/pipelines.py` — shared 3-pipeline runner (LLM-only / Basic RAG /
  GraphRAG) used by both the HTTP server and the evaluation harness, so their
  numbers agree by construction.
- `mcp_server/mcp_server.py` — **MCP server** (27 tools, stdio) — the
  protocol surface for AI agents.
- `mcp_server/server.py` — **HTTP demo server** (FastAPI) for the Next.js
  dashboard: 3-pipeline comparison + benchmark + schema/visualize + ingest +
  federated search + SSE stream feed.
- `mcp_server/formatters/` — Contract 8: token-bounded Markdown / structured
  serialization of a `SubgraphContext` for LLM prompts (`PromptFormatConfig`).
- `frontend/` — Next.js 14 dashboard (query lab, graph viz, benchmark, ingest & stream).
- `hackathon/` — TigerGraph-specific: dataset generation, GSQL loaders,
  evaluation harness, static demo data.
- `schemas/` — JSON Schema files for the wire contracts (10 schemas).
- `tests/` — pytest suite (unit + `integration`-marked live-backend tests).

The hackathon context: a TigerGraph Cloud workspace (`GraphragProtocol`
graph, Paper/Author/Concept vertices, ~50k vertices / ~79k edges) loaded
from arXiv metadata, with embeddings via `gemini-embedding-001`.

## 2. Verified current state (what actually exists and runs)

| Component | Status | Notes |
|---|---|---|
| Protocol models (10 contracts) | **done** | `protocol.py` + `protocol_extensions.py`, Pydantic v2, JSON Schemas in `schemas/` |
| Retrieval contract (7 ops + auto-routing) | **done** | `contracts/retrieval.py`; `search(mode='auto')` classifies global/entity/hybrid |
| Schema discovery contract | **done** | `contracts/schema_discovery.py` (TTL-cached, thread-safe) |
| Provenance contract | **done** | `contracts/provenance.py` (trace, trajectory, sources, audit) |
| Construction contract | **done, real writes** | `contracts/construction.py`: real `upsertVertex`/`upsertEdge`, counters measured before/after, `NEW_ONLY` is insert-only, events published at the mutation point |
| Federation contract | **done, real fan-out** | `contracts/federation.py`: concurrent fan-out, RRF/weighted merge, per-backend timings + errors echoed, graph_id sanitized |
| Streaming contract | **done, real bus** | `contracts/streaming.py` (thread-safe pub/sub with heartbeat) + SSE at `/stream/events` + MCP `graphrag_events` |
| Authorization contract | **done, enforced** | `contracts/authorization.py`; write endpoints fail closed (403) without `GRAPHRAG_ADMIN_TOKEN` (constant-time check) |
| Evaluation contract | **done** | `contracts/evaluation.py`: measured precision/recall/latency/grounding; judge + BERTScore `null` when unavailable |
| TigerGraph adapter | **done, real** | pyTigerGraph REST++ + compiled GSQL (`CREATE OR REPLACE` install-once), Gemini embeddings w/ keyword degradation |
| Demo adapter | **done** | In-memory, read-only reference adapter (`fallback_adapter.py`); used when `GRAPHRAG_BACKEND=demo` for tests/offline dev |
| MCP server | **done, real** | `mcp_server/mcp_server.py`; 27 tools over stdio (mcp SDK ≥2) — see §4 |
| HTTP demo server | **done, real** | FastAPI: `/health /query /benchmark/results /schema /graph/visualize /ingest /documents/{document_id} /federated/search /graph/entity-link /auth/operations /stream/events /evaluation/report` |
| Formatters (Contract 8) | **done** | Markdown + structured, token-budgeted (`PromptFormatConfig` model + JSON Schema) |
| Frontend | **done (demo)** | Next.js 14 + Recharts; types match the demo server contract (`judge_pass`/`bertscore_f1` nullable), includes Ingest & Stream UI |
| Hackathon scripts | **done** | KG check/loaders + `evaluate.py` (real eval harness, live workspace required) |
| Live smoke script | **done** | `scripts/smoke_construction.py` — ingest → read back → delete, exits non-zero on mismatch |
| Tests | **118 unit + 20 `integration`** | unit suite is hermetic; live tests self-skip without creds (`pytest -m integration`) |

Nothing in this repo is a mock in a runtime path: the only non-TigerGraph
backend is the labeled read-only demo adapter (tests/offline dev), and every
metric that cannot be measured is reported as `null` with a reason.

Known gaps: no community-recompute producer for `community_recomputed` events.

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

# Live smoke tests (need the live workspace in .env)
.venv/bin/python scripts/smoke_construction.py   # Contract 4: ingest -> read back -> delete
.venv/bin/python hackathon/scripts/check_kg.py   # vertex/edge counts + fanout sanity check
.venv/bin/python hackathon/scripts/evaluate.py --limit 10   # real eval harness -> hackathon/results/
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

27 tools:

| Tool | Backed by | Purpose |
|---|---|---|
| `graphrag_search` | RetrievalContract.search | auto-routing NL query (local/global/hybrid/entity) |
| `graphrag_local_search` | RetrievalContract.local_search | entity-anchored local search |
| `graphrag_global_search` | RetrievalContract.global_search | community-level global search |
| `graphrag_hybrid_search` | RetrievalContract.hybrid_search | weighted vector + graph search |
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
| `graphrag_ingest` | ConstructionContract.ingest | real ingestion (admin token required), publishes events |
| `graphrag_delete_document` | ConstructionContract.delete_document | real deletion (admin token required) |
| `graphrag_federated_search` | FederationContract.federated_search | multi-graph fan-out + merge |
| `graphrag_entity_link` | FederationContract.cross_graph_entity_link | cross-graph entity candidates |
| `graphrag_events` | STREAM_BUS | recent graph-mutation events (Contract 7) |
| `graphrag_evaluate` | EvaluationContract.evaluate_report | real retrieval/judge metrics over the query set |
| `graphrag_authorize` | AuthorizationContract | permission check + allowed operations for a token |

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
- **TigerGraph:** queries are installed idempotently (`CREATE OR REPLACE`), and
  the adapter probes `getInstalledQueries` first so a warm workspace installs
  nothing. Edge types are `AUTHORED_BY`, `MENTIONS`, `CITES`. `Paper` keys on
  `id`, `Author`/`Concept` on `name` (all `PRIMARY_ID_AS_ATTRIBUTE="true"`).
- **DATETIME writes:** a `published` value must be sent as the
  `YYYY-MM-DD HH:MM:SS` string; an epoch integer fails with
  `REST-30200 value cannot be converted to Datetime`. `ConstructionContract`
  formats it exactly like `hackathon/scripts/build_kg.py` does.
- **`getVerticesById` raises 601 for an unknown id** (it does not return an
  empty list), so every existence probe must catch — `construction._exists`
  and `scripts/smoke_construction.py` both do.
- **Construction counters:** `entities_created` counts only vertices this call
  created; a vertex matched by resolution lands in `entities_resolved` exactly
  once. `documents_written`/`documents_created` are the ids actually written —
  never inferred from `document_ids`. Dry runs measure the real graph but write
  nothing (`vertices_before == vertices_after`).
- **Events are published at the mutation point** by
  `ConstructionContract._emit` → `streaming.publish_ingestion_report`. Do not
  publish again in a server/tool wrapper (that double-published before); pass
  `publish_events=False` to build a silent contract (tests).
- **Write endpoints fail closed:** `GRAPHRAG_ADMIN_TOKEN` unset ⇒ ingests and
  deletes return 403 with the reason. Set it in `.env` for local writes.
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
| Construction / writes | TigerGraph + admin token | HTTP 409 (read-only adapter) or 403 (no token) |
| Federation fan-out | every listed graph reachable | unreachable backends named in `query.errors`, live ones still merge |
| Streaming events | a write happened | dry runs publish nothing (no fabricated events) |
| LLM judge / BERTScore | eval harness run with a key / `bert-score` installed | `null` + note (never invented) |
| Demo-server answers | `GOOGLE_API_KEY` set | `answer_source: extraction_only` |
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
