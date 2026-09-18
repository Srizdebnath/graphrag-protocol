export interface RetrievalRequest {
  protocol: string;
  operation: string;
  query: string;
  entity_hints?: string[];
  depth: number;
  top_k: number;
  filters?: Record<string, unknown>;
  backend?: string;
}

export interface Entity {
  id: string;
  type: string;
  name: string;
  properties: Record<string, unknown>;
  relevance_score: number;
  source_chunks: string[];
}

export interface Relationship {
  id: string;
  source: string;
  target: string;
  type: string;
  weight: number;
  properties: Record<string, unknown>;
  evidence: Record<string, unknown>[];
}

export interface PathResult {
  id: string;
  source: string;
  target: string;
  hops: string[];
  score: number;
}

export interface CommunitySummary {
  id: string;
  level: number;
  members: string[];
  summary: string;
}

export interface TextChunk {
  id: string;
  text: string;
  source_doc: string;
  metadata: Record<string, unknown>;
}

export interface Provenance {
  query_id?: string;
  citations: Record<string, unknown>[];
  visited_entities: string[];
  cited_entities: string[];
  completeness_score: number;
  source_documents: string[];
}

export interface RetrievalMetrics {
  token_count: number;
  latency_ms: number;
  graph_hops_traversed: number;
  entities_retrieved: number;
  relationships_retrieved: number;
  communities_used: number;
}

export interface SubgraphContext {
  protocol: string;
  operation: string;
  query: {
    text: string;
    entity_hints?: string[];
    depth: number;
    top_k: number;
  };
  results: {
    entities: Entity[];
    relationships: Relationship[];
    paths: PathResult[];
    communities: CommunitySummary[];
    text_chunks: TextChunk[];
  };
  provenance: Provenance;
  metrics: RetrievalMetrics;
}

export interface EntityType {
  name: string;
  count: number;
  attributes: Record<string, string>;
}

export interface RelationshipType {
  name: string;
  source: string;
  target: string;
  count: number;
}

export interface GraphStatistics {
  total_vertices: number;
  total_edges: number;
  density: number;
  components: number;
}

export interface GraphSchema {
  protocol: string;
  graph_id: string;
  entity_types: EntityType[];
  relationship_types: RelationshipType[];
  statistics: GraphStatistics;
}

export interface PipelineResult {
  answer: string;
  tokens_total: number;
  /** How the answer was produced: "llm" or "extraction_only". */
  answer_source?: string;
  token_breakdown?: {
    input_tokens: number;
    output_tokens: number;
    context_tokens: number;
  };
  latency_ms: number;
  retrieval_method: string;
  context_tokens?: number;
  provenance?: Provenance;
  entities_used?: number;
  graph_hops?: number;
}

export interface Evaluation {
  judge_pass: boolean | null;
  judge_reason: string | null;
  bertscore_f1: number | null;
}

export interface BenchmarkResult {
  query_id: string;
  query: string;
  category: string;
  pipeline_1: PipelineResult;
  pipeline_2: PipelineResult;
  pipeline_3: PipelineResult;
  evaluation: Evaluation;
}
