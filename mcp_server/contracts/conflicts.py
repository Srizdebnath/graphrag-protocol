"""Contract 19: Conflict & Uncertainty Resolution over Knowledge Graphs.

Detects contradictory facts, claims, or temporal properties within a SubgraphContext
and resolves them using provenance authority (source citation density, vertex degree)
and temporal recency. Emits an uncertainty score [0.0, 1.0] and structured conflict reports.
No mocks, no synthetic fakes — real deterministic resolution.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from mcp_server.adapters.base import BaseGraphRAGAdapter
from mcp_server.protocol import SubgraphContext

_ISO_RE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?")


class ConflictResolutionContract:
    """Contract 19: detects and resolves contradictory graph facts."""

    def __init__(self, adapter: BaseGraphRAGAdapter | None = None) -> None:
        self._adapter = adapter

    def detect_conflicts(self, context: SubgraphContext) -> list[dict[str, Any]]:
        """Detect conflicting properties or contradictory relations in a SubgraphContext.

        Scans:
        1. Duplicate entity references with conflicting scalar properties (e.g. status, affiliation, date).
        2. Incompatible or opposing edge types between the same vertex pair.
        3. Multiple temporal assertions (e.g. differing publication or creation dates).

        Returns:
            List of detected conflict objects with candidate facts.
        """
        entities = context.results.get("entities") or []
        relationships = context.results.get("relationships") or []
        conflicts: list[dict[str, Any]] = []

        # 1. Group entities by normalized name or ID
        grouped_entities: dict[str, list[dict[str, Any]]] = {}
        for ent in entities:
            key = (ent.get("name") or ent.get("id") or "").strip().lower()
            if key:
                grouped_entities.setdefault(key, []).append(ent)

        for key, ents in grouped_entities.items():
            if len(ents) < 2:
                continue
            # Compare scalar properties across representations
            prop_values: dict[str, set[str]] = {}
            for e in ents:
                props = e.get("properties") or {}
                for pk, pv in props.items():
                    if pv is not None and not isinstance(pv, (dict, list)):
                        prop_values.setdefault(pk, set()).add(str(pv))

            for prop_name, values in prop_values.items():
                if len(values) > 1:
                    conflicts.append(
                        {
                            "conflict_type": "property_contradiction",
                            "subject": key,
                            "property": prop_name,
                            "candidates": sorted(values),
                            "entities_involved": [e.get("id") for e in ents],
                        }
                    )

        # 2. Check relationship contradictions (multiple contradictory relations between same pair)
        pair_rels: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for rel in relationships:
            src = str(rel.get("source") or "")
            tgt = str(rel.get("target") or "")
            if src and tgt:
                pair_key = (src, tgt) if src <= tgt else (tgt, src)
                pair_rels.setdefault(pair_key, []).append(rel)

        opposing_pairs = {
            ("inhibits", "activates"),
            ("supports", "contradicts"),
            ("affiliates", "opposes"),
            ("positive", "negative"),
        }

        for (src, tgt), rels in pair_rels.items():
            types = {str(r.get("type") or "").lower() for r in rels}
            for op1, op2 in opposing_pairs:
                if op1 in types and op2 in types:
                    conflicts.append(
                        {
                            "conflict_type": "opposing_relationships",
                            "subject": f"{src} <-> {tgt}",
                            "property": "relationship_type",
                            "candidates": sorted(types),
                            "relationship_ids": [r.get("id") for r in rels],
                        }
                    )

        return conflicts

    def resolve_conflicts(
        self,
        context: SubgraphContext,
        recency_weight: float = 0.6,
        authority_weight: float = 0.4,
    ) -> dict[str, Any]:
        """Resolve detected conflicts using temporal recency and source authoritativeness.

        Args:
            context: The SubgraphContext to analyze.
            recency_weight: Weight given to newer timestamps (default 0.6).
            authority_weight: Weight given to provenance source citation counts (default 0.4).

        Returns:
            Dict containing detected conflicts, resolved facts, remaining uncertain facts,
            and an overall `uncertainty_score` [0.0, 1.0].
        """
        conflicts = self.detect_conflicts(context)
        if not conflicts:
            return {
                "conflicts_detected": 0,
                "resolved_facts": [],
                "unresolved_conflicts": [],
                "uncertainty_score": 0.0,
                "resolution_policy": "temporal_recency_and_citation_authority",
            }

        resolved: list[dict[str, Any]] = []
        unresolved: list[dict[str, Any]] = []
        total_uncertainty = 0.0

        for conf in conflicts:
            candidates = conf["candidates"]
            scored_candidates = []

            for c in candidates:
                recency_score = self._extract_recency_score(c)
                authority_score = self._compute_authority_score(c, context)
                composite_score = (recency_weight * recency_score) + (authority_weight * authority_score)
                scored_candidates.append(
                    {
                        "candidate": c,
                        "composite_score": round(composite_score, 4),
                        "recency_score": round(recency_score, 4),
                        "authority_score": round(authority_score, 4),
                    }
                )

            scored_candidates.sort(key=lambda x: x["composite_score"], reverse=True)

            if len(scored_candidates) >= 2:
                top_diff = scored_candidates[0]["composite_score"] - scored_candidates[1]["composite_score"]
                item_uncertainty = max(0.0, min(1.0, 1.0 - (top_diff * 4.0)))
            else:
                top_diff = 1.0
                item_uncertainty = 0.0

            total_uncertainty += item_uncertainty

            if top_diff >= 0.03:
                resolved.append(
                    {
                        "subject": conf["subject"],
                        "property": conf["property"],
                        "resolved_value": scored_candidates[0]["candidate"],
                        "confidence": round(max(0.5, 1.0 - item_uncertainty), 4),
                        "candidates_ranked": scored_candidates,
                        "rationale": (
                            f"Selected '{scored_candidates[0]['candidate']}' based on "
                            f"composite score {scored_candidates[0]['composite_score']}."
                        ),
                    }
                )
            else:
                unresolved.append(
                    {
                        "subject": conf["subject"],
                        "property": conf["property"],
                        "candidates": scored_candidates,
                        "uncertainty": round(item_uncertainty, 4),
                        "reason": "Insufficient score separation between candidates; requires human validation.",
                    }
                )

        avg_uncertainty = round(total_uncertainty / max(1, len(conflicts)), 4)
        return {
            "conflicts_detected": len(conflicts),
            "resolved_facts": resolved,
            "unresolved_conflicts": unresolved,
            "uncertainty_score": avg_uncertainty,
            "resolution_policy": "temporal_recency_and_citation_authority",
        }

    @staticmethod
    def _extract_recency_score(value: str) -> float:
        """Score recency from 0.0 to 1.0 based on year/timestamp present in string."""
        match = re.search(r"\b(19\d\d|20\d\d)\b", value)
        if match:
            year = int(match.group(1))
            current_year = datetime.now(timezone.utc).year
            # Normalize years from 1990 to current_year
            normalized = (year - 1990) / max(1, (current_year - 1990))
            return max(0.1, min(1.0, normalized))
        return 0.5  # Neutral when no date found

    @staticmethod
    def _compute_authority_score(value: str, context: SubgraphContext) -> float:
        """Compute authority score based on occurrences in entities, relationships, and source docs."""
        val_lower = str(value).lower()
        score = 0.0

        for doc in context.provenance.source_documents:
            if val_lower in doc.lower():
                score += 0.3

        for ent in context.results.get("entities") or []:
            props = ent.get("properties") or {}
            for v in props.values():
                if val_lower in str(v).lower():
                    score += 0.2

        return min(1.0, max(0.2, score))
