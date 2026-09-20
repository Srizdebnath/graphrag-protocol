# GraphRAG Protocol — Specification

**Version:** 1.1 · **Status:** Draft · **License:** MIT

> **Universal GraphRAG Interoperability Protocol.** Standard contracts, a reference MCP server, and pluggable adapters so *any agent can query any GraphRAG backend uniformly*.

---

## 1. Overview

GraphRAG systems — TigerGraph, Neo4j, LightRAG, LlamaIndex, FalkorDB, Microsoft GraphRAG — deep down all do the same thing: answer questions by retrieving a *subgraph* (entities, relationships, paths, communities, and supporting text) around a query. Yet every engine reinvents that retrieval surface with its own APIs, serialization formats, provenance story, and metrics. Switching backends means rewriting your retrieval layer. Embedding a different engine means rewriting your agent tooling.

GraphRAG Protocol fills the missing middle layer between two existing standards:

<pre>
+---------------------+            +---------------------+
|     GQL / Cypher    |            |   MCP (Model Context |
| graph query standard|            |     Protocol)       |
|  (the bottom)       |            |   (the top)         |
+---------------------+            +---------------------+
          |                                    |
          |          +----------------+        |
          +--------->|  GraphRAG      |<-------+
                     |  Interoperability
                     |  Protocol (this)
                     |  + 15 contracts
                     |  + 42-tool MCP server
                     |  + adapters
                     +----------------+
</pre>

- **GQL** standardizes *how to query any graph* — but it returns raw graph primitives, not retrieval semantics (relevance scoring, provenance, community-level reasoning).
- **MCP** standardizes *how any agent connects to any tool* — but it says nothing about GraphRAG operation signatures, response shape, or citations.
- **GraphRAG Protocol** standardizes the *retrieval contract between the two*: a uniform request (`RetrievalRequest`), a uniform response (`SubgraphContext`), provenance, schema discovery, and evaluation.

### Why this matters

1. **Portability.** An agent written against this protocol can be repointed at any backend by swapping one adapter — no query rewriting, no reformatting of results.
2. **Token efficiency.** The standard context format forces adapters to return only the subgraph needed to answer, cutting prompt tokens versus vector-RAG baselines.
3. **Auditability.** The provenance contract (Contract 5) makes every answer traceable to source documents — including which entities were *visited but not cited*, enabling trajectory-completeness audits.
4. **Vendor-neutral evaluation.** Because all backends emit the same `RetrievalMetrics`, backends can be benchmarked on identical queries with identical scoring.
5. **Interpretability.** The explanation contract (Contract 13) tells agents *why* each entity was retrieved, turning a black box into an explainable retrieval system.
6. **Temporal reasoning.** The temporal contract (Contract 12) lets agents filter any subgraph by date range — essential for news, financial, and medical graphs.

---

## 2. The 15 Contracts

| # | Contract | Purpose | JSON Schema | Status |
|---|----------|---------|-------------|--------|
| 1 | **Retrieval** `RetrievalRequest` | Standard query format + 7 operations | `schemas/retrieval-request.json` | Detailed in §3 |
| 2 | **Subgraph Context** `SubgraphContext` | Standard response envelope | `schemas/subgraph-context.json` | Detailed in §4 |
| 3 | **Schema Discovery** `GraphSchema` | Backend-agnostic schema introspection | `schemas/graph-schema.json` | Detailed in §5 |
| 4 | **Construction** `IngestionConfig` | Document → knowledge-graph ingestion | `schemas/ingestion-config.json` | Summarized in §10.1 |
| 5 | **Provenance** `Provenance` | Citation & audit trail | `schemas/provenance.json` | Detailed in §6 |
| 6 | **Federation** `FederationConfig` | Multi-backend query fan-out + merge | `schemas/federation-config.json` | Summarized in §10.2 |
| 7 | **Streaming** `StreamEvent` | Real-time graph change notifications | `schemas/stream-event.json` | Summarized in §10.3 |
| 8 | **Prompt Formatting** `PromptFormatConfig` | Context → LLM-ready text | `schemas/prompt-format-config.json` | Detailed in §7 |
| 9 | **Evaluation** `EvaluationReport` | Standard retrieval/answer metrics | `schemas/evaluation-report.json` | Summarized in §10.4 |
| 10 | **Authorization** `AccessPolicy` | Per-operation permission model | `schemas/access-policy.json` | Summarized in §10.5 |
| 11 | **Semantic Similarity** | Cosine + Jaccard similarity between entities or text | — | `contracts/similarity.py` |
| 12 | **Temporal Query** | Date-range filtering over retrieved subgraphs | — | `contracts/temporal.py` |
| 13 | **Explanation** | Natural-language "why retrieved" narrative per entity | — | `contracts/explanation.py` |
| 14 | **Diff** | Structural delta between two SubgraphContexts | — | `contracts/diff.py` |
| 15 | **Aggregate** | OLAP-style count, group-by, top-N, stats summary | — | `contracts/aggregate.py` |



