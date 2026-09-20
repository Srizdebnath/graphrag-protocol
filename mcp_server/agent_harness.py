"""Autonomous Agentic GraphRAG Investigation Harness.

Manages dynamic state, specialized retrieval tools, intermediate evidence evaluation,
adaptive strategy pivoting, and termination criteria. Emits the canonical AgenticTrace
measuring the investigation trajectory without synthetic mocks or fakes.
"""

from __future__ import annotations

import os
import re
import time
from typing import Any

from pydantic import BaseModel, Field

from mcp_server.adapters.base import BaseGraphRAGAdapter
from mcp_server.contracts.aggregate import AggregateContract
from mcp_server.contracts.retrieval import RetrievalContract
from mcp_server.contracts.similarity import SimilarityContract
from mcp_server.formatters.markdown_formatter import MarkdownFormatter
from mcp_server.protocol import Provenance, RetrievalMetrics, SubgraphContext, TraversalStep


class ToolInvocation(BaseModel):
    """Record of a single tool execution within the agentic investigation."""

    step: int
    tool: str
    arguments: dict[str, Any]
    latency_ms: float
    tokens: int
    entities_found: int
    relationships_found: int
    status: str = "ok"


class AgenticTrace(BaseModel):
    """Measurable execution trace of the autonomous agentic investigation."""

    steps_count: int
    retrieval_methods_selected: list[str]
    tools_called: list[ToolInvocation]
    time_per_operation_ms: list[float]
    tokens_per_operation: list[int]
    total_tokens: int
    total_latency_ms: float
    citations_count: int
    strategy_changed: bool = False
    strategy_change_reason: str | None = None
    stop_reason: str
    evidence_sufficiency: float = Field(ge=0.0, le=1.0)


class AgenticInvestigationResult(BaseModel):
    """Complete output of an autonomous investigation."""

    question: str
    answer: str
    answer_source: str
    context: SubgraphContext
    trace: AgenticTrace


