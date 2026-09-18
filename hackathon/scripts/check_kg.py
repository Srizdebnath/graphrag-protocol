"""Verify the live GraphragProtocol knowledge graph in TigerGraph Savanna.

Prints real vertex/edge counts, a 3-paper fanout (authors + concepts) from the
live graph, and — when embeddings exist — a vectorSearch smoke test over the
PaperEmb vertex vector attribute.

Usage:
    python hackathon/scripts/check_kg.py [--limit 5]
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

# ---------------------------------------------------------------------------
# GSQL queries (syntax v3) — installed on the live graph
# ---------------------------------------------------------------------------

QUERY_FANOUT = """USE GRAPH {graph}
CREATE OR REPLACE QUERY PaperFanout(INT n) FOR GRAPH {graph} SYNTAX v3 {{
  MapAccum<STRING, ListAccum<STRING>> @@authors;
  MapAccum<STRING, ListAccum<STRING>> @@concepts;
  ListAccum<STRING> @@ids;
  Start = {{Paper.*}};
  Sampled = SELECT p FROM Start:p ORDER BY p.id LIMIT n;
  Ids = SELECT p FROM Sampled:p ACCUM @@ids += p.id;
  Auth = SELECT a FROM (s:Sampled) -[:AUTHORED_BY]-> (a:Author) ACCUM @@authors += (s.id -> a.name);
  Conc = SELECT c FROM (s:Sampled) -[:MENTIONS]-> (c:Concept) ACCUM @@concepts += (s.id -> c.name);
  PRINT @@ids, @@authors, @@concepts;
}}
INSTALL QUERY PaperFanout
"""

QUERY_COUNTS = """USE GRAPH {graph}
CREATE OR REPLACE QUERY EdgeCounts() FOR GRAPH {graph} SYNTAX v3 {{
  MapAccum<STRING, INT> @@counts;
  Start = {{Paper.*}};
  R1 = SELECT a FROM (s:Start) -[:AUTHORED_BY]-> (a:Author) ACCUM @@counts += ("AUTHORED_BY" -> 1);
  R2 = SELECT c FROM (s:Start) -[:MENTIONS]-> (c:Concept) ACCUM @@counts += ("MENTIONS" -> 1);
  R3 = SELECT t FROM (s:Start) -[:CITES]-> (t:Paper)    ACCUM @@counts += ("CITES" -> 1);
  PRINT @@counts;
}}
INSTALL QUERY EdgeCounts
"""

QUERY_VEC = """USE GRAPH {graph}
CREATE OR REPLACE QUERY VectorSmoke(LIST<FLOAT> q, INT k) FOR GRAPH {graph} SYNTAX v3 {{
  MapAccum<VERTEX<PaperEmb>, FLOAT> @@dist;
  MapAccum<STRING, FLOAT> @@out;
  MapAccum<STRING, STRING> @@titles;
  ListAccum<STRING> @@ids;
  Start = {{PaperEmb.*}};
  Top = vectorSearch({{PaperEmb.abstract_embedding}}, q, k, {{distance_map: @@dist}});
  Emb = SELECT pe FROM Top:pe POST-ACCUM @@out += (pe.id -> @@dist.get(pe)), @@ids += pe.id;
  P = {{Paper.*}};
  Res = SELECT pp FROM P:pp WHERE pp.id IN @@ids ACCUM @@titles += (pp.id -> pp.title);
  PRINT @@titles, @@out;
}}
INSTALL QUERY VectorSmoke
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="Check live GraphragProtocol graph")
    ap.add_argument("--embed-limit", type=int, default=1024, help="truncate query text for smoke embedding")
    ap.add_argument("--k", type=int, default=5, help="top-k for vector smoke test")
    args = ap.parse_args()

    from pyTigerGraph import TigerGraphConnection

    conn = TigerGraphConnection(
        host=os.environ["TIGERGRAPH_HOST"],
        graphname=os.environ["TIGERGRAPH_GRAPH_NAME"],
        gsqlSecret=os.environ["TIGERGRAPH_GSQL_SECRET"],
        tgCloud=True,
    )
    graph = conn.graphname
    print(f"[conn] {conn.host} graph={graph}")

    try:
        print("[version]", conn.getVersion())
    except Exception as e:  # noqa: BLE001
        print("[version] n/a:", e)

    print("\n=== VERTEX / EDGE COUNTS ===")
    pytg = {
        "Paper": None,
        "Author": None,
        "Concept": None,
        "PaperEmb": None,
    }
    for vt in pytg:
        try:
            c = conn.getVertexCount(vt)
            pytg[vt] = c
            print(f"  getVertexCount({vt}) = {c}")
        except Exception as e:  # noqa: BLE001
            print(f"  getVertexCount({vt}) FAILED: {e}")
    for et in ("AUTHORED_BY", "MENTIONS", "CITES"):
        try:
            print(f"  getEdgeCount({et}) = {conn.getEdgeCount(et)}")
        except Exception as e:  # noqa: BLE001
            print(f"  getEdgeCount({et}) FAILED: {e}")

    # Authoritative edge counts via GSQL traversal (stats can lag)
    print("\n=== AUTHORITATIVE EDGE COUNTS (GSQL traversal) ===")
    try:
        conn.gsql(QUERY_COUNTS.format(graph=graph))
        res = conn.runInstalledQuery("EdgeCounts", {})
        _pprint(res)
    except Exception as e:  # noqa: BLE001
        print("EdgeCounts FAILED:", type(e).__name__, e)

    # --- fanout query ----------------------------------------------------
    print("\n=== SAMPLE FANOUT (3 papers -> authors, concepts) ===")
    try:
        conn.gsql(QUERY_FANOUT.format(graph=graph))
        res = conn.runInstalledQuery("PaperFanout", {"n": 3})
        _pprint(res)
    except Exception as e:  # noqa: BLE001
        print("fanout FAILED:", type(e).__name__, e)

    # --- vector smoke -----------------------------------------------------
    n_emb = pytg.get("PaperEmb") or 0
    if n_emb > 0:
        print("\n=== VECTOR SEARCH SMOKE TEST ===")
        try:
            _print_vector_status(conn)
        except Exception as e:  # noqa: BLE001
            print("vector/status FAILED:", type(e).__name__, e)
        try:
            conn.gsql(QUERY_VEC.format(graph=graph))
            qvec = _make_query_embedding(args.embed_limit)
            if qvec:
                res = conn.runInstalledQuery("VectorSmoke", {"q": qvec, "k": args.k})
                _pprint(res)
            else:
                print("could not produce query embedding (check GOOGLE_API_KEY)")
        except Exception as e:  # noqa: BLE001
            print("VectorSmoke FAILED:", type(e).__name__, e)
    else:
        print("\n(PaperEmb count is 0 — embeddings absent; skipping vector smoke test)")


