"""Contract 13: Explanation — explain why each entity was retrieved.

Builds a deterministic, traversal-log-driven narrative for each entity in a
SubgraphContext. When a Gemini client is available (GOOGLE_API_KEY), it polishes
the raw narrative into natural language. Without one, the deterministic version is
returned — always a real explanation, never fabricated.
"""
from __future__ import annotations

import os
from typing import Any

from mcp_server.adapters.base import BaseGraphRAGAdapter
from mcp_server.protocol import SubgraphContext, TraversalStep


class ExplanationContract:
    """Contract 13: per-entity explanations of retrieval decisions.

    Args:
        adapter: The backend adapter.
        llm_client: Optional pre-built Gemini client. Built lazily from
            GOOGLE_API_KEY when omitted.
    """

    def __init__(self, adapter: BaseGraphRAGAdapter, llm_client: Any | None = None) -> None:
        if adapter is None:
            raise ValueError("ExplanationContract requires a non-None adapter")
        self._adapter = adapter
        self._llm_client = llm_client
        self._llm_resolved = llm_client is not None

    def explain(self, context: SubgraphContext, max_entities: int = 10) -> dict[str, Any]:
        """Generate explanations for why each entity was retrieved.

        Builds a deterministic explanation from the traversal log and provenance.
        If an LLM is available, polishes the raw explanation with a brief sentence.

        Args:
            context: The SubgraphContext to explain.
            max_entities: Maximum number of entities to explain.

        Returns:
            Dict with `query`, `operation`, `explanations` (list of per-entity dicts),
            `traversal_summary` (string), and `method` ('llm' or 'deterministic').
        """
        if context is None:
            raise ValueError("explain requires a SubgraphContext")
        entities = (context.results.get("entities") or [])[:max(1, max_entities)]
        traversal = context.provenance.traversal_log or []
        step_map = {step.entity: step for step in traversal}

        explanations = []
        for ent in entities:
            eid = str(ent.get("id") or "")
            name = str(ent.get("name") or eid)
            etype = str(ent.get("type") or "entity")
            score = float(ent.get("relevance_score") or 0.0)
            step = step_map.get(eid)
            raw_reason = self._deterministic_reason(eid, name, etype, score, step, context)
            explanations.append({
                "entity_id": eid,
                "entity_name": name,
                "entity_type": etype,
                "relevance_score": score,
                "traversal_step": step.step if step else None,
                "traversal_action": step.action if step else "unknown",
                "reason": raw_reason,
            })

        summary = self._traversal_summary(context)
        method = "deterministic"

        # Try LLM polish
        client = self._llm()
        if client and explanations:
            try:
                entity_lines = "\n".join(f"- {e['entity_name']} ({e['entity_type']}): {e['reason']}" for e in explanations[:5])
                prompt = (
                    f"The following entities were retrieved for the query '{context.query}'.\n"
                    f"Explain in 2-3 plain-English sentences why these entities are relevant.\n\n"
                    f"{entity_lines}"
                )
                resp = client.models.generate_content(
                    model=os.environ.get("LLM_MODEL", "gemini-2.5-flash"),
                    contents=prompt,
                )
                summary = (resp.text or summary).strip()
                method = "llm"
            except Exception:  # noqa: BLE001, S110 - LLM polish is optional
                pass

        return {
            "query": context.query,
            "operation": context.operation,
            "traversal_summary": summary,
            "explanations": explanations,
            "method": method,
            "total_entities_explained": len(explanations),
        }

    def explain_path(self, context: SubgraphContext) -> dict[str, Any]:
        """Explain the reasoning behind each path found in a path_search result.

        Args:
            context: The SubgraphContext from a path_search operation.

        Returns:
            Dict with `paths` (list of dicts with `path_entities`, `hops`, `narrative`).
        """
        paths = context.results.get("paths") or []
        entity_map = {e["id"]: e for e in (context.results.get("entities") or [])}
        explained = []
        for path in paths:
            nodes = path.get("entities") or []
            names = [entity_map.get(n, {}).get("name", n) for n in nodes]
            narrative = " → ".join(names)
            if len(nodes) >= 2:
                narrative = f"{names[0]} connects to {names[-1]} via {len(nodes) - 2} intermediate node(s): {narrative}"
            explained.append({
                "path_entities": nodes,
                "entity_names": names,
                "hops": len(nodes) - 1 if len(nodes) > 1 else 0,
                "narrative": narrative,
                "path_summary": path.get("path_summary", narrative),
            })
        return {"operation": context.operation, "query": context.query, "paths": explained}

    # -- helpers
    def _llm(self):
        if self._llm_resolved:
            return self._llm_client
        self._llm_resolved = True
        key = os.environ.get("GOOGLE_API_KEY")
        if not key:
            return None
        try:
            from google import genai
            self._llm_client = genai.Client(api_key=key)
        except Exception:  # noqa: BLE001
            self._llm_client = None
        return self._llm_client

    @staticmethod
    def _deterministic_reason(
        eid: str,
        name: str,
        etype: str,
        score: float,
        step: TraversalStep | None,
        context: SubgraphContext,
    ) -> str:
        """Build a rule-based explanation without any LLM call."""
        parts = []
        if step:
            action_map = {
                "seed": "directly matched the query terms",
                "expand": "reached via graph expansion from a matched entity",
                "match": "matched by the retrieval algorithm",
                "prune": "initially retrieved but was later pruned",
            }
            action_text = action_map.get(step.action, f"reached via '{step.action}' action")
            parts.append(f"Step {step.step}: {name} ({etype}) {action_text}")
        else:
            parts.append(f"{name} ({etype}) was retrieved")

        if score >= 0.8:
            parts.append(f"with high relevance ({score:.2f})")
        elif score >= 0.5:
            parts.append(f"with moderate relevance ({score:.2f})")
        else:
            parts.append(f"with low relevance ({score:.2f})")

        # Check source documents
        source_docs = context.provenance.source_documents
        if source_docs:
            parts.append(f"supported by {len(source_docs)} source document(s)")

        return "; ".join(parts) + "."

    @staticmethod
    def _traversal_summary(context: SubgraphContext) -> str:
        """One-sentence summary of the traversal trajectory."""
        log = context.provenance.traversal_log or []
        total = len(log)
        cited = len([s for s in log if s.entity not in (context.provenance.visited_not_cited or [])])
        ops = context.operation.replace("_", " ")
        return (
            f"{ops.title()} traversed {total} entities, citing {cited} "
            f"from {len(context.provenance.source_documents)} source document(s)."
        )
