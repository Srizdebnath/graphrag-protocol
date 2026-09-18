"""Structured JSON formatter for SubgraphContext (Contract 8).

Produces compact, single-line-per-item JSON designed for programmatic /
agent consumption.  NOT pretty-printed to save tokens.
"""

from __future__ import annotations

import json
from typing import Any

from mcp_server.formatters.base import BaseFormatter
from mcp_server.protocol import Entity, Relationship, SubgraphContext


def _estimate_tokens(text: str) -> int:
    """Approximate token count without an external tokenizer."""
    return int(len(text.split()) * 1.3)


class StructuredFormatter(BaseFormatter):
    """Serialize a SubgraphContext into compact JSON for programmatic use."""

    # ------------------------------------------------------------------
    # Single-item formatters
    # ------------------------------------------------------------------

    def format_entity(self, entity: Entity) -> str:
        """Return a compact JSON string for a single *entity*."""
        obj: dict[str, Any] = {
            "id": entity.id,
            "type": entity.type,
            "name": entity.name,
            "rel": entity.relevance_score,
        }
        if entity.properties:
            obj["props"] = _truncate_props(entity.properties)
        if entity.source_chunks:
            obj["evidence"] = entity.source_chunks
        return json.dumps(obj, separators=(",", ":"))

    def format_relationship(self, relationship: Relationship) -> str:
        """Return a compact JSON string for a single *relationship*."""
        obj: dict[str, Any] = {
            "id": relationship.id,
            "src": relationship.source,
            "tgt": relationship.target,
            "type": relationship.type,
            "weight": relationship.weight,
        }
        if relationship.properties:
            obj["props"] = _truncate_props(relationship.properties)
        if relationship.evidence:
            obj["evidence"] = relationship.evidence
        return json.dumps(obj, separators=(",", ":"))

    # ------------------------------------------------------------------
    # Full context formatter
    # ------------------------------------------------------------------

    def format_context(
        self,
        context: SubgraphContext,
        max_tokens: int = 4096,
    ) -> str:
        """Serialize *context* into compact JSON bounded to *max_tokens*.

        The output is a single JSON object with keys ``entities``,
        ``relationships``, ``paths``, ``communities``, ``text_chunks``,
        and ``provenance``.  Entity and relationship lists are trimmed
        by importance to respect the token budget.
        """
        prov = context.provenance
        m = context.metrics
        results = context.results

        # Sort entities by relevance_score desc
        raw_entities: list[dict] = results.get("entities", [])  # type: ignore[assignment]
        sorted_entities = sorted(
            raw_entities, key=lambda e: e.get("relevance_score", 0), reverse=True
        )

        # Sort relationships by weight desc
        raw_rels: list[dict] = results.get("relationships", [])  # type: ignore[assignment]
        sorted_rels = sorted(raw_rels, key=lambda r: r.get("weight", 0), reverse=True)

        paths = results.get("paths", [])  # type: ignore[assignment]
        communities = results.get("communities", [])  # type: ignore[assignment]
        chunks = results.get("text_chunks", [])  # type: ignore[assignment]

        # Build progressively, respecting budget
        budget = max_tokens
        header_tokens = _estimate_tokens('{"entities":[')
        budget -= header_tokens

        included_entities = _trim_to_budget(sorted_entities, budget, _entity_tokens)
        budget -= sum(_entity_tokens(e) for e in included_entities)

        included_rels = _trim_to_budget(sorted_rels, budget, _rel_tokens)
        budget -= sum(_rel_tokens(r) for r in included_rels)

        # Convert dicts to compact JSON lines
        entity_lines = [_compact_entity(e) for e in included_entities]
        rel_lines = [_compact_rel(r) for r in included_rels]

        provenance_obj: dict[str, Any] = {
            "source_documents": prov.source_documents,
            "backend": prov.backend,
            "total_entities_examined": prov.total_entities_examined,
            "total_chunks_examined": prov.total_chunks_examined,
            "total_chunks_returned": prov.total_chunks_returned,
        }
        if prov.visited_not_cited:
            provenance_obj["visited_not_cited"] = prov.visited_not_cited

        out: dict[str, Any] = {
            "entities": entity_lines,
            "relationships": rel_lines,
            "paths": paths,
            "communities": communities,
            "text_chunks": chunks,
            "provenance": provenance_obj,
            "metrics": {
                "input_tokens": m.input_tokens,
                "entities_returned": m.entities_returned,
                "relationships_returned": m.relationships_returned,
                "graph_hops_traversed": m.graph_hops_traversed,
            },
        }

        return json.dumps(out, separators=(",", ":"))


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

MAX_PROP_CHARS = 120


def _truncate_props(props: dict[str, Any]) -> dict[str, Any]:
    """Truncate long property values to keep JSON compact."""
    out: dict[str, Any] = {}
    for k, v in props.items():
        s = str(v)
        out[k] = s if len(s) <= MAX_PROP_CHARS else s[:MAX_PROP_CHARS] + "…"
    return out


def _entity_tokens(ent: dict) -> int:
    """Rough token estimate for an entity dict."""
    name = ent.get("name", "")
    etype = ent.get("type", "")
    props = ent.get("properties", {})
    return _estimate_tokens(f"{name} {etype} {json.dumps(props)}")


def _rel_tokens(rel: dict) -> int:
    """Rough token estimate for a relationship dict."""
    rtype = rel.get("type", "")
    evidence = rel.get("evidence", [])
    ev_text = " ".join(str(e.get("snippet", "")) for e in evidence)
    return _estimate_tokens(f"{rtype} {ev_text}")


def _compact_entity(ent: dict) -> str:
    """Build a compact single-line JSON string for an entity."""
    obj: dict[str, Any] = {
        "id": ent["id"],
        "type": ent["type"],
        "name": ent.get("name", ""),
        "rel": ent.get("relevance_score", 0),
    }
    props = ent.get("properties", {})
    if props:
        obj["props"] = _truncate_props(props)
    chunks = ent.get("source_chunks", [])
    if chunks:
        obj["evidence"] = chunks
    return json.dumps(obj, separators=(",", ":"))


def _compact_rel(rel: dict) -> str:
    """Build a compact single-line JSON string for a relationship."""
    obj: dict[str, Any] = {
        "id": rel["id"],
        "src": rel["source"],
        "tgt": rel["target"],
        "type": rel["type"],
        "weight": rel.get("weight", 1.0),
    }
    props = rel.get("properties", {})
    if props:
        obj["props"] = _truncate_props(props)
    evidence = rel.get("evidence", [])
    if evidence:
        obj["evidence"] = evidence
    return json.dumps(obj, separators=(",", ":"))


def _trim_to_budget(
    items: list[dict],
    budget: int,
    token_fn: callable,  # type: ignore[valid-type]
) -> list[dict]:
    """Return the longest prefix of *items* whose total tokens fit *budget*."""
    included: list[dict] = []
    used = 0
    for item in items:
        t = token_fn(item)
        if used + t > budget:
            break
        included.append(item)
        used += t
    return included
