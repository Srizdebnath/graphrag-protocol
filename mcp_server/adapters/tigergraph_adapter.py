"""TigerGraph adapter — real, zero-mock implementation of BaseGraphRAGAdapter.

Talks to a TigerGraph Cloud (Savanna) workspace via pyTigerGraph REST++ and
compiled GSQL queries.  All retrieval operations run real backend queries;
results are normalized into protocol models.  Queries are installed
idempotently (``CREATE OR REPLACE``) on first use.

Inputs come from environment variables unless overridden via constructor
kwargs (see :meth:`__init__`).

Degradation fallbacks (never crash, never fabricate):
- If an underlying vertex type is not yet populated (e.g. PaperEmb before
  embeddings load), the affected feature is skipped and a keyword-based
  fallback is used.
- If vector embedding generation fails, hybrid_search degrades to keyword
  graph search.
- If a query cannot be installed/run, the referenced operation returns an
  empty but valid :class:`SubgraphContext`.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any

from dotenv import load_dotenv

from mcp_server.adapters.base import BaseGraphRAGAdapter
from mcp_server.adapters.tigergraph_queries import (
    ALL_QUERIES,
    TG_CONCEPT_MEMBERS,
    TG_ENTITY_LOOKUP,
    TG_LOCAL_SEARCH,
    TG_NEIGHBORHOOD,
    TG_TOP_CONCEPTS,
    TG_VECTOR_SEARCH,
)
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

load_dotenv()

_EMBED_MODEL = os.environ.get("EMBED_MODEL", "gemini-embedding-001")
_EMBED_DIM = int(os.environ.get("EMBED_DIM", "512"))

# Edge type names actually present in the live schema (Paper -> Author,
# Paper -> Concept, Paper -> Paper).  Paths/neighborhoods traverse any edge
# in either direction, mirroring the GSQL `-[e]-` wildcard pattern.
_KNOWN_EDGE_TYPES = ("AUTHORED_BY", "MENTIONS", "CITES")


class TigerGraphAdapter(BaseGraphRAGAdapter):
    """TigerGraph-backed GraphRAG adapter.

    Args:
        host: TG Cloud host; falls back to ``TIGERGRAPH_HOST``.
        graphname: Graph name; falls back to ``TIGERGRAPH_GRAPH_NAME``.
        gsql_secret: GSQL secret; falls back to ``TIGERGRAPH_GSQL_SECRET``.
        username: Username; falls back to ``TIGERGRAPH_USERNAME``.
        port: REST++ port; falls back to ``TIGERGRAPH_PORT``.
        embedder: Optional callable ``str -> list[float]`` used by
            :meth:`hybrid_search`. If omitted, the adapter lazily attempts a
            Google GenAI embedder (``GOOGLE_API_KEY`` / ``EMBED_MODEL``);
            failures degrade to keyword-only hybrid search.
    """

    def __init__(
        self,
        host: str | None = None,
        graphname: str | None = None,
        gsql_secret: str | None = None,
        username: str | None = None,
        port: int | None = None,
        embedder: Callable[[str], list[float]] | None = None,
        **_: Any,
    ) -> None:
        self._host = host or os.environ["TIGERGRAPH_HOST"]
        self._graphname = graphname or os.environ["TIGERGRAPH_GRAPH_NAME"]
        self._gsql_secret = gsql_secret or os.environ["TIGERGRAPH_GSQL_SECRET"]
        self._username = username or os.environ.get("TIGERGRAPH_USERNAME", "tigergraph")
        self._port = port or int(os.environ.get("TIGERGRAPH_PORT", "443"))
        self._embedder: Callable[[str], list[float]] | None = embedder
        self._conn = None
        self._embed_client = None
        self._queries_installed = False
        self._embed_available: bool | None = None

    # ------------------------------------------------------------------
    # Connection + query plumbing
    # ------------------------------------------------------------------

    @property
    def conn(self):
        """Lazily create (once) and return the pyTigerGraph connection."""
        if self._conn is None:
            from pyTigerGraph import TigerGraphConnection

            self._conn = TigerGraphConnection(
                host=self._host,
                graphname=self._graphname,
                gsqlSecret=self._gsql_secret,
                username=self._username,
                restppPort=self._port,
                tgCloud=True,
            )
        return self._conn

    def _install_queries(self) -> None:
        """Install all GSQL queries idempotently (CREATE OR REPLACE)."""
        conn = self.conn
        for gsql in ALL_QUERIES.values():
            try:
                conn.gsql(f"USE GRAPH {self._graphname}\n" + gsql, graphname=self._graphname)
            except Exception:
                continue
        conn.gsql(f"USE GRAPH {self._graphname}\nINSTALL QUERY {', '.join(ALL_QUERIES)}", graphname=self._graphname)
        self._queries_installed = True

    def _run(
        self,
        query_name: str,
        params: dict[str, Any],
        fallback_params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Run an installed query, installing queries if necessary.

        Returns ``runInstalledQuery`` output (list of printed outputs).
        """
        conn = self.conn
        if not self._queries_installed:
            self._install_queries()
        try:
            return conn.runInstalledQuery(query_name, params)
        except Exception:
            # Query may have been dropped/reset server-side; reinstall once.
            if not self._queries_installed:
                raise
            self._queries_installed = False
            self._install_queries()
            try:
                return conn.runInstalledQuery(query_name, params)
            except Exception:
                if fallback_params:
                    return conn.runInstalledQuery(query_name, fallback_params)
                raise

    @staticmethod
    def _output(outputs: list[dict[str, Any]], key: str) -> Any:
        """Return the value printed under *key* from a runInstalledQuery list."""
        for item in outputs:
            if isinstance(item, dict) and key in item:
                return item[key]
        return None

    @staticmethod
    def _vertex_type_count(conn, vtype: str) -> int:
        try:
            return int(conn.getVertexCount(vtype))
        except Exception:
            return 0

    @staticmethod
    def _is_ready(conn, vtype: str) -> bool:
        """True if the vertex type exists and holds at least one vertex."""
        try:
            types = conn.getVertexTypes()
            return vtype in types and TigerGraphAdapter._vertex_type_count(conn, vtype) > 0
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Vertex normalization
    # ------------------------------------------------------------------

    @staticmethod
    def _public_attrs(attributes: dict[str, Any]) -> dict[str, Any]:
        """Strip internal (``@prefixed``) accumulator attributes."""
        return {k: v for k, v in (attributes or {}).items() if not str(k).startswith("@")}

    @classmethod
    def _entity(
        cls,
        vertex: dict[str, Any],
        relevance: float = 0.5,
        source_chunks: list[str] | None = None,
    ) -> dict[str, Any]:
        """Normalize a ``{v_id, v_type, attributes}`` vertex into an Entity dict.

        ``PaperEmb`` vertices are mapped onto their ``Paper`` counterpart so
        vector hits surface as real paper entities (they share the paper id).
        """
        vtype = vertex.get("v_type") or "Unknown"
        vid = vertex.get("v_id")
        attrs = cls._public_attrs(vertex.get("attributes") or {})
        if vtype == "PaperEmb":
            vtype = "Paper"
            if not vid:
                vid = attrs.get("id")
        if vtype == "Paper":
            name = attrs.get("title") or str(vid)
        elif vtype in ("Author", "Concept"):
            name = attrs.get("name") or str(vid)
        else:
            name = str(vid)
        return {
            "id": str(vid),
            "type": vtype,
            "name": name,
            "properties": attrs,
            "relevance_score": max(0.0, min(1.0, relevance)),
            "source_chunks": source_chunks or [],
        }

    @staticmethod
    def _relationship(edge: dict[str, Any]) -> dict[str, Any]:
        """Normalize an edge object into a Relationship dict."""
        etype = edge.get("e_type") or "EDGE"
        src = str(edge.get("from_id"))
        tgt = str(edge.get("to_id"))
        return {
            "id": f"{src}--{etype}-->{tgt}",
            "source": src,
            "target": tgt,
            "type": etype,
            "weight": 1.0,
            "properties": edge.get("attributes") or {},
            "evidence": [],
        }

    @classmethod
    def _entities_from_vertices(cls, vertices: list[dict[str, Any]], relevance: float = 0.5) -> list[dict[str, Any]]:
        return [cls._entity(v, relevance=relevance) for v in vertices]

    def _text_chunks_from_papers(self, papers: list[dict[str, Any]], relevance_fn: Callable[[str], float] | None = None) -> list[dict[str, Any]]:
        """Build TextChunk dicts from Paper vertices (their abstracts)."""
        chunks: list[dict[str, Any]] = []
        for paper in papers:
            attrs = paper.get("attributes") or {}
            abstract = attrs.get("abstract")
            if not abstract:
                continue
            pid = str(paper.get("v_id"))
            chunks.append(
                {
                    "id": f"paper:{pid}:abstract",
                    "text": abstract,
                    "source_doc": pid,
                    "token_count": int(attrs.get("abstract_token_count") or 0),
                    "relevance_score": relevance_fn(pid) if relevance_fn else 0.5,
                }
            )
        return chunks

    # ------------------------------------------------------------------
    # The seven retrieval operations
    # ------------------------------------------------------------------

    def local_search(
        self,
        query: str,
        entity_hints: list[str] | None = None,
        depth: int = 2,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> SubgraphContext:
        terms = self._terms(query, entity_hints)
        t0 = time.monotonic()
        try:
            outputs = self._run(
                TG_LOCAL_SEARCH,
                {"terms": terms, "query_text": query, "depth": depth, "top_k": top_k},
                fallback_params={"terms": [query], "query_text": query, "depth": depth, "top_k": top_k},
            )
        except Exception:
            return self._empty_context(
                "local_search", {"text": query, "depth": depth, "top_k": top_k}, hops=depth
            )

        entities = self._output(outputs, "entities") or []
        relationships = self._output(outputs, "relationships") or []
        relevance = self._output(outputs, "relevance") or {}
        hops = self._output(outputs, "hops") or 0

        seed_ids = {e.get("v_id") for e in (self._output(outputs, "seed") or [])}
        max_hits = max(relevance.values()) if relevance else 1

        papers = [
            e for e in entities
            if e.get("v_type") == "Paper" and str(e.get("v_id")) in seed_ids
        ]
        entity_records: list[dict[str, Any]] = []
        for e in entities:
            pid = str(e.get("v_id"))
            score = relevance.get(pid, 0) / max_hits if relevance else 0.5
            in_seed = str(e.get("v_id")) in seed_ids
            if e.get("v_type") == "Paper" and in_seed:
                score = 0.6 + 0.4 * score
            elif e.get("v_type") == "Paper":
                score = 0.5
            else:
                score = 0.4
            entity_records.append(self._entity(e, relevance=score))
        chunks = self._text_chunks_from_papers(papers, relevance_fn=lambda pid: relevance.get(pid, 1) / max_hits)
        rel_records = [self._relationship(e) for e in relationships]

        entity_records = sorted(
            entity_records, key=lambda e: e["relevance_score"], reverse=True
        )[:top_k]
        rel_records = rel_records[: max(top_k, 50)]
        chunks = sorted(chunks, key=lambda c: c["relevance_score"], reverse=True)[: top_k]
        src_docs = sorted({c["source_doc"] for c in chunks})

        return self._context(
            operation="local_search",
            query={"text": query, "entity_hints": entity_hints or [], "depth": depth, "top_k": top_k},
            entities=entity_records,
            relationships=rel_records,
            text_chunks=chunks,
            hops=int(hops),
            latency_ms=(time.monotonic() - t0) * 1000,
            source_documents=src_docs,
            visited=[],
        )

    def global_search(
        self,
        query: str,
        community_level: int = 2,
        top_communities: int = 10,
    ) -> SubgraphContext:
        t0 = time.monotonic()
        try:
            outputs = self._run(TG_TOP_CONCEPTS, {"top_k": top_communities})
        except Exception:
            return self._empty_context("global_search", {"text": query}, hops=community_level)

        counts = self._output(outputs, "concept_counts") or {}
        ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:top_communities]
        communities = []
        for cid, count in ranked:
            communities.append(
                {
                    "id": f"concept:{cid}",
                    "level": community_level,
                    "summary": f"Concept '{cid}' is mentioned by {count} papers.",
                    "member_count": int(count),
                    "centroid_entity": cid,
                }
            )
        return self._context(
            operation="global_search",
            query={"text": query, "community_level": community_level, "top_communities": top_communities},
            entities=[],
            relationships=[],
            communities=communities,
            hops=community_level,
            latency_ms=(time.monotonic() - t0) * 1000,
            source_documents=[],
            visited=[],
        )

    def hybrid_search(
        self,
        query: str,
        vector_weight: float = 0.5,
        graph_weight: float = 0.5,
        top_k: int = 10,
        depth: int = 2,
    ) -> SubgraphContext:
        """Combine keyword graph search with vector search (when ready).

        Vector search is only added if ``PaperEmb`` is populated and an
        embedding is available; otherwise this is keyword graph search.
        """
        t0 = time.monotonic()
        vector_entities: list[dict[str, Any]] = []
        vector_scores: list[tuple[str, float]] = []
        if self._embedding_enabled():
            try:
                emb = self._embed(query)
                if emb:
                    vector_entities, vector_scores = self._vector_search(emb, top_k)
            except Exception:
                vector_entities, vector_scores = [], []

        try:
            local = self.local_search(query=query, depth=depth, top_k=top_k, filters=None)
        except Exception:
            local = self._empty_context("hybrid_search", {"text": query}, hops=depth)

        merged, used_vector = self._merge(
            local.results["entities"],
            local.results["relationships"],
            vector_entities,
            vector_scores,
            vector_weight=vector_weight,
            graph_weight=graph_weight,
            top_k=top_k,
        )
        hops = int(local.metrics.graph_hops_traversed or depth)
        return self._context(
            operation="hybrid_search",
            query={"text": query, "vector_weight": vector_weight, "graph_weight": graph_weight, "top_k": top_k, "depth": depth},
            entities=merged["entities"],
            relationships=merged["relationships"],
            paths=[],
            communities=[],
            text_chunks=local.results["text_chunks"],
            hops=hops,
            latency_ms=(time.monotonic() - t0) * 1000,
            source_documents=local.provenance.source_documents,
            visited=[],
            note="vector" if used_vector else "keyword",
        )

    def _vector_search(self, embedding: list[float], top_k: int) -> tuple[list[dict[str, Any]], list[tuple[str, float]]]:
        """Return (enriched paper entities, [(paper_id, score), ...])."""
        conn = self.conn
        if not self._is_ready(conn, "PaperEmb"):
            return [], []
        outputs = self._run(TG_VECTOR_SEARCH, {"query_embedding": embedding, "top_k": top_k})
        matches = self._output(outputs, "matches") or []
        distances = self._output(outputs, "distances") or {}
        if not matches:
            return [], []

        # Map PaperEmb -> Paper by their shared id, enrich via REST++.
        paper_ids = [str(m.get("v_id")) for m in matches]
        records = [self._entity(m, relevance=1.0) for m in matches]
        try:
            raw = conn.getVerticesById("Paper", paper_ids, select="id,title,categories,published,abstract_token_count")
            for r in raw:
                attrs = r.get("attributes") or {}
                pid = str(r.get("v_id"))
                for rec in records:
                    if rec["id"] == pid:
                        rec["name"] = attrs.get("title") or rec["name"]
                        prop = {k: v for k, v in attrs.items()}
                        rec["properties"] = prop
                        break
        except Exception:
            pass

        scores: list[tuple[str, float]] = []
        for rid in paper_ids:
            d = float(distances.get(rid, 1.0))
            sim = max(0.0, min(1.0, 1.0 - d))
            scores.append((rid, sim))
        return records, scores

    def entity_lookup(
        self,
        entity_id: str | None = None,
        entity_name: str | None = None,
        entity_type: str | None = None,
        depth: int = 1,
    ) -> SubgraphContext:
        if entity_id is None and entity_name is None:
            return self._empty_context(
                "entity_lookup", {"entity_id": None, "entity_name": None}, hops=depth
            )
        if entity_id is None:
            resolved = self._resolve_entity(entity_name or "", entity_type)
            if resolved is None:
                return self._empty_context(
                    "entity_lookup",
                    {"entity_name": entity_name, "entity_type": entity_type, "depth": depth},
                    hops=depth,
                )
            entity_id, entity_type = resolved

        if not entity_type:
            entity_type = "Paper"
        t0 = time.monotonic()
        try:
            outputs = self._run(
                TG_ENTITY_LOOKUP,
                {"entity_id": entity_id, "entity_type": entity_type, "depth": depth, "top_k": 50},
            )
        except Exception:
            return self._empty_context(
                "entity_lookup",
                {"entity_id": entity_id, "entity_type": entity_type, "depth": depth},
                hops=depth,
            )

        seed = self._output(outputs, "seed") or []
        entities = self._output(outputs, "entities") or []
        relationships = self._output(outputs, "relationships") or []
        hops = self._output(outputs, "hops") or 0
        seed_ids = {str(s.get("v_id")) for s in seed}

        entity_records = []
        for e in entities:
            pid = str(e.get("v_id"))
            score = 1.0 if pid in seed_ids else 0.5
            entity_records.append(self._entity(e, relevance=score))

        context = self._context(
            operation="entity_lookup",
            query={"entity_id": entity_id, "entity_type": entity_type, "depth": depth},
            entities=entity_records,
            relationships=[self._relationship(e) for e in relationships],
            hops=int(hops),
            latency_ms=(time.monotonic() - t0) * 1000,
            source_documents=[entity_id] if entity_type == "Paper" else [],
            visited=[],  # type: ignore[list-item]
        )
        return context

    def path_search(
        self,
        source: str,
        target: str,
        max_hops: int = 4,
    ) -> SubgraphContext:
        """BFS shortest path between *source* and *target*.

        Reuses the neighbourhood expansion (real GSQL results) and performs
        the BFS itself over the returned edges, which is robust to the
        mixed-type graph.  ``source``/``target`` may be ``(entity_id, type)``
        tuples or bare ids (the id is searched across Paper/Author/Concept).
        """
        src_id, src_type = self._split_entity(source)
        tgt_id, tgt_type = self._split_entity(target)

        t0 = time.monotonic()
        try:
            outputs = self._run(
                TG_NEIGHBORHOOD,
                {"seed_id": src_id, "seed_type": src_type or "Paper", "depth": max_hops, "top_k": 500},
            )
        except Exception:
            return self._empty_context("path_search", {"source": source, "target": target}, hops=max_hops)

        entities = self._output(outputs, "entities") or []
        relationships = self._output(outputs, "relationships") or []
        hops = self._output(outputs, "hops") or 0

        # Index vertices and edges.
        v_by_key = {}
        for e in entities:
            key = (str(e.get("v_type")), str(e.get("v_id")))
            v_by_key[key] = e
        adj: dict[tuple[str, str], list[tuple[str, str, dict]]] = {}
        for r in relationships:
            u = (str(r.get("from_type")), str(r.get("from_id")))
            w = (str(r.get("to_type")), str(r.get("to_id")))
            edge = {"from_id": r.get("from_id"), "from_type": r.get("from_type"),
                    "to_id": r.get("to_id"), "to_type": r.get("to_type"), "e_type": r.get("e_type")}
            adj.setdefault(u, []).append((w, r.get("e_type"), edge))
            adj.setdefault(w, []).append((u, r.get("e_type"), edge))

        src_key = (src_type or self._guess_type(src_id, v_by_key), src_id)
        tgt_key = (tgt_type or self._guess_type(tgt_id, v_by_key), tgt_id)

        path_nodes, path_edges = self._bfs_path(adj, src_key, tgt_key, max_hops=max_hops)

        paths: list[dict[str, Any]] = []
        if path_nodes:
            paths.append(
                {
                    "entities": [n[1] for n in path_nodes],
                    "relationships": [pe["id"] if "id" in pe else f"{pe['from_id']}--{pe['e_type']}-->{pe['to_id']}" for pe in path_edges],
                    "path_summary": " -> ".join(n[1] for n in path_nodes),
                }
            )

        path_ids = {n[1] for n in path_nodes}
        entity_records = [
            self._entity(e, relevance=1.0 if str(e.get("v_id")) in {src_id, tgt_id} else 0.6)
            for e in entities
            if str(e.get("v_id")) in path_ids or str(e.get("v_id")) in {src_id, tgt_id}
        ]
        rel_records: list[dict[str, Any]] = []
        for pe in path_edges:
            rel_records.append(self._relationship(pe))

        return self._context(
            operation="path_search",
            query={"source": source, "target": target, "max_hops": max_hops},
            entities=entity_records,
            relationships=rel_records,
            paths=paths,
            hops=int(hops),
            latency_ms=(time.monotonic() - t0) * 1000,
            source_documents=[],
            visited=[],
        )

    def neighborhood(
        self,
        entity_id: str,
        depth: int = 2,
        edge_types: list[str] | None = None,
    ) -> SubgraphContext:
        t0 = time.monotonic()
        try:
            outputs = self._run(
                TG_NEIGHBORHOOD,
                {"seed_id": entity_id, "seed_type": "Paper", "depth": depth, "top_k": 200},
            )
        except Exception:
            return self._empty_context("neighborhood", {"entity_id": entity_id, "depth": depth}, hops=depth)

        seed = self._output(outputs, "seed") or []
        entities = self._output(outputs, "entities") or []
        relationships = self._output(outputs, "relationships") or []
        hops = self._output(outputs, "hops") or 0

        seed_ids = {str(s.get("v_id")) for s in seed}
        if seed_ids and edge_types:
            rel_records = [
                self._relationship(e) for e in relationships
                if e.get("e_type") in set(edge_types)
            ]
        else:
            rel_records = [self._relationship(e) for e in relationships]

        entity_records = [
            self._entity(e, relevance=1.0 if str(e.get("v_id")) in seed_ids else 0.5)
            for e in entities
        ]
        return self._context(
            operation="neighborhood",
            query={"entity_id": entity_id, "depth": depth, "edge_types": edge_types or []},
            entities=entity_records[:200],
            relationships=rel_records[:200],
            hops=int(hops),
            latency_ms=(time.monotonic() - t0) * 1000,
            source_documents=[],
            visited=[],
        )

    def community_members(
        self,
        community_id: str,
        include_summary: bool = True,
    ) -> SubgraphContext:
        t0 = time.monotonic()
        try:
            outputs = self._run(TG_CONCEPT_MEMBERS, {"concept_name": community_id, "top_k": 100})
        except Exception:
            return self._empty_context("community_members", {"community_id": community_id}, hops=1)

        papers = self._output(outputs, "papers") or []
        concepts = self._output(outputs, "concepts") or []

        # papers are bare id strings from a SetAccum; enrich via REST++.
        paper_ids = [str(p) for p in papers]
        raw: list[dict[str, Any]] = []
        entity_records: list[dict[str, Any]] = []
        if paper_ids:
            try:
                raw = self.conn.getVerticesById("Paper", paper_ids, select="id,title,categories,published,abstract_token_count")
                for r in raw:
                    entity_records.append(self._entity(r, relevance=0.7))
            except Exception:
                entity_records = [
                    {"id": pid, "type": "Paper", "name": pid, "properties": {}, "relevance_score": 0.7, "source_chunks": []}
                    for pid in paper_ids
                ]

        communities = []
        for c in concepts:
            cid = str(c)
            member_count = len(paper_ids)
            communities.append(
                {
                    "id": f"concept:{cid}",
                    "level": 1,
                    "summary": f"Papers mentioning concept '{cid}'." if include_summary else "",
                    "member_count": member_count,
                    "centroid_entity": cid,
                }
            )

        chunks = self._text_chunks_from_papers(
            [self._entity(r, relevance=0.7) for r in raw],
        )

        return self._context(
            operation="community_members",
            query={"community_id": community_id, "include_summary": include_summary},
            entities=entity_records,
            relationships=[],
            communities=communities,
            text_chunks=chunks,
            hops=1,
            latency_ms=(time.monotonic() - t0) * 1000,
            source_documents=[p for p in paper_ids],
            visited=[],
        )

    # ------------------------------------------------------------------
    # Schema / provenance / health
    # ------------------------------------------------------------------

    def get_schema(self, graph_id: str | None = None) -> GraphSchema:
        conn = self.conn
        schema = conn.getSchema()
        vid = graph_id or self._graphname

        vertex_types: list[EntityType] = []
        edge_types: list[RelationshipType] = []

        vtypes_raw = schema.get("VertexTypes", [])
        for vt in vtypes_raw:
            name = vt.get("Name")
            count = self._vertex_type_count(conn, name) if name else 0
            attrs = []
            pk = ""
            primary = vt.get("PrimaryId") or {}
            pk = primary.get("AttributeName", "")
            for a in vt.get("Attributes", []):
                attrs.append({"name": a.get("AttributeName"), "type": a.get("AttributeType", {}).get("Name"), "nullable": False})
            emb_attrs = vt.get("EmbeddingAttributes", [])
            for e in emb_attrs:
                attrs.append({
                    "name": e.get("Name"),
                    "type": f"EMBEDDING({e.get('Dimension')})",
                    "metric": e.get("Metric"),
                    "nullable": False,
                })
            sample = None
            if name and count > 0:
                try:
                    rows = conn.getVertices(name, limit=1)
                    if rows:
                        sample = {k: v for k, v in (rows[0].get("attributes") or {}).items()}
                except Exception:
                    sample = None
            vertex_types.append(
                EntityType(type=name, count=count, primary_key=pk, attributes=attrs, sample=sample)
            )

        for et in schema.get("EdgeTypes", []):
            name = et.get("Name")
            try:
                ecount = int(conn.getEdgeCount(name))
            except Exception:
                ecount = 0
            edge_types.append(
                RelationshipType(
                    type=name,
                    source=et.get("FromVertexTypeName", ""),
                    target=et.get("ToVertexTypeName", ""),
                    count=ecount,
                    attributes=[],
                )
            )

        total_v = sum(vt.count for vt in vertex_types)
        total_e = sum(et.count for et in edge_types)
        avg_degree = round((2 * total_e) / total_v, 2) if total_v > 0 else 0.0
        stats = GraphStatistics(
            total_vertices=total_v,
            total_edges=total_e,
            avg_degree=avg_degree,
            connected_components=0,
        )
        return GraphSchema(
            protocol="graphrag/1.0",
            graph_id=vid,
            vertex_types=vertex_types,
            edge_types=edge_types,
            statistics=stats,
        )

    def get_provenance(self, context: SubgraphContext) -> Provenance:
        results = context.results
        entities = results.get("entities", []) or []
        chunks = results.get("text_chunks", []) or []
        paths = results.get("paths", []) or []

        visited = []
        for e in entities:
            visited.append(str(e.get("id")))
        for p in paths:
            for eid in p.get("entities", []):
                if eid not in visited:
                    visited.append(str(eid))

        source_docs = []
        for c in chunks:
            d = c.get("source_doc")
            if d and d not in source_docs:
                source_docs.append(str(d))

        traversal = [
            TraversalStep(step=i + 1, entity=eid, action="seed" if i == 0 else "expand")
            for i, eid in enumerate(visited)
        ]
        return Provenance(
            source_documents=source_docs,
            traversal_log=traversal,
            visited_not_cited=[],
            total_entities_examined=len(entities),
            total_chunks_returned=len(chunks),
            backend="tigergraph",
            backend_version=self._backend_version(),
        )

    def health_check(self) -> dict:
        try:
            self.conn.echo()
            version = self._backend_version() or "unknown"
            return {
                "status": "ok",
                "backend": "tigergraph",
                "version": version,
                "graph_id": self._graphname,
                "uri": self._host,
            }
        except Exception as exc:
            return {"status": "error", "backend": "tigergraph", "error": str(exc)}

    # ------------------------------------------------------------------
    # Embedding support (hybrid search)
    # ------------------------------------------------------------------

    def _embedding_enabled(self) -> bool:
        conn = self.conn
        if not self._is_ready(conn, "PaperEmb"):
            self._embed_available = False
            return False
        if self._embedder is not None:
            self._embed_available = True
            return True
        if os.environ.get("GOOGLE_API_KEY"):
            self._embed_available = True
            return True
        self._embed_available = False
        return False

    def _embed(self, text: str) -> list[float] | None:
        if self._embedder is not None:
            try:
                emb = self._embedder(text)
                return list(emb)
            except Exception:
                return None
        if not os.environ.get("GOOGLE_API_KEY"):
            return None
        from google import genai

        if self._embed_client is None:
            self._embed_client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
        try:
            resp = self._embed_client.models.embed_content(
                model=_EMBED_MODEL,
                contents=[text],
                config={"output_dimensionality": _EMBED_DIM},
            )
            values = resp.embeddings[0].values
            return [float(v) for v in values]
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _terms(query: str, entity_hints: list[str] | None) -> list[str]:
        """Tokenize query + hints into lookup terms.

        Terms are whitespace-split, lowercased tokens of length >= 3 that are
        not pure punctuation/numbers.  Hints are added verbatim.
        """
        terms: list[str] = []
        for hint in entity_hints or []:
            hint = str(hint).strip()
            if hint and hint not in terms:
                terms.append(hint)
        for token in (query or "").split():
            token = token.strip(".,;:!?()[]{}'\"")
            if len(token) >= 3 and not token.isdigit() and token.lower() not in terms:
                terms.append(token.lower())
        return terms or [query or ""]

    def _resolve_entity(self, name: str, entity_type: str | None) -> tuple[str, str] | None:
        """Resolve a bare entity name to (id, type) via REST++ lookups."""
        conn = self.conn
        if entity_type:
            return self._resolve_in_type(conn, name, entity_type)
        for vtype in ("Paper", "Concept", "Author"):
            hit = self._resolve_in_type(conn, name, vtype)
            if hit:
                return hit
        return None

    @staticmethod
    def _resolve_in_type(conn, name: str, vtype: str) -> tuple[str, str] | None:
        try:
            rows = conn.getVertices(vtype, where=f'id=="{name}" OR name=="{name}"', limit=1)
            if rows:
                return str(rows[0]["v_id"]), vtype
        except Exception:
            return None
        return None

    @staticmethod
    def _split_entity(entity: str | tuple[str, str]) -> tuple[str, str | None]:
        """Split a ``(id, type)`` tuple or bare id string into parts."""
        if isinstance(entity, (tuple, list)) and len(entity) == 2:
            return str(entity[0]), str(entity[1])
        return str(entity), None

    @staticmethod
    def _guess_type(vid: str, vertices: dict[tuple[str, str], dict]) -> str | None:
        for (vtype, _vid) in vertices:
            if str(vid) == str(_vid):
                return vtype
        return "Paper"

    @staticmethod
    def _bfs_path(
        adj: dict[tuple[str, str], list[tuple[tuple[str, str], str, dict]]],
        start: tuple[str, str],
        goal: tuple[str, str],
        max_hops: int,
    ) -> tuple[list[tuple[str, str]], list[dict]]:
        """BFS shortest path returning (nodes, edges)."""
        from collections import deque

        if start not in adj or goal not in adj:
            return [], []
        parent: dict[tuple[str, str], tuple[tuple[str, str], dict]] = {}
        queue: deque[tuple[str, str]] = deque([start])
        visited = {start}
        while queue:
            cur = queue.popleft()
            if cur == goal:
                break
            for nxt, etype, edge in adj.get(cur, []):
                if nxt not in visited:
                    visited.add(nxt)
                    parent[nxt] = (cur, edge)
                    queue.append(nxt)
        if goal not in parent and start != goal:
            return [], []

        nodes: list[tuple[str, str]] = []
        edges: list[dict] = []
        cur = goal
        while cur != start:
            prev, edge = parent[cur]
            edges.append(edge)
            nodes.append(cur)
            cur = prev
        nodes.append(start)
        nodes.reverse()
        edges.reverse()
        if len(nodes) - 1 > max_hops:
            return [], []
        return nodes, edges

    @staticmethod
    def _merge(
        local_entities: list[dict[str, Any]],
        local_relationships: list[dict[str, Any]],
        vector_entities: list[dict[str, Any]],
        vector_scores: list[tuple[str, float]],
        vector_weight: float,
        graph_weight: float,
        top_k: int,
    ) -> tuple[dict[str, Any], bool]:
        """Merge vector hits into keyword-local results."""
        merged: dict[str, dict[str, Any]] = {}
        for e in local_entities:
            merged[e["id"]] = {**e, "relevance_score": e.get("relevance_score", 0.5) * max(graph_weight, 0.1)}
        used_vector = False
        if vector_entities:
            used_vector = True
            for e, (pid, score) in zip(vector_entities, vector_scores):
                vscore = score * max(vector_weight, 0.1)
                if pid in merged:
                    prev = merged[pid]["relevance_score"]
                    merged[pid]["relevance_score"] = max(prev, vscore)
                else:
                    merged[pid] = {**e, "relevance_score": vscore}
        ranked = sorted(merged.values(), key=lambda e: e.get("relevance_score", 0), reverse=True)[:top_k]
        return {"entities": ranked, "relationships": local_relationships}, used_vector

    def _backend_version(self) -> str | None:
        try:
            conn = self.conn
            ver = conn.getVersion()
            if isinstance(ver, list):
                for item in ver:
                    if isinstance(item, dict) and item.get("name") == "product":
                        return str(item.get("version", ""))
            elif isinstance(ver, dict):
                return str(ver.get("version", ""))
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Context building
    # ------------------------------------------------------------------

    def _context(
        self,
        operation: str,
        query: dict[str, Any],
        entities: list[dict[str, Any]],
        relationships: list[dict[str, Any]],
        hops: int,
        latency_ms: float,
        source_documents: list[str],
        visited: list[str],
        paths: list[dict[str, Any]] | None = None,
        communities: list[dict[str, Any]] | None = None,
        text_chunks: list[dict[str, Any]] | None = None,
        note: str | None = None,
    ) -> SubgraphContext:
        paths = paths or []
        communities = communities or []
        text_chunks = text_chunks or []

        if note:
            query = {**query, "note": note}

        visited_ids = [v for v in visited if v not in [e.get("id") for e in entities]]
        total_examined = len(entities) + len(visited_ids)
        traversal = [
            TraversalStep(step=i + 1, entity=eid, action="seed" if i == 0 else "expand")
            for i, eid in enumerate([e.get("id") for e in entities] + visited_ids)
        ]
        provenance = Provenance(
            source_documents=list(dict.fromkeys(source_documents)),
            traversal_log=traversal,
            visited_not_cited=visited_ids,
            total_entities_examined=max(total_examined, len(entities)),
            total_chunks_returned=len(text_chunks),
            backend="tigergraph",
            backend_version=self._backend_version(),
        )
        metrics = RetrievalMetrics(
            input_tokens=len(str(query)),
            entities_returned=len(entities),
            relationships_returned=len(relationships),
            paths_found=len(paths),
            communities_matched=len(communities),
            graph_hops_traversed=int(hops),
            latency_ms=round(latency_ms, 2),
        )
        return SubgraphContext(
            protocol="graphrag/1.0",
            operation=operation,
            query=query,
            results={
                "entities": entities,
                "relationships": relationships,
                "paths": paths,
                "communities": communities,
                "text_chunks": text_chunks,
            },
            provenance=provenance,
            metrics=metrics,
        )

    def _empty_context(self, operation: str, query: dict[str, Any], hops: int = 0) -> SubgraphContext:
        return self._context(
            operation=operation,
            query=query,
            entities=[],
            relationships=[],
            hops=hops,
            latency_ms=0.0,
            source_documents=[],
            visited=[],
        )