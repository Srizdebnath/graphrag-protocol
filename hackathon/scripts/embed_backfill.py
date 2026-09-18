"""Backfill embeddings for papers missing a PaperEmb vector.

Only embeds the papers whose id is not already present as a PaperEmb vertex,
so it is cheap to run and idempotent. Uses batched gemini embedding with
rate-limit backoff, then upserts into the PaperEmb vertex.

Usage:
    python hackathon/scripts/embed_backfill.py [--limit 8000] [--batch 100]
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = PROJECT_ROOT / "hackathon" / "data" / "papers" / "papers.jsonl"
load_dotenv(PROJECT_ROOT / ".env")

EMBED_DIM = 512
GRAPH = "GraphragProtocol"


def connect():
    from pyTigerGraph import TigerGraphConnection

    return TigerGraphConnection(
        host=os.environ["TIGERGRAPH_HOST"],
        graphname=os.environ["TIGERGRAPH_GRAPH_NAME"],
        gsqlSecret=os.environ["TIGERGRAPH_GSQL_SECRET"],
        tgCloud=True,
    )


def existing_embedded_ids(conn) -> set[str]:
    """Collect PaperEmb ids via a GSQL query (authoritative, not stats-lagging)."""
    q = f"""USE GRAPH {GRAPH}
CREATE OR REPLACE QUERY ListEmbIds() FOR GRAPH {GRAPH} SYNTAX v3 {{
  ListAccum<STRING> @@ids;
  Start = {{PaperEmb.*}};
  R = SELECT pe FROM Start:pe ACCUM @@ids += pe.id;
  PRINT @@ids;
}}
INSTALL QUERY ListEmbIds
"""
    conn.gsql(q)
    res = conn.runInstalledQuery("ListEmbIds", {})
    for item in res:
        if "@@ids" in item:
            return set(item["@@ids"])
    return set()


def embed_with_backoff(client, model, texts, dim):
    from google import genai

    cfg = genai.types.EmbedContentConfig(output_dimensionality=dim, task_type="RETRIEVAL_DOCUMENT")
    attempt = 0
    while True:
        try:
            resp = client.models.embed_content(model=model, contents=texts, config=cfg)
            out = []
            for e in resp.embeddings:
                vals = getattr(e, "values", None)
                if vals is None:
                    vals = getattr(e, "embedding", [])
                out.append([float(x) for x in vals])
            return out
        except Exception as e:
            attempt += 1
            msg = str(e)
            retriable = (
                "429" in msg
                or "RESOURCE_EXHAUSTED" in msg
                or " 500" in msg
                or "503" in msg
                or "SSL" in msg
                or "UNEXPECTED_EOF" in msg
                or "Connection" in msg
                or "ReadTimeout" in msg
                or "ConnectTimeout" in msg
            )
            if attempt > 12 or not retriable:
                raise
            backoff = min(90, 2 ** attempt + (attempt * 4))
            print(f"  !! embed backoff {msg[:90]}... retry {attempt} in {backoff}s", flush=True)
            time.sleep(backoff)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=8000)
    ap.add_argument("--batch", type=int, default=100)
    ap.add_argument("--data", default=str(DATA_PATH))
    ap.add_argument("--embed-model", default=os.environ.get("TIGERGRAPH_EMBED_MODEL", "gemini-embedding-001"))
    args = ap.parse_args()

    t0 = time.time()
    conn = connect()

    papers: list[dict] = []
    with open(args.data, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            papers.append(json.loads(line))
            if len(papers) >= args.limit:
                break
    print(f"[data] {len(papers)} papers", flush=True)

    have = existing_embedded_ids(conn)
    print(f"[data] {len(have)} already embedded; need {len(papers) - len(have)}", flush=True)

    need = [p for p in papers if p["id"] not in have]
    if not need:
        print("[done] nothing to embed", flush=True)
        return

    from google import genai

    key = os.environ.get("GOOGLE_API_KEY")
    if not key:
        print("[embed] GOOGLE_API_KEY missing; aborting", flush=True)
        return
    client = genai.Client(api_key=key)

    upserted = 0
    for i in range(0, len(need), args.batch):
        chunk = need[i : i + args.batch]
        texts = [f"{p['title']}\n{p['abstract']}"[:8000] for p in chunk]
        embs = embed_with_backoff(client, args.embed_model, texts, EMBED_DIM)
        items = [(p["id"], {"abstract_embedding": v}) for p, v in zip(chunk, embs, strict=True)]
        try:
            upserted += conn.upsertVertices("PaperEmb", items, atomic=False)
        except Exception as e:  # noqa: BLE001
            print(f"  !! upsert batch {i // args.batch} failed: {type(e).__name__}: {e}", flush=True)
        print(f"  embedded+upserted {min(i + args.batch, len(need))}/{len(need)}", flush=True)

    print(f"[done] upserted {upserted} PaperEmb in {time.time() - t0:.1f}s", flush=True)
    time.sleep(5)
    print(f"[verify] PaperEmb count = {conn.getVertexCount('PaperEmb')}", flush=True)


if __name__ == "__main__":
    main()
