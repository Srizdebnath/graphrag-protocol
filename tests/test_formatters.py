"""Tests for the GraphRAG Protocol formatters (Contract 8)."""

from __future__ import annotations

import json

from mcp_server.formatters.markdown_formatter import MarkdownFormatter, _estimate_tokens
from mcp_server.formatters.structured_formatter import StructuredFormatter
from mcp_server.protocol import (
    CommunitySummary,
    Entity,
    PathResult,
    Provenance,
    Relationship,
    RetrievalMetrics,
    SubgraphContext,
    TextChunk,
    TraversalStep,
)

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_context(
    *,
    entities: list[Entity] | None = None,
    relationships: list[Relationship] | None = None,
    paths: list[PathResult] | None = None,
    communities: list[CommunitySummary] | None = None,
    text_chunks: list[TextChunk] | None = None,
) -> SubgraphContext:
    """Build a realistic SubgraphContext for testing."""
    if entities is None:
        entities = [
            Entity(
                id="paper:bert",
                type="Paper",
                name="BERT: Pre-training of Deep Bidirectional Transformers",
                properties={"year": 2018, "citations": 70000},
                relevance_score=0.92,
                source_chunks=["chunk:bert-1"],
            ),
            Entity(
                id="concept:transformer",
                type="Concept",
                name="Transformer",
                properties={"domain": "deep_learning"},
                relevance_score=0.99,
                source_chunks=["chunk:aiayn-1"],
            ),
        ]

    if relationships is None:
        relationships = [
            Relationship(
                id="rel:bert-cites-transformer",
                source="paper:bert",
                target="concept:transformer",
                type="CITES",
                weight=1.0,
                properties={},
                evidence=[
                    {
                        "chunk_id": "chunk:bert-1",
                        "snippet": "based on the Transformer architecture",
                    }
                ],
            ),
            Relationship(
                id="rel:bert-extends",
                source="paper:bert",
                target="concept:transformer",
                type="EXTENDS",
                weight=0.85,
                properties={"relation": "builds_upon"},
                evidence=[],
            ),
        ]

    if paths is None:
        paths = [
            PathResult(
                entities=["paper:bert", "concept:transformer"],
                relationships=["rel:bert-cites-transformer"],
                path_summary="BERT directly cites Transformer architecture",
            )
        ]

    if communities is None:
        communities = [
            CommunitySummary(
                id="community:attention",
                level=1,
                summary="Papers around attention mechanisms and transformers",
                member_count=42,
                centroid_entity="concept:transformer",
            )
        ]

    if text_chunks is None:
        text_chunks = [
            TextChunk(
                id="chunk:aiayn-1",
                text="We propose a new simple network architecture, the Transformer, based solely on attention mechanisms.",
                source_doc="doc:1706.03762",
                token_count=128,
                relevance_score=0.98,
            ),
            TextChunk(
                id="chunk:bert-1",
                text="We propose BERT, based on the Transformer architecture, for pre-training deep bidirectional representations.",
                source_doc="doc:1810.04805",
                token_count=110,
                relevance_score=0.92,
            ),
        ]

    return SubgraphContext(
        operation="local_search",
        query={
            "text": "Which papers cite the Transformer architecture?",
            "entity_hints": ["Attention Is All You Need"],
            "depth": 2,
            "top_k": 5,
        },
        results={
            "entities": [e.model_dump() for e in entities],
            "relationships": [r.model_dump() for r in relationships],
            "paths": [p.model_dump() for p in paths],
            "communities": [c.model_dump() for c in communities],
            "text_chunks": [t.model_dump() for t in text_chunks],
        },
        provenance=Provenance(
            source_documents=["doc:1706.03762", "doc:1810.04805"],
            traversal_log=[
                TraversalStep(step=1, entity="concept:transformer", action="seed"),
                TraversalStep(
                    step=2,
                    entity="paper:bert",
                    action="expand",
                    edge="rel:bert-cites-transformer",
                ),
            ],
            visited_not_cited=["paper:gpt"],
            total_entities_examined=3,
            total_chunks_examined=12,
            total_chunks_returned=2,
            backend="tigergraph",
            backend_version="4.1.0",
        ),
        metrics=RetrievalMetrics(
            input_tokens=42,
            entities_returned=2,
            relationships_returned=2,
            paths_found=1,
            communities_matched=1,
            graph_hops_traversed=2,
            latency_ms=18.4,
        ),
    )


