"""Build the arXiv knowledge graph in TigerGraph (Savanna) from papers.jsonl.

Loads real data (ZERO MOCK): upserts Paper / Author / Concept vertices and
AUTHORED_BY / MENTIONS edges, and optionally embeds abstracts into a separate
PaperEmb vertex with a real vector attribute for hybrid search.

Schema + DDL are created idempotently via conn.gsql() (GSQL Server API on 4.x).
All upserts are rerun-safe (upsert semantics).

Usage:
    python hackathon/scripts/build_kg.py --limit 400 --embed      # smoke test
    python hackathon/scripts/build_kg.py --limit 8000 --embed     # full run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyTigerGraph import TigerGraphConnection

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = PROJECT_ROOT / "hackathon" / "data" / "papers" / "papers.jsonl"

load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_EMBED_MODEL = os.environ.get("TIGERGRAPH_EMBED_MODEL", "gemini-embedding-001")
EMBED_DIM = 512

# ---------------------------------------------------------------------------
# Schema DDL (TigerGraph 4.x on Savanna)
# ---------------------------------------------------------------------------

DDL_VERTEX_TEMPLATE = """USE GLOBAL
{pfx}CREATE VERTEX Paper (PRIMARY_ID id STRING, title STRING, abstract STRING, categories STRING, published DATETIME, abstract_token_count INT) WITH PRIMARY_ID_AS_ATTRIBUTE="true"
{pfx}CREATE VERTEX Author (PRIMARY_ID name STRING) WITH PRIMARY_ID_AS_ATTRIBUTE="true"
{pfx}CREATE VERTEX Concept (PRIMARY_ID name STRING) WITH PRIMARY_ID_AS_ATTRIBUTE="true"
{pfx}CREATE DIRECTED EDGE CITES (FROM Paper, TO Paper)
{pfx}CREATE DIRECTED EDGE AUTHORED_BY (FROM Paper, TO Author)
{pfx}CREATE DIRECTED EDGE MENTIONS (FROM Paper, TO Concept)
"""

DDL_ATTACH_TYPES = """USE GLOBAL
CREATE GLOBAL SCHEMA_CHANGE JOB gp_attach_types {{
  ADD VERTEX Paper TO GRAPH {graph};
  ADD VERTEX Author TO GRAPH {graph};
  ADD VERTEX Concept TO GRAPH {graph};
  ADD EDGE CITES TO GRAPH {graph};
  ADD EDGE AUTHORED_BY TO GRAPH {graph};
  ADD EDGE MENTIONS TO GRAPH {graph};
}}
RUN GLOBAL SCHEMA_CHANGE JOB gp_attach_types
"""

DDL_PAPEREMB_TEMPLATE = """USE GLOBAL
CREATE VERTEX PaperEmb (PRIMARY_ID id STRING) WITH PRIMARY_ID_AS_ATTRIBUTE="true"
"""

DDL_ADD_VECTOR = """USE GLOBAL
CREATE GLOBAL SCHEMA_CHANGE JOB gp_add_vec {{
  ADD VERTEX PaperEmb TO GRAPH {graph};
  ALTER VERTEX PaperEmb ADD VECTOR ATTRIBUTE abstract_embedding(DIMENSION={dim}, METRIC="COSINE");
}}
RUN GLOBAL SCHEMA_CHANGE JOB gp_add_vec
"""

# ---------------------------------------------------------------------------
# Concept extraction (stopword + frequency filter, top-K per paper)
# ---------------------------------------------------------------------------

STOPWORDS = {"a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", "by", "can", "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during", "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such", "than", "that", "that's", "the", "their", "theirs", "them", "themselves", "then", "there", "there's", "these", "they", "they'd", "they'll", "they're", "they've", "this", "those", "through", "to", "too", "under", "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were", "weren't", "what", "what's", "when", "when's", "where", "where's", "which", "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours", "yourself", "yourselves", "paper", "papers", "study", "studies", "approach", "approaches", "method", "methods", "model", "models", "framework", "frameworks", "system", "systems", "technique", "techniques", "result", "results", "dataset", "datasets", "data", "performance", "propose", "proposed", "using", "based", "used", "use", "via", "also", "thus", "however", "new", "two", "one", "set", "well", "work", "works", "show", "shown", "state", "art", "general", "learning", "learned", "experimental", "experiment", "experiments", "evaluation", "evaluate", "evaluated", "benchmark", "benchmarks"}


def extract_concepts(title: str, abstract: str, max_concepts: int = 5) -> list[str]:
    """Pick the most frequent non-stopword tokens from title+abstract."""
    text = f"{title} {abstract}".lower()
    tokens = re.findall(r"[a-z][a-z0-9\-]{2,}", text)
    counts: Counter = Counter()
    for t in tokens:
        t = t.strip("-")
        if len(t) < 4 or t in STOPWORDS:
            continue
        counts[t] += 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [k for k, _ in ranked[:max_concepts]]


def _to_tg_datetime(iso: str) -> str | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Connection + GSQL helpers
# ---------------------------------------------------------------------------


def connect() -> TigerGraphConnection:
    from pyTigerGraph import TigerGraphConnection

    conn = TigerGraphConnection(
        host=os.environ["TIGERGRAPH_HOST"],
        graphname=os.environ["TIGERGRAPH_GRAPH_NAME"],
        gsqlSecret=os.environ["TIGERGRAPH_GSQL_SECRET"],
        tgCloud=True,
    )
    return conn


ERROR_MARKERS = (
    "Encountered \"",
    "SEMANTIC ERROR",
    "Syntax Error",
    "Failed to create",
    "does not exist",
    "is not a valid",
    "Invalid syntax",
)


def gsql_ok(conn, script: str, label: str, allow_errors: bool = False) -> str:
    """Run a GSQL script; raise on hard errors unless explicitly allowed."""
    print(f"[gsql] {label} ...")
    t0 = time.time()
    try:
        out = conn.gsql(script)
    except Exception as e:
        print(f"[gsql] {label} RAISED: {type(e).__name__}: {e}")
        if allow_errors:
            return ""
        raise
    out = str(out).strip()
    dt = time.time() - t0
    if out:
        preview = (out[:400] + "..." if len(out) > 400 else out)
        print(f"[gsql] {label} ok in {dt:.1f}s:\n{preview}")
    else:
        print(f"[gsql] {label} ok in {dt:.1f}s (no output)")
    return out


def _looks_like_error(out: str) -> bool:
    return any(m in out for m in ERROR_MARKERS)


def _poll_until(fn, cond, timeout: int = 60, interval: int = 5, what: str = "") -> list:
    """Call fn() until cond(result) or timeout; used to wait out read-path stat lag."""
    import time as _t

    t0 = _t.time()
    while _t.time() - t0 < timeout:
        try:
            res = fn()
            if cond(res):
                return res
        except Exception as e:  # noqa: BLE001
            print(f"  poll {what} got {type(e).__name__}: {e}")
        _t.sleep(interval)
    print(f"  WARN: timed out waiting for {what}")
    return []


# ---------------------------------------------------------------------------
# Schema creation (idempotent)
# ---------------------------------------------------------------------------


def create_schema(conn) -> dict:
    """Create vertex/edge types + graph membership if missing. Rerun-safe."""
    report = {"vertices": {}, "edges": {}, "embedding": False}

    try:
        vtypes = conn.getVertexTypes()
    except Exception as e:  # noqa: BLE001
        print(f"getVertexTypes() failed: {e}")
        vtypes = []

    if "Paper" not in vtypes:
        script = DDL_VERTEX_TEMPLATE.format(pfx="")
        gsql_ok(conn, script, "create vertices/edges")
        gsql_ok(conn, DDL_ATTACH_TYPES.format(graph=conn.graphname), "attach types to graph")
    else:
        print("[schema] Paper already exists; skipping type creation")

    # Schema-change stats can lag on the read path; poll until Paper shows up or timeout.
    vtypes = _poll_until(
        conn.getVertexTypes,
        lambda vts: "Paper" in vts,
        timeout=90,
        interval=5,
        what="Paper visible in graph",
    )
    for vt in ("Paper", "Author", "Concept"):
        report["vertices"][vt] = vt in vtypes

    ets = conn.getEdgeTypes() or []
    for et in ("CITES", "AUTHORED_BY", "MENTIONS"):
        report["edges"][et] = et in ets

    # --- PaperEmb + vector attribute -----------------------------------
    if "PaperEmb" not in vtypes:
        gsql_ok(conn, DDL_PAPEREMB_TEMPLATE, "create PaperEmb")

    has_vec = _paperemb_has_vector(conn)
    if not has_vec:
        gsql_ok(
            conn,
            DDL_ADD_VECTOR.format(graph=conn.graphname, dim=EMBED_DIM),
            "add vector attribute + attach PaperEmb",
        )
        has_vec = _paperemb_has_vector(conn)
    report["embedding"] = has_vec

    print(f"[schema] done: {report}")
    return report


def _paperemb_has_vector(conn) -> bool:
    try:
        out = conn.gsql("USE GLOBAL\nls")
        return "abstract_embedding" in str(out)
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# Upsert helpers
# ---------------------------------------------------------------------------


def upsert_vertices(conn, vtype: str, items: list, batch: int, label: str) -> int:
    """items: list of (id, {attr: val}). Returns accepted count."""
    total = 0
    n = len(items)
    for i in range(0, n, batch):
        chunk = items[i : i + batch]
        try:
            total += conn.upsertVertices(vtype, chunk, atomic=False)
        except Exception as e:  # noqa: BLE001
            print(f"  !! {label} batch {i // batch} failed: {type(e).__name__}: {e}")
        if (i // batch + 1) % 10 == 0 or i + batch >= n:
            print(f"  {label}: {min(i + batch, n)}/{n}")
    return total


def upsert_edges(conn, stype, etype, ttype, items, batch, label) -> int:
    """items: list of (from_id, to_id). Returns accepted count."""
    total = 0
    n = len(items)
    for i in range(0, n, batch):
        chunk = items[i : i + batch]
        try:
            total += conn.upsertEdges(stype, etype, ttype, chunk, vertexMustExist=False, atomic=False)
        except Exception as e:  # noqa: BLE001
            print(f"  !! {label} batch {i // batch} failed: {type(e).__name__}: {e}")
        if (i // batch + 1) % 10 == 0 or i + batch >= n:
            print(f"  {label}: {min(i + batch, n)}/{n}")
    return total


# ---------------------------------------------------------------------------
# Embeddings (google-genai, batched, rate-limit aware)
# ---------------------------------------------------------------------------


def embed_batch(client, model: str, texts: list[str], dim: int) -> list[list[float]]:
    from google import genai

    cfg = genai.types.EmbedContentConfig(output_dimensionality=dim, task_type="RETRIEVAL_DOCUMENT")
    resp = client.models.embed_content(model=model, contents=texts, config=cfg)
    out = []
    for e in resp.embeddings:
        vals = getattr(e, "values", None)
        if vals is None:
            vals = getattr(e, "embedding", [])
        out.append([float(x) for x in vals])
    return out


def embed_all(client, model: str, papers: list[dict], batch: int) -> list[tuple]:
    """Embed every paper abstract; returns [(id, vector), ...] with backoff on rate limits."""
    vectors: list[tuple] = []
    for i in range(0, len(papers), batch):
        chunk = papers[i : i + batch]
        texts = [f"{p['title']}\n{p['abstract']}"[:8000] for p in chunk]
        attempt = 0
        while True:
            try:
                embs = embed_batch(client, model, texts, EMBED_DIM)
                break
            except Exception as e:
                attempt += 1
                msg = str(e)
                retriable = "429" in msg or "RESOURCE_EXHAUSTED" in msg or "500" in msg or "503" in msg
                if attempt > 8 or not retriable:
                    print(f"  !! embed batch {i // batch} failed permanently: {msg}")
                    raise
                backoff = min(60, 2 ** attempt + (attempt * 3))
                print(f"  !! embed backoff {msg[:80]}... retry {attempt} in {backoff}s")
                time.sleep(backoff)
        vectors.extend((p["id"], v) for p, v in zip(chunk, embs))
        if (i // batch + 1) % 5 == 0 or i + batch >= len(papers):
            print(f"  embedded {min(i + batch, len(papers))}/{len(papers)}")
    return vectors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser(description="Load papers.jsonl into TigerGraph GraphragProtocol")
    ap.add_argument("--limit", type=int, default=8000, help="max papers to load (default 8000)")
    ap.add_argument("--batch", type=int, default=100, help="upsert/embed batch size (default 100)")
    ap.add_argument("--embed", action="store_true", help="embed abstracts into PaperEmb")
    ap.add_argument("--embed-model", default=DEFAULT_EMBED_MODEL)
    ap.add_argument("--skip-schema", action="store_true", help="assume schema already exists")
    ap.add_argument("--data", default=str(DATA_PATH), help="path to papers.jsonl")
    ap.add_argument("--max-concepts", type=int, default=5, help="concepts per paper")
    args = ap.parse_args()

    t_start = time.time()
    conn = connect()
    print(f"[conn] connected: {conn.host} graph={conn.graphname}")

    if not args.skip_schema:
        create_schema(conn)
    else:
        vtypes = conn.getVertexTypes()
        print(f"[schema] skipped (--skip-schema); current vertex types: {vtypes}")

    # --- Load papers --------------------------------------------------
    papers: list[dict] = []
    with open(args.data, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            papers.append(json.loads(line))
            if len(papers) >= args.limit:
                break
    print(f"[data] {len(papers)} papers loaded from {args.data}")

    # --- Prepare structures -------------------------------------------
    paper_attrs = []
    author_ids: set[str] = set()
    edge_authored: list[tuple[str, str]] = []
    edge_mentions: list[tuple[str, str]] = []
    concept_ids: set[str] = set()

    for p in papers:
        pid = p["id"]
        published = _to_tg_datetime(p.get("published", ""))
        attrs = {
            "title": p.get("title", ""),
            "abstract": p.get("abstract", ""),
            "categories": ", ".join(p.get("categories") or []),
            "abstract_token_count": int(p.get("abstract_token_count") or 0),
        }
        if published:
            attrs["published"] = published
        paper_attrs.append((pid, attrs))

        for a in p.get("authors") or []:
            a = str(a).strip()
            if a:
                author_ids.add(a)
                edge_authored.append((pid, a))

        for c in extract_concepts(p.get("title", ""), p.get("abstract", ""), args.max_concepts):
            concept_ids.add(c)
            edge_mentions.append((pid, c))

    author_items = [(n, {"name": n}) for n in sorted(author_ids)]
    concept_items = [(n, {"name": n}) for n in sorted(concept_ids)]
    print(
        f"[data] {len(paper_attrs)} papers, {len(author_items)} unique authors, "
        f"{len(concept_items)} unique concepts, "
        f"{len(edge_authored)} AUTHORED_BY edges, {len(edge_mentions)} MENTIONS edges"
    )

    # --- Upsert vertices ----------------------------------------------
    t0 = time.time()
    n_papers = upsert_vertices(conn, "Paper", paper_attrs, args.batch, "Paper")
    n_authors = upsert_vertices(conn, "Author", author_items, args.batch, "Author")
    n_concepts = upsert_vertices(conn, "Concept", concept_items, args.batch, "Concept")
    print(f"[load] vertices upserted in {time.time() - t0:.1f}s (papers={n_papers}, authors={n_authors}, concepts={n_concepts})")

    # --- Upsert edges --------------------------------------------------
    t0 = time.time()
    n_auth_edges = upsert_edges(conn, "Paper", "AUTHORED_BY", "Author", edge_authored, args.batch, "AUTHORED_BY")
    n_ment_edges = upsert_edges(conn, "Paper", "MENTIONS", "Concept", edge_mentions, args.batch, "MENTIONS")
    print(f"[load] edges upserted in {time.time() - t0:.1f}s (AUTHORED_BY={n_auth_edges}, MENTIONS={n_ment_edges})")

    # --- Embeddings -----------------------------------------------------
    n_emb = 0
    if args.embed:
        from google import genai

        key = os.environ.get("GOOGLE_API_KEY")
        if not key:
            print("[embed] GOOGLE_API_KEY missing; skipping embeddings")
        else:
            try:
                client = genai.Client(api_key=key)
                t0 = time.time()
                vectors = embed_all(client, args.embed_model, papers, args.batch)
                if vectors:
                    items = [(pid, {"abstract_embedding": vec}) for pid, vec in vectors]
                    n_emb = upsert_vertices(conn, "PaperEmb", items, args.batch, "PaperEmb")
                print(f"[load] embeddings upserted in {time.time() - t0:.1f}s (PaperEmb accepted={n_emb})")
            except Exception as e:  # noqa: BLE001
                print(f"[embed] FAILED: {type(e).__name__}: {e} — graph load continues WITHOUT embeddings")

    # --- Verify with real counts ----------------------------------------
    # Savanna count stats can lag a few seconds behind writes; poll until they settle.
    print("\n=== VERIFICATION (live graph) ===")
    time.sleep(3)

    def _count(fn, label: str):
        last = None
        for _ in range(8):
            try:
                last = fn()
                time.sleep(6)
                again = fn()
                if again == last:
                    return again
            except Exception as e:  # noqa: BLE001
                print(f"  {label} read failed: {e}")
                time.sleep(6)
        return last

    counts = {}
    for vt in ("Paper", "Author", "Concept", "PaperEmb"):
        counts[vt] = _count(lambda vt=vt: conn.getVertexCount(vt), f"getVertexCount({vt})")
        print(f"  getVertexCount({vt}) = {counts[vt]}")

    def _ecount(et: str):
        try:
            return conn.getEdgeCount(et)
        except Exception as e:  # noqa: BLE001
            print(f"  getEdgeCount({et}) failed: {e}")
            return None

    time.sleep(3)
    for et in ("AUTHORED_BY", "MENTIONS", "CITES"):
        c = _count(lambda et=et: _ecount(et), f"getEdgeCount({et})")
        print(f"  getEdgeCount({et}) = {c}")

    print(f"\n[total] finished in {time.time() - t_start:.1f}s")


if __name__ == "__main__":
    sys.exit(main())