---

## 3. Contract 1 — Retrieval

**Operation signature (all backends):**

```python
def retrieve(request: RetrievalRequest) -> SubgraphContext
```

### 3.1 The request

```json
{
  "protocol": "graphrag/1.0",
  "operation": "local_search",
  "query": "What drugs interact with metformin?",
  "entity_hints": ["metformin"],
  "depth": 2,
  "top_k": 10,
  "filters": { "entity_type": ["drug", "condition"] },
  "backend": null
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `protocol` | `string` | yes | `"graphrag/1.0"` |
| `operation` | `enum` | yes | One of the 7 operations below |
| `query` | `string` | yes | Natural-language question / search text |
| `entity_hints` | `string[]` | no | Entity names/IDs to seed traversal |
| `depth` | `int [1,10]` | no | Max graph hops (default `2`) |
| `top_k` | `int [1,100]` | no | Max results per category (default `10`) |
| `filters` | `object` | no | Attribute filters applied during retrieval |
| `backend` | `string?` | no | Backend/graph ID for federated environments |

### 3.2 The seven operations

| Operation | Semantics | Primary params | Best for |
|---|---|---|---|
| `local_search` | Precise subgraph around matched entities | `entity_hints`, `depth`, `top_k` | Entity-centric questions |
| `global_search` | Community-summary synthesis | `community_level`, `top_communities` | Corpus-level "what are the trends" questions |
| `hybrid_search` | Vector + graph score fusion | `vector_weight`, `graph_weight`, `top_k`, `depth` | Semantic matching with structural grounding |
| `entity_lookup` | Fetch one entity + context | `entity_id`/`entity_name`/`entity_type`, `depth` | Resolving a specific node |
| `path_search` | Paths between two entities | `source`, `target`, `max_hops` | "How are X and Y related?" |
| `neighborhood` | Expand around an entity | `entity_id`, `depth`, `edge_types` | Exploration, reranking context |
| `community_members` | List a community's members | `community_id`, `include_summary` | Community drill-down |

### 3.3 Worked example — `local_search`

**Request:**

```json
{
  "protocol": "graphrag/1.0",
  "operation": "local_search",
  "query": "Which papers cite the Transformer architecture and use it for NLP?",
  "entity_hints": ["Attention Is All You Need"],
  "depth": 2,
  "top_k": 5
}
```

**Response:** (see Contract 2 §4 for the full shape)

```json
{
  "protocol": "graphrag/1.0",
  "operation": "local_search",
  "query": {
    "text": "Which papers cite the Transformer architecture and use it for NLP?",
    "entity_hints": ["Attention Is All You Need"],
    "depth": 2,
    "top_k": 5
  },
  "results": {
    "entities": [
      {
        "id": "paper:bert",
        "type": "Paper",
        "name": "BERT: Pre-training of Deep Bidirectional Transformers",
        "properties": { "year": 2018, "citations": 70000 },
        "relevance_score": 0.92,
        "source_chunks": ["chunk:bert-1"]
      },
      {
        "id": "concept:transformer",
        "type": "Concept",
        "name": "Transformer",
        "properties": {},
        "relevance_score": 0.99,
        "source_chunks": ["chunk:aiayn-1"]
      }
    ],
    "relationships": [
      {
        "id": "rel:bert-cites-transformer",
        "source": "paper:bert",
        "target": "concept:transformer",
        "type": "CITES",
        "weight": 1.0,
        "properties": {},
        "evidence": [{ "chunk_id": "chunk:bert-1", "snippet": "We propose BERT... based on the Transformer architecture." }]
      }
    ],
    "paths": [],
    "communities": [],
    "text_chunks": [
      {
        "id": "chunk:aiayn-1",
        "text": "We propose a new simple network architecture, the Transformer, based solely on attention mechanisms...",
        "source_doc": "doc:1706.03762",
        "token_count": 128,
        "relevance_score": 0.98
      }
    ]
  },
  "provenance": {
    "source_documents": ["doc:1706.03762", "doc:1810.04805"],
    "traversal_log": [
      { "step": 1, "entity": "concept:transformer", "action": "seed", "edge": null },
      { "step": 2, "entity": "paper:bert", "action": "expand", "edge": "rel:bert-cites-transformer" }
    ],
    "visited_not_cited": ["paper:gpt"],
    "total_entities_examined": 3,
    "total_chunks_examined": 12,
    "total_chunks_returned": 2,
    "backend": "tigergraph",
    "backend_version": "4.1.0"
  },
  "metrics": {
    "input_tokens": 42,
    "entities_returned": 2,
    "relationships_returned": 1,
    "paths_found": 0,
    "communities_matched": 0,
    "graph_hops_traversed": 2,
    "latency_ms": 18.4
  }
}
```

---

## 4. Contract 2 — Subgraph Context

Every retrieval operation returns a `SubgraphContext`:

| Field | Type | Required | Description |
|---|---|---|---|
| `protocol` | `string` | yes | `"graphrag/1.0"` |
| `operation` | `string` | yes | Echo of the operation that produced this |
| `query` | `object` | yes | Echo of the original request `{text, entity_hints, depth, top_k}` |
| `results` | `object` | yes | `{entities[], relationships[], paths[], communities[], text_chunks[]}` |
| `provenance` | `object` | yes | Contract 5 citation/audit trail (§6) |
| `metrics` | `object` | yes | `RetrievalMetrics` (§4.1) |

**Results sub-structures:**

- **`entities`** — `{id, type, name, properties, relevance_score, source_chunks}[]`
- **`relationships`** — `{id, source, target, type, weight, properties, evidence}[]`
- **`paths`** — `{entities[], relationships[], path_summary}[]`
- **`communities`** — `{id, level, summary, member_count, centroid_entity}[]`
- **`text_chunks`** — `{id, text, source_doc, token_count, relevance_score}[]`

### 4.1 RetrievalMetrics

| Field | Type | Description |
|---|---|---|
| `input_tokens` | `int` | Tokens consumed by the query/context |
| `entities_returned` | `int` | Entities returned |
| `relationships_returned` | `int` | Relationships returned |
| `paths_found` | `int` | Paths discovered |
| `communities_matched` | `int` | Communities matched |
| `graph_hops_traversed` | `int` | Total hops traversed (op-cost measure) |
| `latency_ms` | `float` | End-to-end retrieval latency |

These are the canonical comparison fields for the Evaluation contract (§10.4): any two backends answering the same query emit comparable `RetrievalMetrics`.

---

## 5. Contract 3 — Schema Discovery

Backends expose an introspection endpoint so agents can reason about the graph before querying.

```python
def get_schema(graph_id: str | None = None) -> GraphSchema
```

**Response shape:**

```json
{
  "protocol": "graphrag/1.0",
  "graph_id": "arxiv_kg",
  "vertex_types": [
    {
      "type": "Paper",
      "count": 1523,
      "primary_key": "id",
      "attributes": [
        { "name": "id", "type": "STRING", "nullable": false },
        { "name": "title", "type": "STRING", "nullable": false },
        { "name": "year", "type": "INT", "nullable": true }
      ],
      "sample": { "id": "paper:bert", "title": "BERT: Pre-training of Deep Bidirectional Transformers", "year": 2018 }
    }
  ],
  "edge_types": [
    {
      "type": "CITES",
      "source": "Paper",
      "target": "Paper",
      "count": 8943,
      "attributes": [{ "name": "year", "type": "INT", "nullable": true }]
    }
  ],
  "statistics": {
    "total_vertices": 5410,
    "total_edges": 14233,
    "avg_degree": 5.26,
    "connected_components": 37
  }
}
```

This is what lets an LLM plan a correct retrieval without reading backend-specific schema dialects.

---

## 6. Contract 5 — Provenance

Every `SubgraphContext` carries a `Provenance` object making the retrieval fully auditable.

```json
{
  "source_documents": ["doc:1706.03762", "doc:1810.04805"],
  "traversal_log": [
    { "step": 1, "entity": "concept:transformer", "action": "seed", "edge": null },
    { "step": 2, "entity": "paper:bert", "action": "expand", "edge": "rel:bert-cites-transformer" }
  ],
  "visited_not_cited": ["paper:gpt"],
  "extraction_provenance": [
    {
      "element_id": "rel:bert-cites-transformer",
      "source_doc": "doc:1810.04805",
      "chunk_id": "chunk:bert-1",
      "extracted_text": "based on the Transformer architecture",
      "confidence": 0.97
    }
  ],
  "total_entities_examined": 3,
  "total_chunks_examined": 12,
  "total_chunks_returned": 2,
  "backend": "tigergraph",
  "backend_version": "4.1.0"
}
```

### 6.1 Why `visited_not_cited`?

Traditional RAG audits only report *what was cited*. The protocol additionally reports **entities examined during traversal that were pruned from the final context**. This enables:

- **Trajectory completeness scoring** — did the pipeline look at the right region of the graph, or did it silently miss a nearby relevant entity?
- **Failure debugging** — a wrong answer with a high completeness score points at the LLM, not the retriever.
- **Novel evaluation signal** — a completeness metric impossible to compute from chunk-level RAG alone.

```python
def trajectory_completeness(p: Provenance) -> float:
    cited = {s.entity for s in p.traversal_log if s.entity not in p.visited_not_cited}
    return len(cited) / max(1, p.total_entities_examined)
