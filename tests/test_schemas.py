"""Wire-contract tests: every ``schemas/*.json`` must match its Pydantic model.

``SPEC.md`` publishes ``schemas/*.json`` as the wire contract while
``mcp_server/protocol.py`` + ``mcp_server/protocol_extensions.py`` are the
implementation. This suite is the glue that keeps both honest: it fails when a
model gains or loses a field without the schema being updated (or the other way
round), and when a definition is neither backed by a model nor explicitly
listed as a documented-only shape.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_server import protocol as p
from mcp_server import protocol_extensions as x

SCHEMAS = Path(__file__).resolve().parents[1] / "schemas"

# filename -> (primary model, {definition name: model or enum})
_CONTRACTS: dict[str, tuple[type, dict[str, type]]] = {
    "retrieval-request.json": (p.RetrievalRequest, {}),
    "subgraph-context.json": (
        p.SubgraphContext,
        {
            "Entity": p.Entity,
            "Relationship": p.Relationship,
            "PathResult": p.PathResult,
            "CommunitySummary": p.CommunitySummary,
            "TextChunk": p.TextChunk,
            "TraversalStep": p.TraversalStep,
            "Provenance": p.Provenance,
            "ExtractionRecord": p.ExtractionRecord,
            "RetrievalMetrics": p.RetrievalMetrics,
        },
    ),
    "graph-schema.json": (
        p.GraphSchema,
        {
            "EntityType": p.EntityType,
            "RelationshipType": p.RelationshipType,
            "GraphStatistics": p.GraphStatistics,
        },
    ),
    "provenance.json": (
        p.Provenance,
        {"TraversalStep": p.TraversalStep, "ExtractionRecord": p.ExtractionRecord},
    ),
    "ingestion-config.json": (
        x.IngestionConfig,
        {
            "ExtractionStrategy": x.ExtractionStrategy,
            "ResolveStrategy": x.ResolveStrategy,
            "Triple": x.Triple,
            "IngestionReport": x.IngestionReport,
        },
    ),
    "federation-config.json": (
        x.FederationConfig,
        {
            "BackendRef": x.BackendRef,
            "MergeStrategy": x.MergeStrategy,
            "EntityLink": x.EntityLink,
        },
    ),
    "stream-event.json": (x.StreamEvent, {"StreamEventType": x.StreamEventType}),
    "evaluation-report.json": (
        x.EvaluationReport,
        {"RetrievalEval": x.RetrievalEval, "AnswerEval": x.AnswerEval},
    ),
    "access-policy.json": (
        x.AccessPolicy,
        {"PermissionDecision": x.PermissionDecision, "PermissionResult": x.PermissionResult},
    ),
    "prompt-format-config.json": (
        p.PromptFormatConfig,
        {"PromptFormat": p.PromptFormat},
    ),
}

#: Definitions that intentionally describe a free-form ``dict`` payload instead
#: of a model (the models type those fields as ``dict[str, Any]``). They are
#: documentation, not enforcement, so they are listed here on purpose.
_DOCUMENTED_ONLY = {"AttributeDef"}


def _load(filename: str) -> dict:
    return json.loads((SCHEMAS / filename).read_text())


def _definition_names(data: dict) -> set[str]:
    return set(data.get("definitions") or {})


def test_every_schema_file_is_bound_to_a_contract():
    """No unbound schema files, and every published contract file exists."""
    assert {path.name for path in SCHEMAS.glob("*.json")} == set(_CONTRACTS)


@pytest.mark.parametrize("filename", sorted(_CONTRACTS))
def test_schema_title_and_properties_match_the_model(filename: str) -> None:
    model, _ = _CONTRACTS[filename]
    data = _load(filename)

    assert data["title"] == model.__name__
    assert data["$id"].endswith(f"/{filename}")
    assert data["$schema"] == "http://json-schema.org/draft-07/schema#"

    schema_fields = set(data.get("properties") or {})
    model_fields = set(model.model_fields)
    assert schema_fields == model_fields, (
        f"{filename}: properties drift from {model.__name__} "
        f"(missing from schema: {sorted(model_fields - schema_fields)}, "
        f"unknown to model: {sorted(schema_fields - model_fields)})"
    )
    # Anything the schema declares required must be a real property.
    assert set(data.get("required") or []) <= schema_fields


@pytest.mark.parametrize("filename", sorted(_CONTRACTS))
def test_definitions_track_models_and_enums(filename: str) -> None:
    _, definitions = _CONTRACTS[filename]
    data = _load(filename)
    declared = _definition_names(data)

    assert declared == set(definitions) | (_DOCUMENTED_ONLY & declared)

    for name, model in definitions.items():
        assert name in declared, f"{filename}: {name} definition is missing"
        entry = data["definitions"][name]
        if isinstance(model, type) and issubclass(model, x.Enum) or model in (
            x.ExtractionStrategy,
            x.ResolveStrategy,
            x.MergeStrategy,
            x.StreamEventType,
            x.PermissionDecision,
        ):
            assert entry["enum"] == [member.value for member in model], f"{filename}: {name} enum drift"
            continue
        assert set(entry.get("properties") or {}) == set(model.model_fields), (
            f"{filename}: {name} definition drifted from the {model.__name__} model"
        )
        assert set(entry.get("required") or []) <= set(entry.get("properties") or {})


@pytest.mark.parametrize("filename", sorted(_CONTRACTS))
def test_local_refs_resolve(filename: str) -> None:
    data = _load(filename)
    refs: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            if isinstance(node.get("$ref"), str):
                refs.append(node["$ref"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data)
    for ref in refs:
        assert ref.startswith("#/definitions/"), f"{filename}: unexpected ref {ref}"
        assert ref.split("/")[-1] in _definition_names(data), f"{filename}: dangling ref {ref}"
