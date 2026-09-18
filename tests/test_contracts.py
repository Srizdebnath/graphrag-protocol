"""Tests for the CONTRACTS layer of GraphRAG Protocol.

Uses an in-memory :class:`FakeAdapter` implementing
:class:`BaseGraphRAGAdapter` to verify that each contract normalizes raw
adapter output into protocol models and applies its protocol-smart logic.
"""

from __future__ import annotations

import pytest

from mcp_server.adapters.base import BaseGraphRAGAdapter
from mcp_server.contracts.provenance import ProvenanceContract
from mcp_server.contracts.retrieval import RetrievalContract
from mcp_server.contracts.schema_discovery import SchemaDiscoveryContract
from mcp_server.protocol import (
    GraphSchema,
    Provenance,
    RetrievalMetrics,
    RetrievalResult,
    SubgraphContext,
    TraversalStep,
)


class FakeAdapter(BaseGraphRAGAdapter):
    """In-memory adapter returning realistic GraphRAG data."""

    def __init__(self) -> None:
        self._schema_call_count = 0

    # -- retrieval --------------------------------------------------------------

    def local_search(self, query, entity_hints=None, depth=2, top_k=10, filters=None):
        return SubgraphContext(
            operation="local_search",
            query={"text": query, "depth": depth, "top_k": top_k},
            results={
                "entities": [
                    {
                        "id": "paper:bert",
                        "type": "Paper",
                        "name": "BERT",
                        "relevance_score": 0.92,
                    }
                ],
                "relationships": [
                    {
                        "id": "rel:bert-cites",
                        "source": "paper:bert",
                        "target": "concept:transformer",
                        "type": "CITES",
                    }
                ],
                "paths": [],
                "communities": [],
                "text_chunks": [
                    {
                        "id": "chunk:bert-1",
                        "text": "BERT builds on Transformer.",
                        "source_doc": "doc:1810.04805",
                        "token_count": 20,
                        "relevance_score": 0.98,
                    }
                ],
            },
            provenance=Provenance(
                source_documents=["doc:1810.04805"],
                backend="fake",
            ),
            metrics=RetrievalMetrics(),
        )

    def global_search(self, query, community_level=2, top_communities=10):
        return SubgraphContext(
            operation="global_search",
            query={"text": query},
            results={
                "communities": [
                    {
                        "id": "comm:1",
                        "level": community_level,
                        "summary": "Overall themes across the corpus.",
                        "member_count": 42,
                    }
                ]
            },
            provenance=Provenance(
                source_documents=["doc:overview"],
                backend="fake",
            ),
            metrics=RetrievalMetrics(),
        )

    def hybrid_search(self, query, vector_weight=0.5, graph_weight=0.5, top_k=10, depth=2):
        return SubgraphContext(
            operation="hybrid_search",
            query={"text": query},
            results={
                "entities": [
                    {
                        "id": "concept:transformer",
                        "type": "Concept",
                        "name": "Transformer",
                        "relevance_score": 0.85,
                    }
                ],
                "relationships": [],
                "paths": [],
                "communities": [],
                "text_chunks": [],
            },
            provenance=Provenance(backend="fake"),
            metrics=RetrievalMetrics(),
        )

    def entity_lookup(self, entity_id=None, entity_name=None, entity_type=None, depth=1):
        return SubgraphContext(
            operation="entity_lookup",
            query={"entity_id": entity_id, "entity_name": entity_name},
            results={
                "entities": [
                    {
                        "id": entity_id or f"{entity_type}:{entity_name}",
                        "type": entity_type or "Concept",
                        "name": entity_name or entity_id,
                        "relevance_score": 1.0,
                    }
                ]
            },
            provenance=Provenance(backend="fake"),
            metrics=RetrievalMetrics(),
        )

    def path_search(self, source, target, max_hops=4):
        return SubgraphContext(
            operation="path_search",
            query={"source": source, "target": target},
            results={
                "paths": [
                    {
                        "entities": [source, "mid", target],
                        "relationships": ["r1", "r2"],
                        "path_summary": f"{source} -> {target}",
                    }
                ]
            },
            provenance=Provenance(backend="fake"),
            metrics=RetrievalMetrics(),
        )

    def neighborhood(self, entity_id, depth=2, edge_types=None):
        return SubgraphContext(
            operation="neighborhood",
            query={"entity_id": entity_id, "depth": depth},
            results={"entities": []},
            provenance=Provenance(backend="fake"),
            metrics=RetrievalMetrics(),
        )

    def community_members(self, community_id, include_summary=True):
        return SubgraphContext(
            operation="community_members",
            query={"community_id": community_id},
            results={"communities": []},
            provenance=Provenance(backend="fake"),
            metrics=RetrievalMetrics(),
        )

    # -- schema / provenance / health ------------------------------------------

    def get_schema(self, graph_id=None):
        self._schema_call_count += 1
        return {
            "protocol": "graphrag/1.0",
            "graph_id": graph_id or "fake_graph",
            "vertex_types": [
                {
                    "type": "Paper",
                    "count": 1523,
                    "primary_key": "id",
                    "attributes": [{"name": "id", "type": "STRING", "nullable": False}],
                    "sample": {"id": "paper:bert", "title": "BERT"},
                }
            ],
            "edge_types": [
                {
                    "type": "CITES",
                    "source": "Paper",
                    "target": "Paper",
                    "count": 8943,
                    "attributes": [],
                }
            ],
            "statistics": {
                "total_vertices": 5410,
                "total_edges": 14233,
                "avg_degree": 5.26,
                "connected_components": 37,
            },
        }

    def get_provenance(self, context):
        return Provenance(
            source_documents=["doc:1810.04805"],
            backend="fake",
        )

    def health_check(self):
        return {"status": "ok", "backend": "fake"}


