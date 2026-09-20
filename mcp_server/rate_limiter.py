"""Rate limiting middleware for GraphRAG MCP server.

Token-bucket rate limiter to prevent flooding of expensive retrieval and mutation operations.
"""

from __future__ import annotations

import threading
import time
from typing import ClassVar


class RateLimiter:
    """Sliding-window token-bucket rate limiter per client/token."""

    _instance: RateLimiter | None = None
    _lock = threading.Lock()

    # Default limits (calls per minute)
    DEFAULT_LIMITS: ClassVar[dict[str, int]] = {
        "read": 120,        # search, entity, path, neighborhood, schema
        "mutate": 20,       # ingest, update, delete
        "fanout": 30,       # federated search
        "heavy": 10,        # evaluate, LLM reasoning
    }

    def __init__(self, limits: dict[str, int] | None = None) -> None:
        self.limits = limits or dict(self.DEFAULT_LIMITS)
        # client_id:category -> list of timestamp floats
        self._history: dict[str, list[float]] = {}
        self._hist_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> RateLimiter:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _category_for_tool(self, tool_name: str) -> str:
        if tool_name in ("graphrag_ingest", "graphrag_delete_document", "graphrag_register_backend"):
            return "mutate"
        if tool_name in ("graphrag_federated_search", "graphrag_batch"):
            return "fanout"
        if tool_name in ("graphrag_evaluate",):
            return "heavy"
        return "read"

    def check(self, client_id: str, tool_name: str) -> tuple[bool, float]:
        """Check if request is permitted. Returns (allowed, retry_after_seconds)."""
        category = self._category_for_tool(tool_name)
        max_per_minute = self.limits.get(category, 60)
        key = f"{client_id or 'anon'}:{category}"
        now = time.monotonic()
        window_start = now - 60.0

        with self._hist_lock:
            records = self._history.setdefault(key, [])
            # Prune records older than 60 seconds
            self._history[key] = [t for t in records if t > window_start]
            records = self._history[key]

            if len(records) >= max_per_minute:
                oldest = records[0]
                retry_after = round(max(0.1, 60.0 - (now - oldest)), 1)
                return False, retry_after

            records.append(now)
            return True, 0.0
