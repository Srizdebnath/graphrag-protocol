# Benchmark Dataset

This directory contains the benchmark queries and reference answers used by the GraphRAG protocol evaluation harness. All queries are **grounded in the real arXiv paper data** stored in `../papers/papers.jsonl`.

## Corpus

The corpus consists of **8,000 arXiv papers** fetched from the public arXiv API across AI/NLP categories (cs.AI, cs.CL, cs.LG, cs.CV, and related).

| Metric | Value |
|--------|-------|
| Total papers | 8,000 |
| Total abstract tokens | ~2.15M |
| Primary categories | cs.AI (4503), cs.LG (3623), cs.CL (2199), cs.CV (994) |
| Fetch date | 2026-09-08 |

Each paper record contains: `id` (arXiv ID), `title`, `authors`, `abstract`, `categories`, `published`, `updated`, `doi`, and `abstract_token_count`.

## Query Categories

### single_hop.json (15 queries, q001–q015)
Facts verifiable from a **single paper abstract** — e.g., paper title, author list, task description, or method. Each query has a `papers` field listing 1 relevant arXiv ID.

### multi_hop.json (15 queries, q016–q030)
Queries requiring **2–3 hop reasoning** that link multiple real papers via shared topics, methods, or applications. The `papers` field lists 2–3 relevant arXiv IDs connected by semantic concepts.

### global.json (10 queries, q031–q040)
**Corpus-wide synthesis** questions about dominant themes, most common methods, popular categories, and cross-category intersections. These have an empty `papers` list because they require reasoning across the entire corpus, not individual papers.

### comparison.json (10 queries, q041–q050)
**Pairwise comparison** queries about how two real papers approach overlapping topics using different methods or targeting different applications. Each query's `papers` field lists the 2 arXiv IDs to compare.

### reference_answers.json (50 answers)
Dictionary mapping each query ID (q001–q050) to a **1–3 sentence reference answer**. Answers are grounded **only** in what the actual paper abstracts state. Global answers are grounded in computed term/category frequencies from the real corpus.

## ID Convention

- All queries use IDs `q001` through `q050`, unique across all query files.
- IDs are zero-padded to 3 digits.
- Category ranges: single_hop = q001–q015, multi_hop = q016–q030, global = q031–q040, comparison = q041–q050.
- `papers` entries are arXiv IDs that must exist in `papers.jsonl` (validated at generation time).

## Regenerating

To regenerate the paper corpus:

```bash
python hackathon/scripts/download_papers.py --count 8000 --categories cs.AI,cs.CL,cs.LG
```

To regenerate the query files from the current corpus:

```bash
python hackathon/scripts/build_queries.py
```

The query builder loads `papers.jsonl` and validates that every paper ID referenced in the queries actually exists in the corpus before writing the output files.