@pytest.fixture
def adapter() -> FakeAdapter:
    """A fresh in-memory fake adapter per test."""
    return FakeAdapter()


@pytest.fixture
def retrieval(adapter: FakeAdapter) -> RetrievalContract:
    """A retrieval contract bound to a fake adapter."""
    return RetrievalContract(adapter)


@pytest.fixture
def schema_contract(adapter: FakeAdapter) -> SchemaDiscoveryContract:
    """A schema-discovery contract bound to a fake adapter."""
    return SchemaDiscoveryContract(adapter)


@pytest.fixture
def provenance_contract(adapter: FakeAdapter) -> ProvenanceContract:
    """A provenance contract bound to a fake adapter."""
    return ProvenanceContract(adapter)


# ---------------------------------------------------------------------------
# RetrievalContract
# ---------------------------------------------------------------------------


class TestRetrievalContract:
    def test_local_search_returns_context(self, retrieval: RetrievalContract) -> None:
        context = retrieval.local_search(
            query="What does BERT build on?",
            entity_hints=["bert"],
            depth=2,
            top_k=5,
        )
        assert context.operation == "local_search"
        assert context.results["entities"][0]["id"] == "paper:bert"
        assert context.results["relationships"][0]["type"] == "CITES"
        assert context.provenance.source_documents == ["doc:1810.04805"]
        assert context.metrics.entities_returned == 1

    def test_auto_route_global(self, retrieval: RetrievalContract) -> None:
        result = retrieval.search("What are the main themes across all papers?")
        assert isinstance(result, RetrievalResult)
        assert result.context.operation == "global_search"

    def test_auto_route_hybrid_default(self, retrieval: RetrievalContract) -> None:
        result = retrieval.search("Which technique improves retrieval quality in detail?")
        assert result.context.operation == "hybrid_search"

    def test_auto_route_entity(self, retrieval: RetrievalContract) -> None:
        result = retrieval.search("bert")
        assert result.context.operation == "entity_lookup"

    def test_rejects_empty_query(self, retrieval: RetrievalContract) -> None:
        with pytest.raises(ValueError):
            retrieval.search("   ")

    def test_unknown_mode_rejected(self, retrieval: RetrievalContract) -> None:
        with pytest.raises(ValueError):
            retrieval.search("hello", mode="bogus")

    def test_weights_normalized(self, retrieval: RetrievalContract) -> None:
        context = retrieval.hybrid_search("semantic question", vector_weight=1.0, graph_weight=1.0)
        assert context.operation == "hybrid_search"


# ---------------------------------------------------------------------------
# SchemaDiscoveryContract
# ---------------------------------------------------------------------------