# ------------------------------------------------------------------
# Markdown formatter tests
# ------------------------------------------------------------------


class TestMarkdownFormatter:
    """Tests for MarkdownFormatter."""

    def test_format_entity(self) -> None:
        formatter = MarkdownFormatter()
        entity = Entity(
            id="paper:test",
            type="Paper",
            name="Test Paper",
            properties={"year": 2024},
            relevance_score=0.8,
            source_chunks=["chunk:1"],
        )
        out = formatter.format_entity(entity)
        assert "**Test Paper**" in out
        assert "(Paper)" in out
        assert "[Source: chunk:1]" in out

    def test_format_entity_uses_id_when_name_empty(self) -> None:
        formatter = MarkdownFormatter()
        entity = Entity(
            id="paper:noname",
            type="Paper",
            name="",
            relevance_score=0.5,
        )
        out = formatter.format_entity(entity)
        assert "paper:noname" in out

    def test_format_relationship(self) -> None:
        formatter = MarkdownFormatter()
        rel = Relationship(
            id="rel:1",
            source="A",
            target="B",
            type="CITES",
            weight=0.9,
            evidence=[{"chunk_id": "chunk:1", "snippet": "A cites B"}],
        )
        out = formatter.format_relationship(rel)
        assert "A --CITES--> B" in out
        assert "weight=0.90" in out
        assert '"A cites B"' in out
        assert "[Source: chunk:1]" in out

    def test_format_context_contains_required_sections(self) -> None:
        formatter = MarkdownFormatter()
        ctx = _make_context()
        out = formatter.format_context(ctx)
        assert "## Retrieved Context" in out
        assert "### Entities" in out
        assert "### Relationships" in out
        assert "### Paths" in out
        assert "### Communities" in out
        assert "### Source Chunks" in out

    def test_format_context_contains_entity_names(self) -> None:
        formatter = MarkdownFormatter()
        ctx = _make_context()
        out = formatter.format_context(ctx)
        assert "BERT: Pre-training of Deep Bidirectional Transformers" in out
        assert "Transformer" in out

    def test_format_context_contains_relationship_arrow(self) -> None:
        formatter = MarkdownFormatter()
        ctx = _make_context()
        out = formatter.format_context(ctx)
        assert "--CITES-->" in out
        assert "--EXTENDS-->" in out

    def test_format_context_footer_tokens_line(self) -> None:
        formatter = MarkdownFormatter()
        ctx = _make_context()
        out = formatter.format_context(ctx)
        assert "Retrieved via: tigergraph" in out
        assert "2 hops" in out
        assert "2 entities, 2 relationships" in out
        assert "42 tokens" in out

    def test_max_tokens_trims_entities(self) -> None:
        """Many entities with a small budget should be trimmed."""
        formatter = MarkdownFormatter()
        entities = [
            Entity(
                id=f"ent:{i}",
                type="Type",
                name=f"Entity_{i}",
                properties={"detail": "x " * 10},
                relevance_score=min(i / 30.0, 1.0),
                source_chunks=[f"chunk:{i}"],
            )
            for i in range(30)
        ]
        ctx = _make_context(entities=entities, relationships=[])
        out = formatter.format_context(ctx, max_tokens=80)
        assert "trimmed to fit token budget" in out
        # Not all 30 entities should appear (low-relevance ones trimmed)
        assert "Entity_0" not in out
        assert "Entity_5" not in out

    def test_max_tokens_trims_relationships(self) -> None:
        """Many relationships with a small budget should be trimmed."""
        formatter = MarkdownFormatter()
        rels = [
            Relationship(
                id=f"rel:{i}",
                source=f"src_{i}",
                target=f"tgt_{i}",
                type="LINK",
                weight=min(i / 30.0, 1.0),
                evidence=[
                    {"chunk_id": "c1", "snippet": f"source entity {i} links to target entity {i} with details"}
                ],
            )
            for i in range(30)
        ]
        ctx = _make_context(entities=[], relationships=rels)
        out = formatter.format_context(ctx, max_tokens=80)
        assert "trimmed to fit token budget" in out


