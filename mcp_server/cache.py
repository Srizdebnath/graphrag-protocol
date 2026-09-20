"""Query caching layer for GraphRAG MCP tools.

Deterministic caching of SubgraphContext results with TTL expiration,
LRU eviction, and automatic invalidation when graph mutations occur.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any

from mcp_server.storage import PersistentStorage


class QueryCache:
    """Thread-safe query result cache with TTL and automatic invalidation."""

    _instance: QueryCache | None = None
    _lock = threading.Lock()

    def __init__(self, default_ttl: float = 300.0, max_size: int = 1000) -> None:
        self.default_ttl = max(0.0, float(default_ttl))
        self.max_size = max_size
        self._memory: dict[str, tuple[float, float, str, dict[str, Any]]] = {}  # key -> (timestamp, ttl, graph_id, data)
        self._lock_mem = threading.Lock()
        self._storage = PersistentStorage.get_instance()
        self.hits = 0
        self.misses = 0

    @classmethod
    def get_instance(cls) -> QueryCache:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @staticmethod
    def make_key(tool_name: str, args: dict[str, Any]) -> str:
        """Create a deterministic hash key from tool name and arguments."""
        # Normalize args
        cleaned = {k: v for k, v in args.items() if v is not None}
        dumped = json.dumps(cleaned, sort_keys=True, default=str)
        digest = hashlib.sha256(dumped.encode("utf-8")).hexdigest()[:16]
        return f"{tool_name}:{digest}"

    def get(self, key: str) -> dict[str, Any] | None:
        now = time.monotonic()
        with self._lock_mem:
            if key in self._memory:
                ts, ttl, _graph_id, data = self._memory[key]
                if now - ts <= ttl:
                    self.hits += 1
                    return data
                del self._memory[key]

        # Check persistent storage
        stored = self._storage.cache_get(key)
        if stored is not None:
            with self._lock_mem:
                self.hits += 1
                self._memory[key] = (now, self.default_ttl, stored.get("graph_id", "default"), stored)
            return stored

        self.misses += 1
        return None

    def set(
        self,
        key: str,
        tool_name: str,
        result: dict[str, Any],
        graph_id: str = "default",
        ttl: float | None = None,
    ) -> None:
        effective_ttl = ttl if ttl is not None else self.default_ttl
        now = time.monotonic()
        with self._lock_mem:
            if len(self._memory) >= self.max_size:
                # Evict oldest entry
                oldest_key = min(self._memory.keys(), key=lambda k: self._memory[k][0])
                del self._memory[oldest_key]
            self._memory[key] = (now, effective_ttl, graph_id, result)

        try:
            self._storage.cache_set(key, tool_name, graph_id, result, ttl_seconds=effective_ttl)
        except Exception:  # noqa: BLE001, S110
            pass

    def invalidate(self, graph_id: str | None = None) -> int:
        """Invalidate cache entries for a graph (or all if None)."""
        count = 0
        with self._lock_mem:
            if graph_id is None:
                count = len(self._memory)
                self._memory.clear()
            else:
                to_delete = [k for k, v in self._memory.items() if v[2] == graph_id]
                for k in to_delete:
                    del self._memory[k]
                count = len(to_delete)

        if graph_id:
            try:
                self._storage.cache_clear_for_graph(graph_id)
            except Exception:  # noqa: BLE001, S110
                pass
        return count
