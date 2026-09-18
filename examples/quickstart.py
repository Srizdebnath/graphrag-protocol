"""Quickstart example — build a SubgraphContext in memory and print both formats."""

from __future__ import annotations

from mcp_server.formatters import MarkdownFormatter, StructuredFormatter
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


def build_sample_context() -> SubgraphContext:
    """Construct a realistic SubgraphContext entirely in-memory."""
    return SubgraphContext(
        operation="local_search",
        query={
            "text": "Which papers cite the Transformer architecture and use it for NLP?",
            "entity_hints": ["Attention Is All You Need"],
            "depth": 2,
            "top_k": 5,
        },
        results={
            "entities": [
                Entity(
                    id="paper:bert",
                    type="Paper",
                    name="BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
                    properties={"year": 2018, "citations": 70000, "venue": "NAACL"},
                    relevance_score=0.92,
                    source_chunks=["chunk:bert-1"],
                ).model_dump(),
                Entity(
                    id="concept:transformer",
                    type="Concept",
                    name="Transformer",
                    properties={"domain": "deep_learning", "first_paper": "1706.03762"},
                    relevance_score=0.99,
                    source_chunks=["chunk:aiayn-1"],
                ).model_dump(),
                Entity(
                    id="paper:gpt2",
                    type="Paper",
                    name="Language Models are Unsupervised Multitask Learners",
                    properties={"year": 2019, "citations": 12000},
                    relevance_score=0.78,
                    source_chunks=["chunk:gpt2-1"],
                ).model_dump(),
            ],
            "relationships": [
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
                            "snippet": "We propose BERT, based on the Transformer architecture.",
                        }
                    ],
                ).model_dump(),
                Relationship(
                    id="rel:gpt2-extends-transformer",
                    source="paper:gpt2",
                    target="concept:transformer",
                    type="EXTENDS",
                    weight=0.88,
                    properties={"relation": "builds_upon"},
                    evidence=[
                        {
                            "chunk_id": "chunk:gpt2-1",
                            "snippet": "GPT-2 uses a Transformer decoder.",
                        }
                    ],
                ).model_dump(),
            ],
            "paths": [
                PathResult(
                    entities=["paper:bert", "concept:transformer", "paper:gpt2"],
                    relationships=["rel:bert-cites-transformer", "rel:gpt2-extends-transformer"],
                    path_summary="BERT → Transformer ← GPT-2: both papers build on Transformer",
                ).model_dump(),
            ],
            "communities": [
                CommunitySummary(
                    id="community:attention-papers",
                    level=1,
                    summary="Cluster of papers on attention mechanisms including Transformer, BERT, GPT-2, and related work.",
                    member_count=42,
                    centroid_entity="concept:transformer",
                ).model_dump(),
            ],
            "text_chunks": [
                TextChunk(
                    id="chunk:aiayn-1",
                    text="We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely.",
                    source_doc="doc:1706.03762",
                    token_count=128,
                    relevance_score=0.98,
                ).model_dump(),
                TextChunk(
                    id="chunk:bert-1",
                    text="We introduce BERT, which is designed to pre-train deep bidirectional representations from unlabeled text by jointly conditioning on both left and right context in all layers.",
                    source_doc="doc:1810.04805",
                    token_count=140,
                    relevance_score=0.92,
                ).model_dump(),
            ],
        },
        provenance=Provenance(
            source_documents=["doc:1706.03762", "doc:1810.04805", "doc:1910.14659"],
            traversal_log=[
                TraversalStep(step=1, entity="concept:transformer", action="seed"),
                TraversalStep(
                    step=2,
                    entity="paper:bert",
                    action="expand",
                    edge="rel:bert-cites-transformer",
                ),
                TraversalStep(
                    step=3,
                    entity="paper:gpt2",
                    action="expand",
                    edge="rel:gpt2-extends-transformer",
                ),
            ],
            visited_not_cited=["paper:roberta"],
            total_entities_examined=5,
            total_chunks_examined=18,
            total_chunks_returned=2,
            backend="tigergraph",
            backend_version="4.1.0",
        ),
        metrics=RetrievalMetrics(
            input_tokens=64,
            entities_returned=3,
            relationships_returned=2,
            paths_found=1,
            communities_matched=1,
            graph_hops_traversed=2,
            latency_ms=22.5,
        ),
    )


def main() -> None:
    ctx = build_sample_context()

    md_fmt = MarkdownFormatter()
    st_fmt = StructuredFormatter()

    md_output = md_fmt.format_context(ctx, max_tokens=1024)
    st_output = st_fmt.format_context(ctx, max_tokens=1024)

    print("=" * 72)
    print("MARKDOWN FORMAT")
    print("=" * 72)
    print(md_output)
    print()
    print("=" * 72)
    print("STRUCTURED (JSON) FORMAT")
    print("=" * 72)
    print(st_output)
    print()

    # Quick sanity check
    import json
    parsed = json.loads(st_output)
    print(f"Markdown length : {len(md_output)} chars")
    print(f"JSON length     : {len(st_output)} chars")
    print(f"Entities in JSON: {len(parsed['entities'])}")


if __name__ == "__main__":
    main()
