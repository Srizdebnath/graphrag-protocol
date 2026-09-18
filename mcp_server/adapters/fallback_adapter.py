"""Local demo adapter used when no external GraphRAG backend is configured."""

from __future__ import annotations

from typing import Any

from mcp_server.adapters.base import BaseGraphRAGAdapter
from mcp_server.protocol import (
    EntityType,
    GraphSchema,
    GraphStatistics,
    Provenance,
    RelationshipType,
    RetrievalMetrics,
    SubgraphContext,
    TraversalStep,
)


class DemoGraphRAGAdapter(BaseGraphRAGAdapter):
    """Minimal in-memory adapter for local, no-infra development."""

    def __init__(self, graph_id: str = "demo_graph") -> None:
        self.graph_id = graph_id
        self.entity_index = {
            "paper:bert": {
                "id": "paper:bert",
                "type": "Paper",
                "name": "BERT",
                "properties": {"year": 2018, "title": "BERT: Pre-training of Deep Bidirectional Transformers"},
                "relevance_score": 0.95,
            },
            "paper:attention": {
                "id": "paper:attention",
                "type": "Paper",
                "name": "Attention Is All You Need",
                "properties": {"year": 2017, "title": "Attention Is All You Need"},
                "relevance_score": 0.9,
            },
            "concept:transformer": {
                "id": "concept:transformer",
                "type": "Concept",
                "name": "Transformer",
                "properties": {"category": "architecture"},
                "relevance_score": 0.88,
            },
            "author:vaswani": {
                "id": "author:vaswani",
                "type": "Author",
                "name": "Ashish Vaswani",
                "properties": {"affiliation": "Google Research"},
                "relevance_score": 0.82,
            },
        }
        self.relationships = [
            {
                "id": "rel:1",
                "source": "paper:attention",
                "target": "concept:transformer",
                "type": "MENTIONS",
                "weight": 1.0,
                "properties": {"evidence": "Attention is all you need"},
                "evidence": [{"chunk_id": "chunk:1", "snippet": "The Transformer model relies entirely on attention."}],
            },
            {
                "id": "rel:2",
                "source": "paper:bert",
                "target": "concept:transformer",
                "type": "EXTENDS",
                "weight": 0.92,
                "properties": {"relation": "builds_upon"},
                "evidence": [{"chunk_id": "chunk:2", "snippet": "BERT is pretrained with deep bidirectional transformers."}],
            },
        ]
        self.chunks = [
            {
                "id": "chunk:1",
                "text": "The Transformer architecture uses self-attention and eliminates recurrence for sequence modeling.",
                "source_doc": "doc:1706.03762",
                "token_count": 24,
                "relevance_score": 0.9,
            },
            {
                "id": "chunk:2",
                "text": "BERT pre-trains deep bidirectional representations by jointly conditioning on both left and right context.",
                "source_doc": "doc:1810.04805",
                "token_count": 28,
                "relevance_score": 0.95,
            },
        ]

    def local_search(
        self,
        query: str,
        entity_hints: list[str] | None = None,
        depth: int = 2,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> SubgraphContext:
        entities = list(self.entity_index.values())[:top_k]
        return self._context(
            operation="local_search",
            query={"text": query, "entity_hints": entity_hints or [], "depth": depth, "top_k": top_k},
            entities=entities,
            relationships=self.relationships[:top_k],
            text_chunks=self.chunks[:top_k],
            hops=depth,
            latency_ms=25.0,
            provenance_source_docs=[c["source_doc"] for c in self.chunks[:top_k]],
            visited=["paper:attention", "concept:transformer"],
        )

    def global_search(
        self,
        query: str,
        community_level: int = 2,
        top_communities: int = 10,
    ) -> SubgraphContext:
        communities = [
            {
                "id": "community:transformer",
                "level": community_level,
                "summary": "Models centered on transformer-based sequence modeling and pretraining.",
                "member_count": 3,
                "centroid_entity": "concept:transformer",
            }
        ]
        return self._context(
            operation="global_search",
            query={"text": query, "community_level": community_level, "top_communities": top_communities},
            entities=list(self.entity_index.values())[:3],
            communities=communities,
            hops=community_level,
            latency_ms=32.0,
            provenance_source_docs=["doc:1706.03762", "doc:1810.04805"],
            visited=["concept:transformer"],
        )

    def hybrid_search(
        self,
        query: str,
        vector_weight: float = 0.5,
        graph_weight: float = 0.5,
        top_k: int = 10,
        depth: int = 2,
    ) -> SubgraphContext:
        return self.local_search(
            query=query,
            entity_hints=["transformer", "bert"],
            depth=depth,
            top_k=top_k,
            filters={"mode": "hybrid"},
        )

    def entity_lookup(
        self,
        entity_id: str | None = None,
        entity_name: str | None = None,
        entity_type: str | None = None,
        depth: int = 1,
    ) -> SubgraphContext:
        target_id = entity_id or entity_name
        matched = None
        for entity in self.entity_index.values():
            if entity_id and str(entity["id"]) == str(entity_id):
                matched = entity
                break
            if entity_name and entity["name"].lower() == str(entity_name).lower():
                matched = entity
                break
        if matched is None:
            matched = {
                "id": target_id or "unknown",
                "type": entity_type or "Unknown",
                "name": entity_name or target_id or "Unknown",
                "properties": {},
                "relevance_score": 0.5,
            }
        return self._context(
            operation="entity_lookup",
            query={"entity_id": entity_id, "entity_name": entity_name, "entity_type": entity_type, "depth": depth},
            entities=[matched],
            relationships=self.relationships[:2],
            hops=depth,
            latency_ms=18.0,
            provenance_source_docs=["doc:1706.03762"],
            visited=[matched["id"]],
        )

    def path_search(
        self,
        source: str,
        target: str,
        max_hops: int = 4,
    ) -> SubgraphContext:
        source_id = source if source.startswith(("paper:", "concept:")) else "paper:attention"
        target_id = target if target.startswith(("paper:", "concept:")) else "concept:transformer"
        _first = next(iter(self.entity_index.values()))
        _second = list(self.entity_index.values())[1]
        return self._context(
            operation="path_search",
            query={"source": source, "target": target, "max_hops": max_hops},
            entities=[self.entity_index.get(source_id, _first), self.entity_index.get(target_id, _second)],
            relationships=[self.relationships[1]],
            paths=[{
                "entities": [source_id, "concept:transformer", target_id],
                "relationships": ["rel:2"],
                "path_summary": f"{source} -> transformer -> {target}",
            }],
            hops=max_hops,
            latency_ms=20.0,
            provenance_source_docs=["doc:1810.04805"],
            visited=[source_id, target_id],
        )

    def neighborhood(
        self,
        entity_id: str,
        depth: int = 2,
        edge_types: list[str] | None = None,
    ) -> SubgraphContext:
        entity = self.entity_index.get(entity_id, next(iter(self.entity_index.values())))
        return self._context(
            operation="neighborhood",
            query={"entity_id": entity_id, "depth": depth, "edge_types": edge_types or []},
            entities=[entity, self.entity_index["concept:transformer"]],
            relationships=[self.relationships[1]],
            hops=depth,
            latency_ms=12.0,
            provenance_source_docs=["doc:1810.04805"],
            visited=[entity["id"], "concept:transformer"],
        )

    def community_members(
        self,
        community_id: str,
        include_summary: bool = True,
    ) -> SubgraphContext:
        return self._context(
            operation="community_members",
            query={"community_id": community_id, "include_summary": include_summary},
            entities=list(self.entity_index.values())[:3],
            communities=[{
                "id": community_id,
                "level": 1,
                "summary": "Semantic cluster around transformer models and pretrained language models.",
                "member_count": 3,
                "centroid_entity": "concept:transformer",
            }],
            hops=1,
            latency_ms=14.0,
            provenance_source_docs=["doc:1706.03762", "doc:1810.04805"],
            visited=["paper:bert", "concept:transformer"],
        )

    def get_schema(self, graph_id: str | None = None) -> GraphSchema:
        return GraphSchema(
            protocol="graphrag/1.0",
            graph_id=graph_id or self.graph_id,
            vertex_types=[
                EntityType(type="Paper", count=4, primary_key="id", attributes=[{"name": "id", "type": "STRING", "nullable": False}], sample={"id": "paper:bert", "name": "BERT"}),
                EntityType(type="Author", count=2, primary_key="id", attributes=[{"name": "id", "type": "STRING", "nullable": False}], sample={"id": "author:vaswani", "name": "Ashish Vaswani"}),
                EntityType(type="Concept", count=3, primary_key="id", attributes=[{"name": "id", "type": "STRING", "nullable": False}], sample={"id": "concept:transformer", "name": "Transformer"}),
            ],
            edge_types=[
                RelationshipType(type="MENTIONS", source="Paper", target="Concept", count=2, attributes=[]),
                RelationshipType(type="EXTENDS", source="Paper", target="Concept", count=1, attributes=[]),
            ],
            statistics=GraphStatistics(total_vertices=9, total_edges=3, avg_degree=0.67, connected_components=1),
        )

    def get_provenance(self, context: SubgraphContext) -> Provenance:
        source_docs = sorted({c.get("source_doc") for c in context.results.get("text_chunks", []) if c.get("source_doc")})
        traversal = [
            TraversalStep(step=1, entity="paper:attention", action="seed"),
            TraversalStep(step=2, entity="concept:transformer", action="expand", edge="rel:1"),
        ]
        return Provenance(
            source_documents=source_docs,
            traversal_log=traversal,
            visited_not_cited=[],
            total_entities_examined=len(context.results.get("entities", [])),
            total_chunks_returned=len(context.results.get("text_chunks", [])),
            backend="demo",
        )

    def health_check(self) -> dict:
        return {"status": "ok", "backend": "demo", "version": "0.1.0", "graph_id": self.graph_id}

    def _context(
        self,
        *,
        operation: str,
        query: dict[str, Any],
        entities: list[dict[str, Any]] | None = None,
        relationships: list[dict[str, Any]] | None = None,
        paths: list[dict[str, Any]] | None = None,
        communities: list[dict[str, Any]] | None = None,
        text_chunks: list[dict[str, Any]] | None = None,
        hops: int,
        latency_ms: float,
        provenance_source_docs: list[str] | None = None,
        visited: list[str] | None = None,
    ) -> SubgraphContext:
        metrics = RetrievalMetrics(
            input_tokens=max(1, len(str(query)) // 2),
            entities_returned=len(entities or []),
            relationships_returned=len(relationships or []),
            paths_found=len(paths or []),
            communities_matched=len(communities or []),
            graph_hops_traversed=hops,
            latency_ms=latency_ms,
        )
        provenance = Provenance(
            source_documents=provenance_source_docs or [],
            traversal_log=[
                TraversalStep(step=i + 1, entity=eid, action="seed" if i == 0 else "expand")
                for i, eid in enumerate(visited or [])
            ],
            visited_not_cited=[],
            total_entities_examined=len(entities or []),
            total_chunks_returned=len(text_chunks or []),
            backend="demo",
        )
        return SubgraphContext(
            operation=operation,
            query=query,
            results={
                "entities": entities or [],
                "relationships": relationships or [],
                "paths": paths or [],
                "communities": communities or [],
                "text_chunks": text_chunks or [],
            },
            provenance=provenance,
            metrics=metrics,
        )


__all__ = ["DemoGraphRAGAdapter"]