class AgenticInvestigationHarness:
    """Orchestrator agent managing dynamic multi-step investigations."""

    def __init__(self, adapter: BaseGraphRAGAdapter) -> None:
        self.adapter = adapter
        self.retrieval = RetrievalContract(adapter)
        self.similarity = SimilarityContract(adapter)
        self.aggregate = AggregateContract(adapter)
        self.formatter = MarkdownFormatter()

    def investigate(
        self,
        question: str,
        max_steps: int = 5,
        target_confidence: float = 0.85,
    ) -> AgenticInvestigationResult:
        """Execute an autonomous, multi-step agentic graph investigation.

        Args:
            question: The natural-language query to investigate.
            max_steps: Maximum number of tool iterations before halting (default 5).
            target_confidence: Minimum evidence sufficiency score to stop early.

        Returns:
            AgenticInvestigationResult with synthesized answer and detailed trace.
        """
        t0 = time.monotonic()
        q = (question or "").strip()
        if not q:
            raise ValueError("Investigate requires a non-empty question")

        accumulated_entities: dict[str, dict[str, Any]] = {}
        accumulated_relationships: list[dict[str, Any]] = []
        accumulated_source_docs: set[str] = set()
        traversal_log: list[TraversalStep] = []

        tools_called: list[ToolInvocation] = []
        retrieval_methods: list[str] = []
        time_per_op: list[float] = []
        tokens_per_op: list[int] = []

        strategy_changed = False
        strategy_change_reason: str | None = None
        stop_reason = "max_steps_reached"
        evidence_sufficiency = 0.0

        current_strategy = "entity_link_and_expand"

        # --- STEP 1: Entity Linking from Question ---
        step_idx = 1
        t_step = time.monotonic()
        entities_found = self._find_candidate_entities(q)
        dt_ms = (time.monotonic() - t_step) * 1000
        step_tokens = max(1, len(str(entities_found)) // 4)

        for e in entities_found:
            accumulated_entities[e["id"]] = e
            traversal_log.append(
                TraversalStep(step=step_idx, entity=e["id"], action="seed", score=float(e.get("relevance_score", 0.9)))
            )

        tools_called.append(
            ToolInvocation(
                step=step_idx,
                tool="graphrag_entity_lookup",
                arguments={"query": q, "top_candidates": len(entities_found)},
                latency_ms=round(dt_ms, 2),
                tokens=step_tokens,
                entities_found=len(entities_found),
                relationships_found=0,
            )
        )
        retrieval_methods.append("entity_lookup")
        time_per_op.append(round(dt_ms, 2))
        tokens_per_op.append(step_tokens)

        # Check early exit if simple entity lookup failed
        if not entities_found:
            strategy_changed = True
            strategy_change_reason = "No direct entity matches found in query; pivoted to fuzzy keyword search"
            current_strategy = "keyword_local_search"

        # --- ITERATIVE REASONING & EXPANSION LOOP ---
        while step_idx < max_steps:
            step_idx += 1
            t_step = time.monotonic()

            if current_strategy == "entity_link_and_expand" and accumulated_entities:
                seed_id = next(iter(accumulated_entities.keys()))
                ctx = self.adapter.neighborhood(entity_id=seed_id, depth=2)
                op_name = "neighborhood"
                new_ents = ctx.results.get("entities") or []
                new_rels = ctx.results.get("relationships") or []

                for e in new_ents:
                    if e.get("id") not in accumulated_entities:
                        accumulated_entities[e["id"]] = e
                        traversal_log.append(
                            TraversalStep(
                                step=step_idx,
                                entity=e["id"],
                                action="expand",
                                score=float(e.get("relevance_score", 0.7)),
                            )
                        )
                accumulated_relationships.extend(new_rels)
                accumulated_source_docs.update(ctx.provenance.source_documents)

                dt_ms = (time.monotonic() - t_step) * 1000
                st_tokens = max(1, len(str(new_ents)) // 4)
                tools_called.append(
                    ToolInvocation(
                        step=step_idx,
                        tool="graphrag_neighborhood",
                        arguments={"entity_id": seed_id, "depth": 2},
                        latency_ms=round(dt_ms, 2),
                        tokens=st_tokens,
                        entities_found=len(new_ents),
                        relationships_found=len(new_rels),
                    )
                )
                retrieval_methods.append(op_name)
                time_per_op.append(round(dt_ms, 2))
                tokens_per_op.append(st_tokens)

                # Check if multi-entity path search is needed
                entity_ids = list(accumulated_entities.keys())
                if len(entity_ids) >= 2:
                    current_strategy = "multi_hop_path"
                else:
                    current_strategy = "verify_evidence"

            elif current_strategy == "multi_hop_path":
                keys = list(accumulated_entities.keys())
                src, tgt = keys[0], keys[1]
                ctx = self.adapter.path_search(source=src, target=tgt, max_hops=4)
                op_name = "path_search"
                paths = ctx.results.get("paths") or []

                dt_ms = (time.monotonic() - t_step) * 1000
                st_tokens = max(1, len(str(paths)) // 4)
                tools_called.append(
                    ToolInvocation(
                        step=step_idx,
                        tool="graphrag_path",
                        arguments={"source": src, "target": tgt, "max_hops": 4},
                        latency_ms=round(dt_ms, 2),
                        tokens=st_tokens,
                        entities_found=0,
                        relationships_found=len(paths),
                    )
                )
                retrieval_methods.append(op_name)
                time_per_op.append(round(dt_ms, 2))
                tokens_per_op.append(st_tokens)

                if not paths:
                    strategy_changed = True
                    strategy_change_reason = f"No direct path between {src} and {tgt}; pivoted to community clustering"
                    current_strategy = "community_global_search"
                else:
                    current_strategy = "verify_evidence"

            elif current_strategy == "community_global_search":
                ctx = self.adapter.global_search(query=q, top_communities=3)
                op_name = "global_search"
                comms = ctx.results.get("communities") or []

                dt_ms = (time.monotonic() - t_step) * 1000
                st_tokens = max(1, len(str(comms)) // 4)
                tools_called.append(
                    ToolInvocation(
                        step=step_idx,
                        tool="graphrag_global_search",
                        arguments={"query": q, "top_communities": 3},
                        latency_ms=round(dt_ms, 2),
                        tokens=st_tokens,
                        entities_found=0,
                        relationships_found=len(comms),
                    )
                )
                retrieval_methods.append(op_name)
                time_per_op.append(round(dt_ms, 2))
                tokens_per_op.append(st_tokens)
                current_strategy = "verify_evidence"

            else:  # keyword_local_search or verify_evidence
                ctx = self.adapter.local_search(query=q, top_k=5, depth=1)
                op_name = "local_search"
                new_ents = ctx.results.get("entities") or []
                for e in new_ents:
                    accumulated_entities[e["id"]] = e
                accumulated_source_docs.update(ctx.provenance.source_documents)

                dt_ms = (time.monotonic() - t_step) * 1000
                st_tokens = max(1, len(str(new_ents)) // 4)
                tools_called.append(
                    ToolInvocation(
                        step=step_idx,
                        tool="graphrag_local_search",
                        arguments={"query": q, "top_k": 5},
                        latency_ms=round(dt_ms, 2),
                        tokens=st_tokens,
                        entities_found=len(new_ents),
                        relationships_found=0,
                    )
                )
                retrieval_methods.append(op_name)
                time_per_op.append(round(dt_ms, 2))
                tokens_per_op.append(st_tokens)

            # Evaluate Evidence Sufficiency
            evidence_sufficiency = self._compute_evidence_sufficiency(
                question=q,
                entities=list(accumulated_entities.values()),
                relationships=accumulated_relationships,
            )

            if evidence_sufficiency >= target_confidence:
                stop_reason = f"target_confidence_reached ({evidence_sufficiency:.2f} >= {target_confidence:.2f})"
                break

        # Construct Final SubgraphContext
        total_latency = (time.monotonic() - t0) * 1000
        total_tokens = sum(tokens_per_op)

        subgraph_context = SubgraphContext(
            protocol="graphrag/1.0",
            operation="agentic_investigate",
            query={"text": q, "max_steps": max_steps, "steps_executed": step_idx},
            results={
                "entities": list(accumulated_entities.values()),
                "relationships": accumulated_relationships,
                "paths": [],
                "communities": [],
                "text_chunks": [],
            },
            provenance=Provenance(
                source_documents=sorted(accumulated_source_docs),
                traversal_log=traversal_log,
                visited_not_cited=[],
                total_entities_examined=len(accumulated_entities),
                total_chunks_returned=len(accumulated_source_docs),
                backend=self.adapter.__class__.__name__,
                backend_version="1.0",
            ),
            metrics=RetrievalMetrics(
                input_tokens=total_tokens,
                entities_returned=len(accumulated_entities),
                relationships_returned=len(accumulated_relationships),
                paths_found=0,
                communities_matched=0,
                graph_hops_traversed=step_idx,
                latency_ms=round(total_latency, 2),
            ),
        )

        trace = AgenticTrace(
            steps_count=step_idx,
            retrieval_methods_selected=retrieval_methods,
            tools_called=tools_called,
            time_per_operation_ms=time_per_op,
            tokens_per_operation=tokens_per_op,
            total_tokens=total_tokens,
            total_latency_ms=round(total_latency, 2),
            citations_count=len(accumulated_source_docs),
            strategy_changed=strategy_changed,
            strategy_change_reason=strategy_change_reason,
            stop_reason=stop_reason,
            evidence_sufficiency=round(evidence_sufficiency, 3),
        )

        # Synthesize Grounded Answer
        answer, source = self._synthesize_answer(q, subgraph_context)

        return AgenticInvestigationResult(
            question=q,
            answer=answer,
            answer_source=source,
            context=subgraph_context,
            trace=trace,
        )

    def _find_candidate_entities(self, query: str) -> list[dict[str, Any]]:
        """Look up entity candidates from query words."""
        # Try words of 3+ letters
        tokens = [w for w in re.findall(r"\b[A-Za-z0-9\-]{3,}\b", query) if w.lower() not in {"what", "when", "where", "which", "how", "does", "with", "from"}]
        found = []
        for tok in tokens[:3]:
            ctx = self.adapter.entity_lookup(entity_name=tok)
            ents = ctx.results.get("entities") or []
            valid_ents = [
                e for e in ents
                if str(e.get("id", "")).lower() not in {"unknown", ""}
                and str(e.get("type", "")).lower() not in {"unknown", ""}
            ]
            if valid_ents:
                found.extend(valid_ents[:2])
        return found

    @staticmethod
    def _compute_evidence_sufficiency(
        question: str,
        entities: list[dict[str, Any]],
        relationships: list[dict[str, Any]],
    ) -> float:
        """Measure evidence coverage for the question."""
        if not entities:
            return 0.1
        score = 0.2
        # Entity quantity bonus
        score += min(0.4, len(entities) * 0.1)
        # Relationship bonus
        if relationships:
            score += min(0.3, len(relationships) * 0.05)
        # Direct name overlap bonus
        q_lower = question.lower()
        matched_names = sum(1 for e in entities if str(e.get("name", "")).lower() in q_lower)
        if matched_names >= 1:
            score += 0.2
        return min(1.0, score)

    def _synthesize_answer(self, question: str, context: SubgraphContext) -> tuple[str, str]:
        """Synthesize final grounded answer using LLM when available, or extractive synthesis."""
        key = os.environ.get("GOOGLE_API_KEY")
        context_md = self.formatter.format_context(context, max_tokens=2500)

        if key:
            try:
                from google import genai

                client = genai.Client(api_key=key)
                prompt = (
                    "You are an investigative GraphRAG agent. Answer the question thoroughly based ONLY "
                    "on the retrieved multi-hop graph context below. Explicitly cite entity names and source documents.\n\n"
                    f"Context:\n{context_md}\n\nQuestion: {question}"
                )
                model_name = os.environ.get("LLM_MODEL", "gemini-2.5-flash")
                resp = client.models.generate_content(model=model_name, contents=prompt)
                return ((resp.text or "").strip() or "(empty response)", "llm")
            except Exception:  # noqa: BLE001, S110
                pass

        # Extractive deterministic fallback
        ents = context.results.get("entities") or []
        names = [str(e.get("name") or e.get("id")) for e in ents[:5]]
        docs = context.provenance.source_documents[:3]
        docs_str = f" from sources {', '.join(docs)}" if docs else ""
        answer_text = (
            f"[extractive_synthesis] Evidence connects entities: {', '.join(names)}{docs_str}. "
            f"Context contains {len(ents)} entities and {len(context.results.get('relationships') or [])} relationships."
        )
        return (answer_text, "extractive")