```

---

## 7. Contract 8 — Prompt Formatting

Retrieved contexts are useless to an LLM unless serialized efficiently. Contract 8 defines the formatter interface that converts a `SubgraphContext` into bounded, LLM-ready text.

```python
class BaseFormatter(ABC):
    def format_context(context: SubgraphContext, max_tokens: int = 4096) -> str: ...
    def format_entity(entity: Entity) -> str: ...
    def format_relationship(relationship: Relationship) -> str: ...
```

Guarantees:

1. **Token-bounded** — output is truncated/priced against `max_tokens` by prioritizing top-scored entities, relationships, paths, communities, then chunks.
2. **Citation-preserving** — formatted output keeps references (e.g., `[chunk:bert-1]`) so the LLM answer can point back to provenance.
3. **Deterministic** — same context + same formatter = same output string (LLM-friendly).

Reference formatters: Markdown (default, inline citations), Structured JSON, XML, YAML.

---

## 8. Pydantic Model Reference (Python SDK)

The canonical Python types live in `mcp_server/protocol.py`:

`RetrievalMode`, `RetrievalRequest`, `Entity`, `Relationship`, `PathResult`, `CommunitySummary`, `TextChunk`, `TraversalStep`, `ExtractionRecord`, `Provenance`, `RetrievalMetrics`, `SubgraphContext`, `EntityType`, `RelationshipType`, `GraphStatistics`, `GraphSchema`, `RetrievalResult`.

Abstract interfaces in `mcp_server/contracts/base.py` (`BaseRetrievalContract`), `mcp_server/adapters/base.py` (`BaseGraphRAGAdapter`), and `mcp_server/formatters/base.py` (`BaseFormatter`).

---

## 9. Architecture

```
Agents (LangGraph, CrewAI, custom)  │  MCP server (42 tools)  │  Protocol contracts  │  Adapters  │  Backends
           │                        │        graphrag_search        │   retrieval        │  TigerGraph│
           │                        │        graphrag_entity         │   schema           │  Neo4j     │
           │      (MCP)             │        graphrag_path           │   provenance  ◄───►│  LightRAG  │
           └────────────────────────►        graphrag_similarity     │   construction     │  ChromaDB  │
                                             graphrag_temporal        │   similarity       │  ...       │
                                             graphrag_explain          │   explanation                  │
                                             graphrag_diff             │   diff                         │
                                             graphrag_count            │   aggregate                    │
                                             ... 42 tools ...         │                                │