# ------------------------------------------------------------------
# Structured formatter tests
# ------------------------------------------------------------------


class TestStructuredFormatter:
    """Tests for StructuredFormatter."""

    def test_format_entity(self) -> None:
        formatter = StructuredFormatter()
        entity = Entity(
            id="paper:test",
            type="Paper",
            name="Test Paper",
            relevance_score=0.8,
        )
        out = formatter.format_entity(entity)
        parsed = json.loads(out)
        assert parsed["id"] == "paper:test"
        assert parsed["type"] == "Paper"
        assert parsed["name"] == "Test Paper"
        assert parsed["rel"] == 0.8

    def test_format_relationship(self) -> None:
        formatter = StructuredFormatter()
        rel = Relationship(
            id="rel:1",
            source="A",
            target="B",
            type="CITES",
            weight=0.9,
            evidence=[{"chunk_id": "c1", "snippet": "test"}],
        )
        out = formatter.format_relationship(rel)
        parsed = json.loads(out)
        assert parsed["id"] == "rel:1"
        assert parsed["src"] == "A"
        assert parsed["tgt"] == "B"
        assert parsed["type"] == "CITES"

    def test_format_context_is_valid_json(self) -> None:
        formatter = StructuredFormatter()
        ctx = _make_context()
        out = formatter.format_context(ctx)
        parsed = json.loads(out)
        assert "entities" in parsed
        assert "relationships" in parsed
        assert "provenance" in parsed
        assert "metrics" in parsed

    def test_format_context_contains_entity_ids(self) -> None:
        formatter = StructuredFormatter()
        ctx = _make_context()
        out = formatter.format_context(ctx)
        parsed = json.loads(out)
        entity_ids = [json.loads(e)["id"] for e in parsed["entities"]]
        assert "paper:bert" in entity_ids
        assert "concept:transformer" in entity_ids

    def test_format_context_provenance(self) -> None:
        formatter = StructuredFormatter()
        ctx = _make_context()
        out = formatter.format_context(ctx)
        parsed = json.loads(out)
        prov = parsed["provenance"]
        assert prov["backend"] == "tigergraph"
        assert prov["total_entities_examined"] == 3
        assert "doc:1706.03762" in prov["source_documents"]

    def test_max_tokens_trims_entities(self) -> None:
        """Structured formatter should trim entities when budget is tight."""
        formatter = StructuredFormatter()
        entities = [
            Entity(
                id=f"ent:{i}",
                type="Type",
                name=f"Entity_{i}",
                properties={"detail": "x " * 10},
                relevance_score=min(i / 20.0, 1.0),
            )
            for i in range(20)
        ]
        ctx = _make_context(entities=entities)
        out = formatter.format_context(ctx, max_tokens=100)
        parsed = json.loads(out)
        assert len(parsed["entities"]) < 20

    def test_entities_sorted_by_relevance(self) -> None:
        formatter = StructuredFormatter()
        entities = [
            Entity(id="e:low", type="T", name="Low", relevance_score=0.1),
            Entity(id="e:high", type="T", name="High", relevance_score=0.99),
            Entity(id="e:mid", type="T", name="Mid", relevance_score=0.5),
        ]
        ctx = _make_context(entities=entities)
        out = formatter.format_context(ctx)
        parsed = json.loads(out)
        first = json.loads(parsed["entities"][0])
        assert first["id"] == "e:high"


# ------------------------------------------------------------------
# Token estimation
# ------------------------------------------------------------------


class TestTokenEstimation:
    def test_estimate_tokens(self) -> None:
        assert _estimate_tokens("hello world") == int(2 * 1.3)
        assert _estimate_tokens("") == 0
        assert _estimate_tokens("a b c d e") == int(5 * 1.3)
