"""TigerGraph reference adapter demo — runs all seven operations against the
live Savanna ``GraphragProtocol`` workspace via the protocol.

Requires ``.env`` (TIGERGRAPH_HOST/GSQL_SECRET/GRAPH_NAME; GOOGLE_API_KEY
optional for vector-backed hybrid search).  The six GSQL queries are
installed idempotently on first use.
"""

from __future__ import annotations

from dotenv import load_dotenv

from mcp_server.adapters import TigerGraphAdapter
from mcp_server.formatters import MarkdownFormatter
from mcp_server.protocol import SubgraphContext

load_dotenv()


def _clip(text: str, limit: int = 1200) -> str:
    return text if len(text) <= limit else text[:limit] + f" ... [{len(text) - limit} more chars]"


def _headline(op: str, context: SubgraphContext) -> None:
    m = context.metrics
    print(
        f"\n### {op.upper()}"
        f"  (entities={m.entities_returned}, relationships={m.relationships_returned}, "
        f"hops={m.graph_hops_traversed}, latency={m.latency_ms:.0f}ms)"
    )


def main() -> None:
    adapter = TigerGraphAdapter()

    print("== Health ==")
    print(adapter.health_check())

    print("\n== Schema ==")
    schema = adapter.get_schema()
    for vt in schema.vertex_types:
        print(f"  vertex {vt.type:12s} count={vt.count:6d} pk={vt.primary_key}")
    for et in schema.edge_types:
        print(f"  edge   {et.type:12s} {et.source}->{et.target} count={et.count:6d}")
    s = schema.statistics
    print(f"  totals vertices={s.total_vertices} edges={s.total_edges} avg_degree={s.avg_degree}")

    # Real seed papers from the live graph.
    papers = adapter.conn.getVertices("Paper", limit=2, select="id,title,categories,published,abstract_token_count")
    if not papers:
        print("\nNo Paper vertices yet — graph still building. Exiting demo.")
        return
    p1 = papers[0]
    p2 = papers[1] if len(papers) > 1 else papers[0]
    p1_id, p1_title = str(p1["v_id"]), (p1.get("attributes") or {}).get("title", str(p1["v_id"]))
    p2_id, p2_title = str(p2["v_id"]), (p2.get("attributes") or {}).get("title", str(p2["v_id"]))

    concepts = adapter.conn.getVertices("Concept", limit=1)
    concept_name = str(concepts[0]["attributes"].get("name", concepts[0]["v_id"])) if concepts else "transformer"

    print(f"\nSeed paper 1: {p1_title}  [{p1_id}]")
    print(f"Seed paper 2: {p2_title}  [{p2_id}]")
    print(f"Seed concept: {concept_name}")

    fmt = MarkdownFormatter()

    # 1. Local search over live graph.
    ctx = adapter.local_search(query="transformer attention mechanism", depth=2, top_k=8)
    _headline("local_search", ctx)
    print(_clip(fmt.format_context(ctx, max_tokens=1024)))

    # 2. Entity lookup of a real paper.
    ctx = adapter.entity_lookup(entity_id=p1_id, entity_type="Paper", depth=1)
    _headline("entity_lookup", ctx)
    for e in ctx.results["entities"][:4]:
        print(f"  - [{e['type']}] {e['name']}  (score={e['relevance_score']:.2f})")

    # 3. Global (community) search.
    ctx = adapter.global_search(query="overall research themes", top_communities=5)
    _headline("global_search", ctx)
    for c in ctx.results["communities"][:5]:
        print(f"  - {c['summary'][:90]}... (members={c['member_count']})")

    # 4. Hybrid search (keyword graph search; vector path enabled if PaperEmb
    #    is populated and an embedder is configured).
    try:
        ctx = adapter.hybrid_search(query="graph neural network embeddings", top_k=6)
        _headline("hybrid_search", ctx)
        note = ctx.query.get("note", "")
        print(f"  mode={note or 'keyword'}")
        for e in ctx.results["entities"][:6]:
            print(f"  - [{e['type']}] {e['name']} (score={e['relevance_score']:.2f})")
    except Exception as exc:  # noqa: BLE001
        print(f"  hybrid_search failed: {exc}")

    # 5. Neighborhood expansion.
    ctx = adapter.neighborhood(entity_id=p1_id, depth=1)
    _headline("neighborhood", ctx)
    for e in ctx.results["entities"][:6]:
        print(f"  - [{e['type']}] {e['name']}")

    # 6. Path search between the two seeded papers.
    ctx = adapter.path_search(source=p1_id, target=p2_id, max_hops=3)
    _headline("path_search", ctx)
    for p in ctx.results["paths"][:2]:
        print(f"  path: {p['path_summary'][:120]}")

    # 7. Community members for a real concept.
    ctx = adapter.community_members(community_id=concept_name)
    _headline("community_members", ctx)
    print(f"  papers: {[e['id'] for e in ctx.results['entities'][:5]]}")

    print("\n== Provenance (first) ==")
    prov = adapter.get_provenance(ctx)
    print(f"  backend={prov.backend} documents={prov.source_documents[:3]}")


if __name__ == "__main__":
    main()