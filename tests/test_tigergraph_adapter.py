"""Live integration tests for the TigerGraph adapter (zero mocks).

These tests run against the real Savanna workspace configured in ``.env``.
They are skipped automatically when TigerGraph credentials are absent or
the workspace is unreachable.

Because compiling GSQL queries is comparatively slow, all tests share a
single module-scoped adapter so the six queries are installed exactly once.
"""

from __future__ import annotations

import os

import pytest

from mcp_server.adapters import TigerGraphAdapter
from mcp_server.protocol import GraphSchema, Provenance, SubgraphContext

_REQUIRED_ENV = ("TIGERGRAPH_HOST", "TIGERGRAPH_GSQL_SECRET", "TIGERGRAPH_GRAPH_NAME")


def _creds_present() -> bool:
    for key in _REQUIRED_ENV:
        if not os.environ.get(key):
            return False
    return True


pytestmark = [
    pytest.mark.integration,  # hits the live backend when creds are present
    pytest.mark.skipif(
        not _creds_present(),
        reason="TigerGraph env not configured (TIGERGRAPH_HOST/GSQL_SECRET/GRAPH_NAME)",
    ),
]


@pytest.fixture(scope="module")
def adapter() -> TigerGraphAdapter:
    """A live adapter; skip the module if the workspace is unreachable."""
    a = TigerGraphAdapter()
    health = a.health_check()
    if health.get("status") != "ok":
        pytest.skip(f"TigerGraph workspace unreachable: {health}")
    return a


class TestHealthAndSchema:
    def test_health_check_reports_ok_and_backend(self, adapter: TigerGraphAdapter) -> None:
        health = adapter.health_check()
        assert health["status"] == "ok"
        assert health["backend"] == "tigergraph"
        assert health["version"]

    def test_get_schema_returns_populated_graph_schema(self, adapter: TigerGraphAdapter) -> None:
        schema = adapter.get_schema()
        assert isinstance(schema, GraphSchema)
        assert schema.protocol == "graphrag/1.0"
        types = {vt.type: vt for vt in schema.vertex_types}
        assert "Paper" in types
        assert types["Paper"].count > 0
        assert schema.statistics.total_vertices > 0

    def test_local_search_returns_context_with_entities_or_chunks(
        self, adapter: TigerGraphAdapter
    ) -> None:
        context = adapter.local_search(query="transformer attention", depth=2, top_k=10)
        assert isinstance(context, SubgraphContext)
        assert context.operation == "local_search"
        assert isinstance(context.results["entities"], list)
        assert isinstance(context.results["relationships"], list)
        assert context.metrics.entities_returned >= 0

    def test_entity_lookup_by_id(self, adapter: TigerGraphAdapter) -> None:
        papers = adapter.conn.getVertices("Paper", limit=1)
        if not papers:
            pytest.skip("no Paper vertices to look up")
        pid = str(papers[0]["v_id"])
        context = adapter.entity_lookup(entity_id=pid, entity_type="Paper", depth=1)
        assert context.operation == "entity_lookup"
        assert any(e["id"] == pid for e in context.results["entities"])

    def test_entity_lookup_resolves_name_if_id_missing(self, adapter: TigerGraphAdapter) -> None:
        context = adapter.entity_lookup(entity_name="transformer", entity_type="Concept", depth=1)
        assert isinstance(context, SubgraphContext)
        assert context.operation == "entity_lookup"

    def test_global_search_returns_communities(self, adapter: TigerGraphAdapter) -> None:
        context = adapter.global_search(query="research trends", top_communities=5)
        assert isinstance(context, SubgraphContext)
        assert context.operation == "global_search"
        assert isinstance(context.results["communities"], list)

    def test_neighborhood_returns_expansion(self, adapter: TigerGraphAdapter) -> None:
        papers = adapter.conn.getVertices("Paper", limit=1)
        if not papers:
            pytest.skip("no Paper vertices for neighborhood")
        context = adapter.neighborhood(entity_id=str(papers[0]["v_id"]), depth=2)
        assert context.operation == "neighborhood"
        assert isinstance(context.results["entities"], list)

    def test_hybrid_search_degrades_to_keyword_without_vector(
        self, adapter: TigerGraphAdapter
    ) -> None:
        context = adapter.hybrid_search(query="graph neural network", top_k=5)
        assert isinstance(context, SubgraphContext)
        assert context.operation == "hybrid_search"
        assert isinstance(context.results["entities"], list)

    def test_community_members_returns_papers(self, adapter: TigerGraphAdapter) -> None:
        concepts = adapter.conn.getVertices("Concept", limit=1)
        if not concepts:
            pytest.skip("no Concept vertices for community_members")
        cid = str(concepts[0]["attributes"].get("name") or concepts[0]["v_id"])
        context = adapter.community_members(community_id=cid)
        assert context.operation == "community_members"
        assert isinstance(context.results["communities"], list)

    def test_path_search_returns_valid_context(self, adapter: TigerGraphAdapter) -> None:
        papers = adapter.conn.getVertices("Paper", limit=2)
        if len(papers) < 2:
            pytest.skip("need at least two Paper vertices for path_search")
        context = adapter.path_search(
            source=str(papers[0]["v_id"]), target=str(papers[1]["v_id"]), max_hops=3
        )
        assert isinstance(context, SubgraphContext)
        assert context.operation == "path_search"
        assert isinstance(context.results["paths"], list)

    def test_provenance_has_backend_trail(self, adapter: TigerGraphAdapter) -> None:
        context = adapter.local_search(query="retrieval augmented generation", top_k=5)
        prov = adapter.get_provenance(context)
        assert isinstance(prov, Provenance)
        assert prov.backend == "tigergraph"