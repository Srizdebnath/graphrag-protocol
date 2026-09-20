"""Contract 3: Schema Discovery.

Wraps a backend adapter's schema-introspection primitives and adds a
time-based cache so repeated calls do not hammer the backend. All results
are normalized into protocol models (:class:`GraphSchema`,
:class:`EntityType`, :class:`RelationshipType`, :class:`GraphStatistics`).
"""

from __future__ import annotations

import threading
import time
from typing import Any

from mcp_server.adapters.base import BaseGraphRAGAdapter
from mcp_server.protocol import (
    EntityType,
    GraphSchema,
    GraphStatistics,
    RelationshipType,
)

CacheKey = tuple[str, str]
_CachedValue = tuple[float, Any]


class SchemaDiscoveryContract:
    """Contract 3: normalized, cached schema introspection.

    Args:
        adapter: The backend adapter to introspect. Must not be ``None``.
        ttl_seconds: Lifetime of cached values in seconds (default 300).
    """

    def __init__(
        self,
        adapter: BaseGraphRAGAdapter,
        ttl_seconds: float = 300.0,
    ) -> None:
        """Initialize the contract and its cache.

        Args:
            adapter: A :class:`BaseGraphRAGAdapter` instance.
            ttl_seconds: Cache time-to-live in seconds.

        Raises:
            ValueError: If ``adapter`` is ``None``.
        """
        if adapter is None:
            raise ValueError("SchemaDiscoveryContract requires a non-None adapter")
        self._adapter: BaseGraphRAGAdapter = adapter
        self._ttl: float = max(0.0, float(ttl_seconds))
        self._cache: dict[CacheKey, _CachedValue] = {}
        self._lock = threading.Lock()

    # -- public API -------------------------------------------------------------

    def get_schema(self, graph_id: str | None = None) -> GraphSchema:
        """Return the full, normalized graph schema.

        Results are cached per ``graph_id`` for the configured TTL.

        Args:
            graph_id: Optional graph identifier; falls back to the
                adapter's default graph.

        Returns:
            A :class:`GraphSchema` with vertex/edge types and statistics.
        """
        cache_key = ("schema", graph_id or "")
        cached = self._get(cache_key)
        if cached is not None:
            return cached
        schema = self._adapter.get_schema(graph_id=graph_id)
        schema = self._normalize_graph_schema(schema)
        self._set(cache_key, schema)
        return schema

    def get_entity_types(self, graph_id: str | None = None) -> list[EntityType]:
        """Return all vertex types with attributes and counts.

        Args:
            graph_id: Optional graph identifier.

        Returns:
            List of :class:`EntityType`.
        """
        cache_key = ("entity_types", graph_id or "")
        cached = self._get(cache_key)
        if cached is not None:
            return cached
        schema = self.get_schema(graph_id=graph_id)
        self._set(cache_key, schema.vertex_types)
        return schema.vertex_types

    def get_relationship_types(
        self, graph_id: str | None = None
    ) -> list[RelationshipType]:
        """Return all edge types with source/target and counts.

        Args:
            graph_id: Optional graph identifier.

        Returns:
            List of :class:`RelationshipType`.
        """
        cache_key = ("relationship_types", graph_id or "")
        cached = self._get(cache_key)
        if cached is not None:
            return cached
        schema = self.get_schema(graph_id=graph_id)
        self._set(cache_key, schema.edge_types)
        return schema.edge_types

    def get_sample_entities(
        self, entity_type: str, count: int = 5, graph_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Return sample entities of a given type for LLM context.

        Cached per ``(entity_type, count)``. Falls back to the ``sample``
        attribute of the matching :class:`EntityType` if the adapter does
        not expose a dedicated sample API.

        Args:
            entity_type: The vertex type to sample.
            count: Maximum number of samples to return.
            graph_id: Optional graph identifier.

        Returns:
            A list of sample entity dicts (may be empty if none available).
        """
        if not entity_type:
            raise ValueError("entity_type must be a non-empty string")
        count = max(1, min(100, int(count)))
        cache_key = ("sample", f"{graph_id or ''}:{entity_type}:{count}")
        cached = self._get(cache_key)
        if cached is not None:
            return cached

        get_sample = getattr(self._adapter, "get_sample_entities", None)
        samples: list[dict[str, Any]] = []
        if callable(get_sample):
            raw = get_sample(entity_type=entity_type, count=count)
            samples = self._as_list(raw)
        if not samples:
            for vt in self.get_entity_types(graph_id=graph_id):
                if vt.type == entity_type and vt.sample:
                    samples.append(vt.sample)
        samples = samples[:count]
        self._set(cache_key, samples)
        return samples

    def get_statistics(self, graph_id: str | None = None) -> GraphStatistics:
        """Return graph-level statistics.

        Args:
            graph_id: Optional graph identifier.

        Returns:
            A :class:`GraphStatistics`.
        """
        cache_key = ("statistics", graph_id or "")
        cached = self._get(cache_key)
        if cached is not None:
            return cached
        schema = self.get_schema(graph_id=graph_id)
        self._set(cache_key, schema.statistics)
        return schema.statistics

    # -- cache helpers ----------------------------------------------------------

    def _get(self, key: CacheKey) -> Any:
        """Retrieve a non-expired cached value.

        Args:
            key: The composite cache key.

        Returns:
            The cached value, or ``None`` if absent/expired.
        """
        with self._lock:
            item = self._cache.get(key)
            if item is None:
                return None
            stored_at, value = item
            if time.monotonic() - stored_at > self._ttl:
                self._cache.pop(key, None)
                return None
            return value

    def _set(self, key: CacheKey, value: Any) -> None:
        """Store a value with the current timestamp.

        Args:
            key: The composite cache key.
            value: The value to cache.
        """
        with self._lock:
            self._cache[key] = (time.monotonic(), value)

    # -- normalization helpers --------------------------------------------------

    def _normalize_graph_schema(self, raw: Any) -> GraphSchema:
        """Normalize a schema (dict or model) into :class:`GraphSchema`.

        Args:
            raw: The raw schema from the adapter.

        Returns:
            A normalized :class:`GraphSchema`.
        """
        if isinstance(raw, GraphSchema):
            return raw
        if isinstance(raw, dict):
            return GraphSchema(**raw)
        raise TypeError(
            f"Adapter returned unsupported schema type: {type(raw).__name__}"
        )

    @staticmethod
    def _as_list(raw: Any) -> list[dict[str, Any]]:
        """Coerce adapter sample output into a list of dicts.

        Args:
            raw: Raw sample output (list of dicts/models, or ``None``).

        Returns:
            A list of plain dicts.
        """
        if raw is None:
            return []
        items = raw if isinstance(raw, (list, tuple)) else [raw]
        result: list[dict[str, Any]] = []
        for item in items:
            if isinstance(item, dict):
                result.append(item)
            elif hasattr(item, "model_dump"):
                result.append(item.model_dump())
            elif hasattr(item, "__dict__"):
                result.append(dict(item.__dict__))
        return result
