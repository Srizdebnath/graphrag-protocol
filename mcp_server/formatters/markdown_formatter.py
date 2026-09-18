"""Markdown formatter for SubgraphContext (Contract 8).

Produces readable Markdown with inline citations, ordered by relevance,
and a metadata footer.  Designed for human inspection and LLM consumption.
"""

from __future__ import annotations

from mcp_server.formatters.base import BaseFormatter
from mcp_server.protocol import Entity, Relationship, SubgraphContext


def _estimate_tokens(text: str) -> int:
    """Approximate token count without an external tokenizer."""
    return int(len(text.split()) * 1.3)


class MarkdownFormatter(BaseFormatter):
    """Serialize a SubgraphContext into Markdown for prompt injection."""

    # ------------------------------------------------------------------
    # Single-item formatters
    # ------------------------------------------------------------------

    def format_entity(self, entity: Entity) -> str:
        """Return a single-line Markdown bullet for *entity*."""
        display = entity.name or entity.id
        parts: list[str] = [f"- **{display}** ({entity.type})"]
        if entity.properties:
            brief = ", ".join(f"{k}={v}" for k, v in list(entity.properties.items())[:5])
            parts.append(f"  {brief}")
        if entity.source_chunks:
            refs = ", ".join(f"[Source: {c}]" for c in entity.source_chunks[:3])
            parts.append(f"  {refs}")
        return " ".join(parts)

    def format_relationship(self, relationship: Relationship) -> str:
        """Return a single-line Markdown description for *relationship*."""
        evidence_snippet = ""
        if relationship.evidence:
            ev = relationship.evidence[0]
            snippet = ev.get("snippet", "")
            chunk = ev.get("chunk_id", "")
            evidence_snippet = f' ("{snippet}" [Source: {chunk}])' if snippet else ""

        props = ""
        if relationship.properties:
            brief = ", ".join(
                f"{k}={v}" for k, v in list(relationship.properties.items())[:3]
            )
            props = f" ({brief})"

        return (
            f"- {relationship.source} --{relationship.type}--> {relationship.target} "
            f"(weight={relationship.weight:.2f}){props}{evidence_snippet}"
        )

    # ------------------------------------------------------------------
    # Full context formatter
    # ------------------------------------------------------------------

    def format_context(
        self,
        context: SubgraphContext,
        max_tokens: int = 4096,
    ) -> str:
        """Serialize *context* into Markdown bounded to *max_tokens* tokens."""
        lines: list[str] = []
        used = 0

        def _add(text: str) -> bool:
            nonlocal used
            t = _estimate_tokens(text)
            if used + t > max_tokens and lines:
                return False
            lines.append(text)
            used += t
            return True

        _add("## Retrieved Context\n")

        results = context.results

        # --- Entities (sorted by relevance_score desc) ---
        raw_entities: list[dict] = results.get("entities", [])  # type: ignore[assignment]
        entities = sorted(raw_entities, key=lambda e: e.get("relevance_score", 0), reverse=True)
        if entities:
            _add("\n### Entities\n")
            shown = 0
            truncated = 0
            budget_left = max_tokens - used
            for ent_dict in entities:
                ent = Entity(**ent_dict)
                line = self.format_entity(ent)
                t = _estimate_tokens(line)
                if budget_left - t < 20 and shown > 0:
                    truncated += len(entities) - shown
                    break
                if _add(line):
                    shown += 1
                    budget_left -= t
                else:
                    truncated += len(entities) - shown
                    break
            if truncated:
                _add(f"\n*…and {truncated} more entities (trimmed to fit token budget)*\n")

        # --- Relationships (sorted by weight desc) ---
        raw_rels: list[dict] = results.get("relationships", [])  # type: ignore[assignment]
        rels = sorted(raw_rels, key=lambda r: r.get("weight", 0), reverse=True)
        if rels:
            _add("\n### Relationships\n")
            shown = 0
            truncated = 0
            budget_left = max_tokens - used
            for rel_dict in rels:
                rel = Relationship(**rel_dict)
                line = self.format_relationship(rel)
                t = _estimate_tokens(line)
                if budget_left - t < 20 and shown > 0:
                    truncated += len(rels) - shown
                    break
                if _add(line):
                    shown += 1
                    budget_left -= t
                else:
                    truncated += len(rels) - shown
                    break
            if truncated:
                _add(f"\n*…and {truncated} more relationships (trimmed to fit token budget)*\n")

        # --- Paths ---
        paths: list[dict] = results.get("paths", [])  # type: ignore[assignment]
        if paths:
            _add("\n### Paths\n")
            for p in paths:
                path_entities = p.get("entities", [])
                summary = p.get("path_summary", "")
                _add(f"- {' → '.join(path_entities)}: {summary}\n")

        # --- Communities ---
        communities: list[dict] = results.get("communities", [])  # type: ignore[assignment]
        if communities:
            _add("\n### Communities\n")
            for c in communities:
                cid = c.get("id", "?")
                level = c.get("level", "?")
                member_count = c.get("member_count", 0)
                summary = c.get("summary", "")
                _add(f"- **{cid}** (level={level}, {member_count} members): {summary}\n")

        # --- Source Chunks ---
        chunks: list[dict] = results.get("text_chunks", [])  # type: ignore[assignment]
        if chunks:
            _add("\n### Source Chunks\n")
            shown = 0
            truncated = 0
            budget_left = max_tokens - used
            for chunk in chunks:
                chunk_id = chunk.get("id", "?")
                text = chunk.get("text", "")
                source = chunk.get("source_doc", "")
                rel_score = chunk.get("relevance_score", 0)
                line = f"- [{chunk_id}] ({source}, rel={rel_score:.2f}): {text}\n"
                t = _estimate_tokens(line)
                if budget_left - t < 20 and shown > 0:
                    truncated += len(chunks) - shown
                    break
                if _add(line):
                    shown += 1
                    budget_left -= t
                else:
                    truncated += len(chunks) - shown
                    break
            if truncated:
                _add(
                    f"\n*…and {truncated} more source chunks (trimmed to fit token budget)*\n"
                )

        # --- Footer with retrieval metadata ---
        prov = context.provenance
        m = context.metrics
        footer = (
            f"\n---\n*Retrieved via: {prov.backend} | {m.graph_hops_traversed} hops | "
            f"{m.entities_returned} entities, {m.relationships_returned} relationships | "
            f"{m.input_tokens} tokens*\n"
        )
        _add(footer)

        return "\n".join(lines)
