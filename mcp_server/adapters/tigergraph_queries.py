"""GSQL query definitions for the TigerGraph adapter.

All queries are installed idempotently (``CREATE OR REPLACE``) into the
TigerGraph workspace and executed via ``TigerGraphConnection.runInstalledQuery``.

Result conventions
------------------
Vertex objects are returned by converting accumulator sets back into
vertex-set variables before ``PRINT``, which makes TigerGraph emit the full
``{"v_id", "v_type", "attributes"}`` shape (accumulator-only ``PRINT`` yields
bare id strings).  Edges are collected into ``SetAccum<EDGE>`` and printed as
edge objects.  Scalar aggregates (relevance, distances, counts) are printed
as JSON maps keyed by vertex id.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Query names
# ---------------------------------------------------------------------------

TG_NEIGHBORHOOD = "tg_neighborhood"
TG_LOCAL_SEARCH = "tg_local_search"
TG_ENTITY_LOOKUP = "tg_entity_lookup"
TG_TOP_CONCEPTS = "tg_top_concepts"
TG_CONCEPT_MEMBERS = "tg_concept_members"
TG_VECTOR_SEARCH = "tg_vector_search"

QUERY_NAMES = frozenset(
    {
        TG_NEIGHBORHOOD,
        TG_LOCAL_SEARCH,
        TG_ENTITY_LOOKUP,
        TG_TOP_CONCEPTS,
        TG_CONCEPT_MEMBERS,
        TG_VECTOR_SEARCH,
    }
)

# ---------------------------------------------------------------------------
# GSQL bodies
# ---------------------------------------------------------------------------

# Breadth-first expansion around a single seed vertex.
# seed_id/seed_type identify the seed; depth bounds hops; top_k unused in
# GSQL (bounded client-side) so expansion is always BFS-complete.
TG_NEIGHBORHOOD_GSQL = """
CREATE OR REPLACE QUERY tg_neighborhood(STRING seed_id, STRING seed_type, INT depth, INT top_k)
SYNTAX v3
{
    SetAccum<VERTEX> @@entities;
    SetAccum<EDGE>   @@relationships;
    SetAccum<VERTEX> @@seed;
    OrAccum @visited;

    Seed = {};
    IF seed_type == "Paper" THEN
        Start = {Paper.*};
        Seed = SELECT s FROM Start:s WHERE s.id == seed_id
               POST-ACCUM @@seed += s, @@entities += s, s.@visited += TRUE;
    ELSE IF seed_type == "Author" THEN
        Start = {Author.*};
        Seed = SELECT s FROM Start:s WHERE s.name == seed_id
               POST-ACCUM @@seed += s, @@entities += s, s.@visited += TRUE;
    ELSE IF seed_type == "Concept" THEN
        Start = {Concept.*};
        Seed = SELECT s FROM Start:s WHERE s.name == seed_id
               POST-ACCUM @@seed += s, @@entities += s, s.@visited += TRUE;
    END;

    INT hops = 0;
    WHILE Seed.size() > 0 AND hops < depth
    DO
        Seed = SELECT t
               FROM Seed:s -[e]- (t)
               WHERE NOT t.@visited
               ACCUM @@relationships += e
               POST-ACCUM t.@visited += TRUE, @@entities += t;
        hops = hops + 1;
    END;

    AnsSeed = @@seed;
    Ans     = @@entities;
    FullSeed = SELECT s FROM AnsSeed:s;
    Full     = SELECT v FROM Ans:v;

    PRINT FullSeed AS seed;
    PRINT Full     AS entities;
    PRINT @@relationships AS relationships;
    PRINT hops      AS hops;
}
"""

# Keyword-seeded local search: match Paper.title/abstract against query
# terms (LIKE, case-insensitive). A single OR-pass over all terms keeps the
# full-text scan to one pass per paper, and a procedural budget-break bounds
# the BFS when a generic query matches too many seeds.
TG_LOCAL_SEARCH_GSQL = """
CREATE OR REPLACE QUERY tg_local_search(
    SET<STRING> terms,
    STRING      query_text,
    INT         depth,
    INT         top_k
)
SYNTAX v3
{
    SetAccum<VERTEX>  @@seed;
    SetAccum<VERTEX>  @@entities;
    SetAccum<EDGE>    @@relationships;
    OrAccum            @visited;
    MapAccum<VERTEX, SumAccum<INT>> @@relevance;

    P = {Paper.*};
    FOREACH term IN terms DO
        Hits = SELECT p FROM P:p
               WHERE LOWER(p.title) LIKE "%" + LOWER(term) + "%"
               ACCUM @@relevance += (p -> 1)
               POST-ACCUM IF NOT p.@visited THEN
                            p.@visited += TRUE,
                            @@seed += p,
                            @@entities += p
                          END;
    END;

    // Abstract scan only when title matches are too thin for top_k: the
    // full-text pass over every abstract is the expensive part, so avoid it
    // when the (cheap) title scan already found enough seeds.
    IF @@seed.size() < top_k THEN
        FOREACH term IN terms DO
            Hits = SELECT p FROM P:p
                   WHERE NOT p.@visited
                     AND LOWER(p.abstract) LIKE "%" + LOWER(term) + "%"
                   ACCUM @@relevance += (p -> 1)
                   POST-ACCUM IF NOT p.@visited THEN
                                p.@visited += TRUE,
                                @@seed += p,
                                @@entities += p
                              END;
        END;
    END;

    Seed = @@seed;
    INT hops = 0;
    // Bound the BFS: generic queries can match hundreds/thousands of seeds,
    // whose hop-2 frontier can cover the entire graph.  Stop expanding once
    // the entity budget is consumed; specific queries sail through untouched.
    INT budget = top_k * 500;
    WHILE Seed.size() > 0 AND hops < depth
    DO
        IF @@entities.size() >= budget THEN BREAK; END;
        Seed = SELECT t
               FROM Seed:s -[e]- (t)
               WHERE NOT t.@visited
               ACCUM @@relationships += e
               POST-ACCUM t.@visited += TRUE, @@entities += t;
        hops = hops + 1;
    END;

    AnsSeed = @@seed;
    Ans     = @@entities;
    FullSeed = SELECT s FROM AnsSeed:s;
    Full     = SELECT v FROM Ans:v;

    PRINT FullSeed AS seed;
    PRINT Full     AS entities;
    PRINT @@relationships AS relationships;
    PRINT @@relevance AS relevance;
    PRINT hops AS hops;
}
"""

# Single-vertex lookup, then BFS expansion (semantically identical to the
# neighborhood query but semantically framed as entity lookup).
TG_ENTITY_LOOKUP_GSQL = """
CREATE OR REPLACE QUERY tg_entity_lookup(STRING entity_id, STRING entity_type, INT depth, INT top_k)
SYNTAX v3
{
    SetAccum<VERTEX> @@entities;
    SetAccum<EDGE>   @@relationships;
    SetAccum<VERTEX> @@seed;
    OrAccum @visited;

    Seed = {};
    IF entity_type == "Paper" THEN
        Start = {Paper.*};
        Seed = SELECT s FROM Start:s WHERE s.id == entity_id
               POST-ACCUM @@seed += s, @@entities += s, s.@visited += TRUE;
    ELSE IF entity_type == "Author" THEN
        Start = {Author.*};
        Seed = SELECT s FROM Start:s WHERE s.name == entity_id
               POST-ACCUM @@seed += s, @@entities += s, s.@visited += TRUE;
    ELSE IF entity_type == "Concept" THEN
        Start = {Concept.*};
        Seed = SELECT s FROM Start:s WHERE s.name == entity_id
               POST-ACCUM @@seed += s, @@entities += s, s.@visited += TRUE;
    END;

    INT hops = 0;
    WHILE Seed.size() > 0 AND hops < depth
    DO
        Seed = SELECT t
               FROM Seed:s -[e]- (t)
               WHERE NOT t.@visited
               ACCUM @@relationships += e
               POST-ACCUM t.@visited += TRUE, @@entities += t;
        hops = hops + 1;
    END;

    AnsSeed = @@seed;
    Ans     = @@entities;
    FullSeed = SELECT s FROM AnsSeed:s;
    Full     = SELECT v FROM Ans:v;

    PRINT FullSeed AS seed;
    PRINT Full     AS entities;
    PRINT @@relationships AS relationships;
    PRINT hops      AS hops;
}
"""

# Global: top concepts by number of papers that mention them.
# Traverses MENTIONS in reverse direction (Concept <- Paper) using the
# direction-agnostic edge pattern.
TG_TOP_CONCEPTS_GSQL = """
CREATE OR REPLACE QUERY tg_top_concepts(INT top_k)
SYNTAX v3
{
    MapAccum<VERTEX, SumAccum<INT>> @@count;

    Concepts = {Concept.*};
    C = SELECT c
        FROM Concept:c -[e:MENTIONS]- (p:Paper)
        ACCUM @@count += (c -> 1);

    PRINT @@count AS concept_counts;
}
"""

# Community: papers mentioning a concept (exact name or LIKE prefix), plus
# the matched concept vertices.
TG_CONCEPT_MEMBERS_GSQL = """
CREATE OR REPLACE QUERY tg_concept_members(STRING concept_name, INT top_k)
SYNTAX v3
{
    SetAccum<VERTEX> @@papers;
    SetAccum<VERTEX> @@concepts;

    Concepts = {Concept.*};
    Matched = SELECT c FROM Concepts:c
              WHERE c.name == concept_name OR c.name LIKE "%" + concept_name + "%"
              POST-ACCUM @@concepts += c;

    P = SELECT p FROM Matched:c -[e:MENTIONS]- (p:Paper)
        ACCUM @@papers += p;

    AnsP = @@papers;
    AnsC = @@concepts;

    PRINT @@concepts AS concepts;
    PRINT @@papers   AS papers;
}
"""

# Vector similarity search over PaperEmb.abstract_embedding (512-dim
# COSINE HNSW index).  Returns nearest PaperEmb vertices plus a distance
# map keyed by paper id.
TG_VECTOR_SEARCH_GSQL = """
CREATE OR REPLACE QUERY tg_vector_search(
    LIST<FLOAT> query_embedding,
    INT          top_k
)
SYNTAX v3
{
    MapAccum<VERTEX, FLOAT> @@distances;

    Matches = vectorSearch(
        {PaperEmb.abstract_embedding},
        query_embedding,
        top_k,
        { distance_map: @@distances }
    );

    PRINT Matches AS matches;
    PRINT @@distances AS distances;
}
"""

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ALL_QUERIES: dict[str, str] = {
    TG_NEIGHBORHOOD: TG_NEIGHBORHOOD_GSQL,
    TG_LOCAL_SEARCH: TG_LOCAL_SEARCH_GSQL,
    TG_ENTITY_LOOKUP: TG_ENTITY_LOOKUP_GSQL,
    TG_TOP_CONCEPTS: TG_TOP_CONCEPTS_GSQL,
    TG_CONCEPT_MEMBERS: TG_CONCEPT_MEMBERS_GSQL,
    TG_VECTOR_SEARCH: TG_VECTOR_SEARCH_GSQL,
}

# Minimum vertex counts below which a query backed by that vertex type is
# considered "not yet ready" and skipped (e.g. PaperEmb before embeddings
# are loaded).
MIN_READY_COUNTS: dict[str, int] = {
    "Paper": 1,
    "Author": 1,
    "Concept": 1,
    "PaperEmb": 1,
}