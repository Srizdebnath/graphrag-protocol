"""Contract implementations for the GraphRAG Protocol.

Contracts 1–3 (retrieval, subgraph context, schema discovery) plus the
implemented extensions: 4 construction, 6 federation, 7 streaming,
9 evaluation, 10 authorization, 11 similarity, 12 temporal, 13 explanation,
14 diff, 15 aggregate.

Contract 2 (SubgraphContext) and Contract 5 (Provenance) are model-level
contracts defined in :mod:`mcp_server.protocol`; Contract 8 (formatters)
lives in :mod:`mcp_server.formatters`.
"""

from .aggregate import AggregateContract
from .authorization import AuthorizationContract
from .base import BaseRetrievalContract
from .construction import ConstructionContract, extract_concepts
from .diff import DiffContract
from .evaluation import EvaluationContract, content_terms
from .explanation import ExplanationContract
from .federation import FederationContract
from .provenance import ProvenanceContract
from .retrieval import RetrievalContract
from .schema_discovery import SchemaDiscoveryContract
from .similarity import SimilarityContract
from .streaming import STREAM_BUS, StreamBus, publish_ingestion_report
from .temporal import TemporalContract

__all__ = [
    "STREAM_BUS",
    "AggregateContract",
    "AuthorizationContract",
    "BaseRetrievalContract",
    "ConstructionContract",
    "DiffContract",
    "EvaluationContract",
    "ExplanationContract",
    "FederationContract",
    "ProvenanceContract",
    "RetrievalContract",
    "SchemaDiscoveryContract",
    "SimilarityContract",
    "StreamBus",
    "TemporalContract",
    "content_terms",
    "extract_concepts",
    "publish_ingestion_report",
]