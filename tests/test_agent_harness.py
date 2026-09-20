"""Hermetic unit tests for the Agentic Investigation Harness, Conflict Resolution, and Query Triage.

Zero mocks: uses DemoGraphRAGAdapter with real graph structures and algorithms.
"""

from __future__ import annotations

import pytest

from mcp_server.adapters.fallback_adapter import DemoGraphRAGAdapter
from mcp_server.agent_harness import AgenticInvestigationHarness
from mcp_server.contracts.conflicts import ConflictResolutionContract
from mcp_server.contracts.retrieval import RetrievalContract
from mcp_server.contracts.triage import QueryTriageContract
from mcp_server.formatters.markdown_formatter import MarkdownFormatter
from mcp_server.pipelines import run_pipelines
from mcp_server.protocol import Provenance, RetrievalMetrics, SubgraphContext


@pytest.fixture()
def demo_adapter():
    return DemoGraphRAGAdapter()


class TestAgenticInvestigationHarness:
    """Tests for the autonomous agentic investigation loop."""

    def test_harness_initialization(self, demo_adapter):
        harness = AgenticInvestigationHarness(demo_adapter)
        assert harness.adapter is demo_adapter
        assert harness.retrieval is not None
        assert harness.similarity is not None

    def test_investigate_empty_query_raises(self, demo_adapter):
        harness = AgenticInvestigationHarness(demo_adapter)
        with pytest.raises(ValueError, match="non-empty question"):
            harness.investigate("")

    def test_investigate_multi_step_trajectory(self, demo_adapter):
        harness = AgenticInvestigationHarness(demo_adapter)
        res = harness.investigate(
            question="How does Attention relate to Transformer in deep learning?",
            max_steps=4,
            target_confidence=0.8,
        )

        assert res.question
        assert res.answer
        assert res.context.protocol == "graphrag/1.0"
        assert res.context.operation == "agentic_investigate"

        trace = res.trace
        assert trace.steps_count >= 1
        assert len(trace.retrieval_methods_selected) == trace.steps_count
        assert len(trace.tools_called) == trace.steps_count
        assert trace.total_tokens > 0
        assert trace.total_latency_ms >= 0
        assert 0.0 <= trace.evidence_sufficiency <= 1.0
        assert trace.stop_reason in {
            "max_steps_reached",
            f"target_confidence_reached ({trace.evidence_sufficiency:.2f} >= 0.80)",
        }

    def test_investigate_strategy_shift_on_unmatched_query(self, demo_adapter):
        harness = AgenticInvestigationHarness(demo_adapter)
        # Query with non-existent entities forces strategy shift to keyword search
        res = harness.investigate(
            question="Quantum Superposition In Cryogenic Qubits",
            max_steps=3,
        )
        assert res.trace.strategy_changed is True
        assert "pivoted" in (res.trace.strategy_change_reason or "").lower()


class TestConflictResolutionContract:
    """Tests for Contract 19: Conflict & Uncertainty Resolution."""

    def test_detect_no_conflicts_on_clean_context(self, demo_adapter):
        contract = ConflictResolutionContract(demo_adapter)
        ctx = demo_adapter.neighborhood(entity_id="transformer", depth=1)
        res = contract.resolve_conflicts(ctx)
        assert res["conflicts_detected"] == 0
        assert res["uncertainty_score"] == 0.0

    def test_detect_and_resolve_property_contradiction(self, demo_adapter):
        contract = ConflictResolutionContract(demo_adapter)
        # Construct synthetic context with contradictory entity facts
        conflict_ctx = SubgraphContext(
            protocol="graphrag/1.0",
            operation="local_search",
            query={"text": "test conflicts"},
            results={
                "entities": [
                    {
                        "id": "BERT",
                        "name": "BERT",
                        "type": "model",
                        "properties": {"year": "2018", "status": "experimental"},
                    },
                    {
                        "id": "BERT_v2",
                        "name": "BERT",
                        "type": "model",
                        "properties": {"year": "2023", "status": "production_standard"},
                    },
                ],
                "relationships": [],
                "paths": [],
                "communities": [],
                "text_chunks": [],
            },
            provenance=Provenance(
                source_documents=["paper_2023_survey.pdf", "paper_2018_initial.pdf"],
                traversal_log=[],
                visited_not_cited=[],
                total_entities_examined=2,
                total_chunks_returned=2,
                backend="test",
                backend_version="1.0",
            ),
            metrics=RetrievalMetrics(input_tokens=100, entities_returned=2, relationships_returned=0),
        )

        detected = contract.detect_conflicts(conflict_ctx)
        assert len(detected) >= 1

        resolution = contract.resolve_conflicts(conflict_ctx)
        assert resolution["conflicts_detected"] >= 1
        assert len(resolution["resolved_facts"]) >= 1

        # The 2023 fact should win over 2018 due to recency weighting
        year_resolutions = [r for r in resolution["resolved_facts"] if r["property"] == "year"]
        if year_resolutions:
            assert year_resolutions[0]["resolved_value"] == "2023"


class TestQueryTriageContract:
    """Tests for Contract 20: Query Triage & ROI Classifier."""

    def test_triage_simple_factoid_routes_to_rag(self, demo_adapter):
        contract = QueryTriageContract(demo_adapter)
        res = contract.triage("What is BERT?")
        assert res["recommended_pipeline"] == "rag"
        assert res["agentic_roi"] == "LOW"

    def test_triage_structured_entity_routes_to_graphrag(self, demo_adapter):
        contract = QueryTriageContract(demo_adapter)
        res = contract.triage("Which papers belong to the attention community?")
        assert res["recommended_pipeline"] == "graphrag"

    def test_triage_multihop_investigation_routes_to_agentic(self, demo_adapter):
        contract = QueryTriageContract(demo_adapter)
        res = contract.triage(
            "How does attention connect to Transformer and what conflicting evidence exists over time?"
        )
        assert res["recommended_pipeline"] == "agentic_graphrag"
        assert res["agentic_roi"] == "HIGH"
        assert res["complexity_score"] >= 0.55


class TestUpdatedPipelinesExecution:
    """Tests that run_pipelines correctly incorporates the agentic harness and trace."""

    def test_run_pipelines_generates_agentic_trace(self, demo_adapter):
        retrieval = RetrievalContract(demo_adapter)
        formatter = MarkdownFormatter()

        output = run_pipelines(
            retrieval=retrieval,
            formatter=formatter,
            question="How does BERT connect to Transformer?",
            use_agent=True,
        )

        assert "pipeline_1" in output
        assert "pipeline_2" in output
        assert "pipeline_3" in output

        p3 = output["pipeline_3"]
        assert p3["retrieval_method"] == "agentic_investigate"
        assert "agentic_trace" in p3
        trace = p3["agentic_trace"]
        assert trace["steps_count"] >= 1
        assert trace["total_tokens"] > 0
        assert "evidence_sufficiency" in trace
