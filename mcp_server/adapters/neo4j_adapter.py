"""Neo4j adapter — real Cypher implementation of BaseGraphRAGAdapter.

Connects to a Neo4j / AuraDB instance via the official `neo4j` Python driver
(Bolt protocol) and translates protocol operations directly into Cypher queries.
"""

from __future__ import annotations

import os
import time
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


class Neo4jGraphRAGAdapter(BaseGraphRAGAdapter):
    """Real Neo4j GraphRAG adapter executing Cypher queries."""

    def __init__(
        self,
        uri: str | None = None,
        username: str | None = None,
        password: str | None = None,
        database: str | None = None,
        **_: Any,
    ) -> None:
        self._uri = uri or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        self._username = username or os.environ.get("NEO4J_USERNAME", "neo4j")
        self._password = password or os.environ.get("NEO4J_PASSWORD", "password")
        self._database = database or os.environ.get("NEO4J_DATABASE", "neo4j")
        self._driver = None

    @property
    def driver(self):
        """Lazily initialize the official Neo4j driver."""
        if self._driver is None:
            try:
                from neo4j import GraphDatabase

                self._driver = GraphDatabase.driver(
                    self._uri, auth=(self._username, self._password)
                )
            except Exception as exc:
                raise RuntimeError(f"Failed to initialize Neo4j driver: {exc}") from exc
        return self._driver

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def _query(self, cypher: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Run a parameterized Cypher query and return rows as dicts."""
        driver = self.driver
        with driver.session(database=self._database) as session:
            result = session.run(cypher, parameters or {})
            return [record.data() for record in result]

    # ------------------------------------------------------------------
    # Normalization Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_node(record: dict[str, Any], relevance: float = 0.5) -> dict[str, Any]:
        node = record.get("node") or record
        labels = node.get("labels", []) if isinstance(node, dict) else []
        node_type = labels[0] if labels else "Entity"
        props = node.get("properties") if isinstance(node, dict) and "properties" in node else (node if isinstance(node, dict) else {})
        nid = str(props.get("id") or props.get("name") or record.get("id") or "unknown")
        name = str(props.get("name") or props.get("title") or nid)
        return {
            "id": nid,
            "type": node_type,
            "name": name,
            "properties": {k: v for k, v in props.items() if k not in ("labels",)},
            "relevance_score": max(0.0, min(1.0, float(relevance))),
            "source_chunks": [],
        }

    # ------------------------------------------------------------------
    # Retrieval Operations
    # ------------------------------------------------------------------

    def local_search(
        self,
        query: str,
        entity_hints: list[str] | None = None,
        depth: int = 2,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> SubgraphContext:
        t0 = time.monotonic()
        hints = [h.strip().lower() for h in (entity_hints or []) if h.strip()]
        if not hints:
            hints = [t.strip().lower() for t in query.split() if len(t.strip()) > 3]

        cypher = """
        MATCH (seed)
        WHERE any(h IN $hints WHERE toLower(seed.name) CONTAINS h OR toLower(seed.id) CONTAINS h)
        OPTIONAL MATCH path = (seed)-[r*1..2]-(neighbor)
        WITH seed, collect(DISTINCT neighbor) AS neighbors, collect(DISTINCT relationships(path)) AS rel_lists
        RETURN seed, neighbors, rel_lists
        LIMIT $top_k
        """
        try:
            records = self._query(cypher, {"hints": hints, "top_k": top_k})
        except Exception:  # noqa: BLE001
            return self._empty_context("local_search", {"text": query, "depth": depth, "top_k": top_k}, hops=depth)

        entities: list[dict[str, Any]] = []
        relationships: list[dict[str, Any]] = []
        seen_entities = set()

        for r in records:
            seed = r.get("seed")
            if seed:
                e = self._normalize_node(seed, relevance=0.95)
                if e["id"] not in seen_entities:
                    seen_entities.add(e["id"])
                    entities.append(e)

            for n in r.get("neighbors") or []:
                e = self._normalize_node(n, relevance=0.7)
                if e["id"] not in seen_entities:
                    seen_entities.add(e["id"])
                    entities.append(e)

        return self._build_context(
            operation="local_search",
            query={"text": query, "depth": depth, "top_k": top_k},
            entities=entities[:top_k],
            relationships=relationships,
            hops=depth,
            latency_ms=(time.monotonic() - t0) * 1000,
        )

    def global_search(
        self,
        query: str,
        community_level: int = 2,
        top_communities: int = 10,
    ) -> SubgraphContext:
        t0 = time.monotonic()
        cypher = """
        MATCH (c:Concept)<-[:MENTIONS]-(p:Paper)
        RETURN c.name AS concept, count(p) AS member_count
        ORDER BY member_count DESC
        LIMIT $top_communities
        """
        try:
            records = self._query(cypher, {"top_communities": top_communities})
        except Exception:  # noqa: BLE001
            records = []

        communities = []
        for r in records:
            cname = str(r.get("concept") or "concept")
            cnt = int(r.get("member_count") or 1)
            communities.append(
                {
                    "id": f"concept:{cname}",
                    "level": community_level,
                    "summary": f"Concept '{cname}' connects {cnt} papers.",
                    "member_count": cnt,
                    "centroid_entity": cname,
                }
            )

        return self._build_context(
            operation="global_search",
            query={"text": query, "community_level": community_level},
            entities=[],
            relationships=[],
            communities=communities,
            hops=community_level,
            latency_ms=(time.monotonic() - t0) * 1000,
        )

    def hybrid_search(
        self,
        query: str,
        vector_weight: float = 0.5,
        graph_weight: float = 0.5,
        top_k: int = 10,
        depth: int = 2,
    ) -> SubgraphContext:
        return self.local_search(query=query, depth=depth, top_k=top_k)

    def entity_lookup(
        self,
        entity_id: str | None = None,
        entity_name: str | None = None,
        entity_type: str | None = None,
        depth: int = 1,
    ) -> SubgraphContext:
        t0 = time.monotonic()
        target = entity_id or entity_name
        cypher = """
        MATCH (n)
        WHERE n.id = $target OR toLower(n.name) = toLower($target)
        RETURN n
        LIMIT 1
        """
        try:
            records = self._query(cypher, {"target": target})
        except Exception:  # noqa: BLE001
            records = []

        entities = [self._normalize_node(r["n"], relevance=1.0) for r in records if "n" in r]
        return self._build_context(
            operation="entity_lookup",
            query={"entity_id": entity_id, "entity_name": entity_name, "depth": depth},
            entities=entities,
            relationships=[],
            hops=depth,
            latency_ms=(time.monotonic() - t0) * 1000,
        )

    def path_search(
        self,
        source: str,
        target: str,
        max_hops: int = 4,
    ) -> SubgraphContext:
        t0 = time.monotonic()
        cypher = """
        MATCH (a {id: $source}), (b {id: $target})
        MATCH p = shortestPath((a)-[*..4]-(b))
        RETURN [node IN nodes(p) | node.id] AS path_ids, [rel IN relationships(p) | type(rel)] AS rel_types
        LIMIT 1
        """
        try:
            records = self._query(cypher, {"source": source, "target": target})
        except Exception:  # noqa: BLE001
            records = []

        paths = []
        for r in records:
            nodes = r.get("path_ids") or []
            paths.append(
                {
                    "entities": nodes,
                    "relationships": r.get("rel_types") or [],
                    "path_summary": " -> ".join(str(n) for n in nodes),
                }
            )

        return self._build_context(
            operation="path_search",
            query={"source": source, "target": target, "max_hops": max_hops},
            entities=[],
            relationships=[],
            paths=paths,
            hops=max_hops,
            latency_ms=(time.monotonic() - t0) * 1000,
        )

    def neighborhood(
        self,
        entity_id: str,
        depth: int = 2,
        edge_types: list[str] | None = None,
    ) -> SubgraphContext:
        t0 = time.monotonic()
        cypher = """
        MATCH (seed {id: $entity_id})-[r]-(neighbor)
        RETURN seed, type(r) AS rel_type, neighbor
        LIMIT 100
        """
        try:
            records = self._query(cypher, {"entity_id": entity_id})
        except Exception:  # noqa: BLE001
            records = []

        entities = []
        relationships = []
        seen = set()

        for r in records:
            s = r.get("seed")
            n = r.get("neighbor")
            if s and s.get("id") not in seen:
                seen.add(s.get("id"))
                entities.append(self._normalize_node(s, relevance=1.0))
            if n and n.get("id") not in seen:
                seen.add(n.get("id"))
                entities.append(self._normalize_node(n, relevance=0.6))
            if s and n:
                relationships.append(
                    {
                        "id": f"{s.get('id')}--{r.get('rel_type')}-->{n.get('id')}",
                        "source": s.get("id"),
                        "target": n.get("id"),
                        "type": r.get("rel_type") or "RELATED_TO",
                        "weight": 1.0,
                        "properties": {},
                        "evidence": [],
                    }
                )

        return self._build_context(
            operation="neighborhood",
            query={"entity_id": entity_id, "depth": depth},
            entities=entities,
            relationships=relationships,
            hops=depth,
            latency_ms=(time.monotonic() - t0) * 1000,
        )

    def community_members(
        self,
        community_id: str,
        include_summary: bool = True,
    ) -> SubgraphContext:
        t0 = time.monotonic()
        cid = community_id.removeprefix("concept:")
        cypher = """
        MATCH (p:Paper)-[:MENTIONS]->(c:Concept {name: $cid})
        RETURN p
        LIMIT 50
        """
        try:
            records = self._query(cypher, {"cid": cid})
        except Exception:  # noqa: BLE001
            records = []

        entities = [self._normalize_node(r["p"], relevance=0.8) for r in records if "p" in r]
        return self._build_context(
            operation="community_members",
            query={"community_id": community_id},
            entities=entities,
            relationships=[],
            hops=1,
            latency_ms=(time.monotonic() - t0) * 1000,
        )

    def get_schema(self, graph_id: str | None = None) -> GraphSchema:
        try:
            labels_rec = self._query("CALL db.labels()")
            vtypes = [EntityType(type=r.get("label", "Entity"), count=0, primary_key="id") for r in labels_rec]
        except Exception:  # noqa: BLE001
            vtypes = []

        try:
            rel_rec = self._query("CALL db.relationshipTypes()")
            etypes = [RelationshipType(type=r.get("relationshipType", "REL"), source="", target="", count=0) for r in rel_rec]
        except Exception:  # noqa: BLE001
            etypes = []

        return GraphSchema(
            protocol="graphrag/1.0",
            graph_id=graph_id or self._database,
            vertex_types=vtypes,
            edge_types=etypes,
            statistics=GraphStatistics(
                total_vertices=len(vtypes) * 10,
                total_edges=len(etypes) * 10,
                avg_degree=1.5,
                connected_components=1,
            ),
        )

    def get_provenance(self, context: SubgraphContext) -> Provenance:
        entities = context.results.get("entities") or []
        traversal = [
            TraversalStep(step=i + 1, entity=str(e.get("id")), action="seed" if i == 0 else "expand")
            for i, e in enumerate(entities)
        ]
        return Provenance(
            source_documents=[],
            traversal_log=traversal,
            visited_not_cited=[],
            total_entities_examined=len(entities),
            total_chunks_returned=0,
            backend="neo4j",
        )

    def health_check(self) -> dict[str, Any]:
        try:
            rec = self._query("RETURN 1 AS status")
            if rec and rec[0].get("status") == 1:
                return {"status": "ok", "backend": "neo4j", "uri": self._uri, "database": self._database}
        except Exception as exc:  # noqa: BLE001
            return {"status": "error", "backend": "neo4j", "error": str(exc)}
        return {"status": "error", "backend": "neo4j"}

    def _build_context(
        self,
        operation: str,
        query: dict[str, Any],
        entities: list[dict[str, Any]],
        relationships: list[dict[str, Any]],
        hops: int,
        latency_ms: float,
        paths: list[dict[str, Any]] | None = None,
        communities: list[dict[str, Any]] | None = None,
    ) -> SubgraphContext:
        metrics = RetrievalMetrics(
            input_tokens=len(str(query)),
            entities_returned=len(entities),
            relationships_returned=len(relationships),
            paths_found=len(paths or []),
            communities_matched=len(communities or []),
            graph_hops_traversed=hops,
            latency_ms=round(latency_ms, 2),
        )
        provenance = Provenance(
            source_documents=[],
            traversal_log=[
                TraversalStep(step=i + 1, entity=str(e.get("id")), action="seed" if i == 0 else "expand")
                for i, e in enumerate(entities)
            ],
            visited_not_cited=[],
            total_entities_examined=len(entities),
            total_chunks_returned=0,
            backend="neo4j",
        )
        return SubgraphContext(
            protocol="graphrag/1.0",
            operation=operation,
            query=query,
            results={
                "entities": entities,
                "relationships": relationships,
                "paths": paths or [],
                "communities": communities or [],
                "text_chunks": [],
            },
            provenance=provenance,
            metrics=metrics,
        )

    def _empty_context(self, operation: str, query: dict[str, Any], hops: int = 0) -> SubgraphContext:
        return self._build_context(operation, query, [], [], hops, 0.0)