class TestSchemaDiscoveryContract:
    def test_get_schema_returns_graph_schema_with_vertex_types(
        self, schema_contract: SchemaDiscoveryContract
    ) -> None:
        schema = schema_contract.get_schema()
        assert isinstance(schema, GraphSchema)
        assert schema.graph_id == "fake_graph"
        assert schema.vertex_types[0].type == "Paper"
        assert schema.vertex_types[0].count == 1523
        assert schema.statistics.total_vertices == 5410

    def test_get_entity_types(self, schema_contract: SchemaDiscoveryContract) -> None:
        types = schema_contract.get_entity_types()
        assert isinstance(types, list)
        assert types[0].type == "Paper"

    def test_get_relationship_types(self, schema_contract: SchemaDiscoveryContract) -> None:
        types = schema_contract.get_relationship_types()
        assert types[0].type == "CITES"
        assert types[0].source == "Paper"

    def test_get_statistics(self, schema_contract: SchemaDiscoveryContract) -> None:
        stats = schema_contract.get_statistics()
        assert stats.total_edges == 14233
        assert stats.avg_degree == pytest.approx(5.26)

    def test_schema_cached_within_ttl(self, adapter: FakeAdapter, schema_contract: SchemaDiscoveryContract) -> None:
        schema_contract.get_schema()
        schema_contract.get_schema()
        schema_contract.get_entity_types()
        schema_contract.get_statistics()
        assert adapter._schema_call_count == 1

    def test_get_sample_entities(self, adapter: FakeAdapter, schema_contract: SchemaDiscoveryContract) -> None:
        samples = schema_contract.get_sample_entities("Paper", count=1)
        assert samples == [{"id": "paper:bert", "title": "BERT"}]


# ---------------------------------------------------------------------------
# ProvenanceContract
# ---------------------------------------------------------------------------


class TestProvenanceContract:
    def test_audit_completeness_full(self, provenance_contract: ProvenanceContract) -> None:
        prov = Provenance(
            source_documents=["doc:a"],
            traversal_log=[
                TraversalStep(step=1, entity="e1", action="seed"),
                TraversalStep(step=2, entity="e2", action="expand"),
            ],
            visited_not_cited=[],
            total_entities_examined=2,
            backend="fake",
        )
        result = provenance_contract.audit_provenance_completeness(prov)
        assert result["completeness"] == pytest.approx(1.0)
        assert "Complete" in result["recommendation"]

    def test_audit_completeness_partial(self, provenance_contract: ProvenanceContract) -> None:
        prov = Provenance(
            source_documents=["doc:a", "doc:b", "doc:c"],
            traversal_log=[
                TraversalStep(step=1, entity="e1", action="seed"),
                TraversalStep(step=2, entity="e2", action="expand"),
                TraversalStep(step=3, entity="e3", action="expand"),
                TraversalStep(step=4, entity="e4", action="expand"),
            ],
            visited_not_cited=["e3", "e4"],
            total_entities_examined=4,
            backend="fake",
        )
        result = provenance_contract.audit_provenance_completeness(prov)
        assert result["completeness"] == pytest.approx(0.5)
        assert result["cited_entities"] == 2
        assert "Low completeness" in result["recommendation"]

    def test_get_source_documents(self, provenance_contract: ProvenanceContract) -> None:
        docs = provenance_contract.get_source_documents("paper:bert")
        assert docs == ["doc:1810.04805"]

    def test_trace_citation(self, provenance_contract: ProvenanceContract) -> None:
        prov = provenance_contract.trace_citation("paper:bert")
        assert prov.source_documents == ["doc:1810.04805"]

    def test_get_traversal_trajectory_from_context(self, provenance_contract: ProvenanceContract) -> None:
        context = SubgraphContext(
            operation="local_search",
            query={},
            provenance=Provenance(
                source_documents=["doc:a"],
                traversal_log=[TraversalStep(step=1, entity="e1", action="seed")],
                backend="fake",
            ),
            metrics=RetrievalMetrics(),
        )
        steps = provenance_contract.get_traversal_trajectory(context=context)
        assert len(steps) == 1
        assert steps[0].entity == "e1"

    def test_get_traversal_trajectory_requires_arg(self, provenance_contract: ProvenanceContract) -> None:
        with pytest.raises(ValueError):
            provenance_contract.get_traversal_trajectory()