def _print_vector_status(conn) -> None:
    """Poll /restpp/vector/status using a bearer token minted from the secret."""
    import httpx

    conn.getToken(secret=os.environ["TIGERGRAPH_GSQL_SECRET"])
    token = getattr(conn, "apiToken", None) or os.environ["TIGERGRAPH_GSQL_SECRET"]
    host = conn.host
    url = f"{host}/restpp/vector/status" if "/restpp" not in host else host.rstrip("/") + "/vector/status"
    # TLS verification is on by default. Only set TIGERGRAPH_TLS_VERIFY=false
    # for known-broken cert chains (e.g. corporate proxies) — never casually.
    verify_tls = os.environ.get("TIGERGRAPH_TLS_VERIFY", "true").lower() not in ("0", "false", "no")
    r = httpx.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=30, verify=verify_tls)
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text
    print(f"  vector/status ({r.status_code}):", body)


def _make_query_embedding(limit: int):
    """Embed a representative arxiv-style query so we can exercise vectorSearch."""
    key = os.environ.get("GOOGLE_API_KEY")
    if not key:
        return None
    from google import genai

    query_text = (
        "graph neural network transformer embeddings for knowledge graph reasoning "
        "and retrieval augmented generation on scientific literature"
    )
    if limit and limit < len(query_text):
        query_text = query_text[:limit]
    client = genai.Client(api_key=key)
    cfg = genai.types.EmbedContentConfig(output_dimensionality=512, task_type="RETRIEVAL_QUERY")
    resp = client.models.embed_content(
        model=os.environ.get("TIGERGRAPH_EMBED_MODEL", "gemini-embedding-001"),
        contents=[query_text],
        config=cfg,
    )
    return list(resp.embeddings[0].values)


def _pprint(res) -> None:
    import json

    try:
        out = json.dumps(res, indent=2, default=str)[:4000]
    except TypeError:
        out = str(res)[:4000]
    print(out)


if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"\n[check] done in {time.time() - t0:.1f}s")