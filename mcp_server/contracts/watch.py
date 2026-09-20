"""Contract 18: Watch & Subscriptions — live graph change observation.

Allows clients to register interest in specific graph change events
(entity creations, edge mutations, community recalculations) with filter expressions.
Bridges persistent SQLite event logs and live memory pub/sub.
"""

from __future__ import annotations

from typing import Any

from mcp_server.contracts.streaming import STREAM_BUS
from mcp_server.storage import PersistentStorage


class WatchContract:
    """Contract 18: query and subscribe to graph change notifications."""

    def __init__(self, storage: PersistentStorage | None = None) -> None:
        self._storage = storage or PersistentStorage.get_instance()

    def watch(
        self,
        graph_id: str | None = None,
        event_types: list[str] | None = None,
        entity_id: str | None = None,
        since_timestamp: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Fetch matching graph mutation events since a given timestamp or cursor.

        Args:
            graph_id: Filter by graph name.
            event_types: Allowlist of event types.
            entity_id: Filter by target entity ID.
            since_timestamp: ISO-8601 timestamp string for incremental updates.
            limit: Maximum number of events to return (1-500).

        Returns:
            Dict with ``total``, ``events``, and ``latest_timestamp``.
        """
        limit = max(1, min(limit, 500))
        # 1. Fetch from persistent storage
        stored = self._storage.get_events(
            limit=limit,
            event_types=event_types,
            graph_id=graph_id,
            since_timestamp=since_timestamp,
        )

        # 2. Filter if entity_id specified
        if entity_id:
            stored = [e for e in stored if str(e.get("entity_id") or "") == str(entity_id)]

        latest_ts = stored[0]["timestamp"] if stored else since_timestamp

        return {
            "graph_id": graph_id or "all",
            "total_events": len(stored),
            "latest_timestamp": latest_ts,
            "events": stored,
            "subscriber_count": STREAM_BUS.subscriber_count,
        }
