#!/usr/bin/env python3
"""Fetch arXiv AI/NLP papers via the public arXiv API and save as JSONL.

Usage:
    .venv/bin/python hackathon/scripts/download_papers.py --count 600
    .venv/bin/python hackathon/scripts/download_papers.py --count 1000 --categories cs.AI,cs.CL
"""

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import requests

ARXIV_API = "http://export.arxiv.org/api/query"
PAGE_SIZE = 100


def estimate_tokens(text: str) -> int:
    """Rough token estimate: word count * 1.4."""
    words = text.split()
    return int(len(words) * 1.4)


def extract_arxiv_id(entry) -> str:
    """Extract the arXiv id slug from an Atom entry."""
    raw = entry.get("id", "")
    # id looks like http://arxiv.org/abs/2401.12345v1
    match = re.search(r"abs/([^v]+)", raw)
    if match:
        return match.group(1)
    # fallback: last path segment
    parts = raw.rstrip("/").split("/")
    return parts[-1] if parts else raw


def parse_entry(entry) -> dict | None:
    """Parse a feedparser entry into our paper dict. Returns None to skip."""
    abstract = entry.get("summary", "").strip()
    if not abstract:
        return None

    arxiv_id = extract_arxiv_id(entry)
    title = re.sub(r"\s+", " ", entry.get("title", "")).strip()

    authors = [a.get("name", "") for a in entry.get("authors", [])]
    authors = [a for a in authors if a]  # drop blanks

    categories = []
    for cat in entry.get("tags", []):
        term = cat.get("term", "")
        if term:
            categories.append(term)

    published = ""
    if hasattr(entry, "published"):
        published = entry.published
    updated = ""
    if hasattr(entry, "updated"):
        updated = entry.updated

    doi = ""
    for link in entry.get("links", []):
        if link.get("type") == "application/pdf":
            pass
    # feedparser doesn't always expose DOI directly; look in arxiv_doi or dc namespace
    doi_raw = getattr(entry, "arxiv_doi", None) or ""
    if doi_raw:
        doi = doi_raw

    abstract_tokens = estimate_tokens(abstract)

    return {
        "id": arxiv_id,
        "title": title,
        "authors": authors,
        "abstract": abstract,
        "categories": categories,
        "published": published,
        "updated": updated,
        "doi": doi,
        "abstract_token_count": abstract_tokens,
    }


def build_search_query(categories: list[str]) -> str:
    cat_parts = [f"cat:{c}" for c in categories]
    return " OR ".join(cat_parts)


def fetch_page(search_query: str, start: int, max_results: int = PAGE_SIZE, retries: int = 3) -> list:
    """Fetch one page from the arXiv API. Returns list of parsed papers."""
    params = {
        "search_query": search_query,
        "start": start,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }

    for attempt in range(retries):
        try:
            resp = requests.get(ARXIV_API, params=params, timeout=60)
            if resp.status_code == 503:
                wait = 5 * (attempt + 1)
                print(f"  [WARN] 503 from arXiv, retrying in {wait}s (attempt {attempt+1}/{retries})...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
        except requests.RequestException as e:
            if attempt < retries - 1:
                time.sleep(3 * (attempt + 1))
                continue
            print(f"  [ERROR] Network request failed: {e}")
            raise

        feed = feedparser.parse(resp.text)
        papers = []
        for entry in feed.entries:
            paper = parse_entry(entry)
            if paper:
                papers.append(paper)
        return papers

    return []


def main():
    parser = argparse.ArgumentParser(description="Fetch arXiv papers")
    parser.add_argument("--count", type=int, default=600, help="Number of papers to fetch")
    parser.add_argument("--categories", type=str, default="cs.AI,cs.CL,cs.LG",
                        help="Comma-separated arXiv categories")
    parser.add_argument("--out", type=str, default="hackathon/data/papers/papers.jsonl",
                        help="Output JSONL path")
    parser.add_argument("--min-tokens", type=int, default=None,
                        help="Minimum abstract token count to keep")
    args = parser.parse_args()

    categories = [c.strip() for c in args.categories.split(",")]
    search_query = build_search_query(categories)
    print("=== arXiv Paper Fetcher ===")
    print(f"Categories: {categories}")
    print(f"Search query: {search_query}")
    print(f"Target count: {args.count}")
    print(f"Output: {args.out}")
    print()

    all_papers: dict[str, dict] = {}  # keyed by id for dedup
    failures: list[str] = []
    total_pages = (args.count + PAGE_SIZE - 1) // PAGE_SIZE

    for page_idx in range(total_pages):
        start = page_idx * PAGE_SIZE
        remaining = args.count - len(all_papers)
        if remaining <= 0:
            break

        print(f"Page {page_idx + 1}/{total_pages} (start={start}, fetched so far: {len(all_papers)})")
        try:
            papers = fetch_page(search_query, start, min(PAGE_SIZE, remaining))
        except Exception as e:  # noqa: BLE001 - keep batch going on ANY fetch failure
            msg = f"Page {page_idx + 1} failed: {e}"
            print(f"  [ERROR] {msg}")
            failures.append(msg)
            break

        if not papers:
            print("  No papers returned, stopping.")
            break

        new_count = 0
        for p in papers:
            pid = p["id"]
            if pid not in all_papers:
                all_papers[pid] = p
                new_count += 1
        print(f"  Got {len(papers)} papers, {new_count} new (deduped: {len(papers) - new_count})")

        # arXiv rate-limit: be polite but don't over-sleep
        if page_idx < total_pages - 1:
            time.sleep(1)

    # Filter by min_tokens
    if args.min_tokens is not None:
        before = len(all_papers)
        all_papers = {k: v for k, v in all_papers.items() if v["abstract_token_count"] >= args.min_tokens}
        print(f"Filtered by --min-tokens={args.min_tokens}: {before} -> {len(all_papers)} papers")

    # Write JSONL
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        f.writelines(json.dumps(paper, ensure_ascii=False) + "\n" for paper in all_papers.values())

    # Category breakdown
    cat_breakdown: dict[str, int] = {}
    total_tokens = 0
    for p in all_papers.values():
        total_tokens += p["abstract_token_count"]
        for c in p["categories"]:
            cat_breakdown[c] = cat_breakdown.get(c, 0) + 1

    stats = {
        "total_papers": len(all_papers),
        "total_abstract_tokens": total_tokens,
        "category_breakdown": cat_breakdown,
        "fetch_date": datetime.now(timezone.utc).isoformat(),
    }
    stats_path = out_path.parent / "stats.json"
    with open(stats_path, "w") as f:
        json.dump(stats, f, indent=2)

    print()
    print("=== Summary ===")
    print(f"Papers fetched:   {args.count} requested")
    print(f"Papers saved:     {len(all_papers)} (deduped by id)")
    print(f"Total abstract tokens: {total_tokens}")
    print(f"Category breakdown: {cat_breakdown}")
    print(f"Failures: {len(failures)}")
    for fm in failures:
        print(f"  - {fm}")
    print(f"Output: {out_path}")
    print(f"Stats:  {stats_path}")


if __name__ == "__main__":
    main()