```

---

## 10. Contracts 4, 6, 7, 9, 10 (Summaries)

### 10.1 Contract 4 — Construction (`IngestionConfig`)

Standard configuration + API for turning documents into a knowledge graph.

```python
ingest(documents, schema, extraction_config) -> IngestionReport
extract_entities(chunks, ontology) -> list[Triple]
resolve_entities(extracted, existing_graph, strategy) -> list[Triple]
update(document_id, content, strategy) -> IngestionReport
```

Removes the need to rewrite extraction pipelines when changing graph backends.

### 10.2 Contract 6 — Federation (`FederationConfig`)

Query several backends and merge results under a transparent policy.

```python
register_backend(name, adapter, weight)
federated_search(query, backends, merge_strategy, top_k) -> SubgraphContext
cross_graph_entity_link(entity_name, backends) -> list[EntityLink]
```

Merge strategies include reciprocal rank fusion and score fusion.

### 10.3 Contract 7 — Streaming (`StreamEvent`)

Notifies consumers of graph mutations.

```python
subscribe(event_types, filter_fn) -> AsyncIterator[StreamEvent]
publish_update(event)
```

Event types: `entity_created`, `edge_updated`, `community_recomputed`, … Enables live agents and incremental indexing.

### 10.4 Contract 9 — Evaluation (`EvaluationReport`)

Standardized, backend-comparable metrics.

```python
evaluate_retrieval(query, context, reference) -> RetrievalEval
evaluate_answer(query, answer, reference, context) -> AnswerEval
cross_backend_benchmark(queries, backends, references) -> BenchmarkReport
```

Includes token counts, latency, precision@k, BERTScore F1, and LLM-as-judge PASS/FAIL — all keyed off the uniform Contract 2/5 outputs.

### 10.5 Contract 10 — Authorization (`AccessPolicy`)

Per-operation permission model for exposure through MCP.

```python
check_permission(operation, graph_id, user_id, resource_filter) -> PermissionResult
get_allowed_operations(user_id, graph_id) -> list[str]
```

---

## 11. Versioning

The protocol version (`"graphrag/1.0"`) is carried on every request and response. Minor additions must not break existing consumers; major changes bump the version and update all schemas.