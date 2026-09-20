"""Contract 7: Streaming — real in-process event bus for graph mutations.

The bus is a genuine asyncio pub/sub with bounded per-subscriber queues and
thread-safe fan-out, so events published from synchronous code paths (the
ingestion contract, HTTP handlers) reach async subscribers (MCP/SSE clients)
without loss. Events are emitted at real mutation points — ingestion calls
:func:`publish_ingestion_report`, which derives events from measured report
counters rather than inventing them.
"""

from __future__ import annotations

import asyncio
import itertools
import threading
from collections import deque
from collections.abc import AsyncIterator, Callable, Iterable
from typing import Any

from mcp_server.protocol_extensions import (
    IngestionReport,
    StreamEvent,
    StreamEventType,
)

_MAX_QUEUE = 1000


class StreamBus:
    """Contract 7: bounded, thread-safe pub/sub over :class:`StreamEvent`.

    Args:
        history_size: Number of recent events retained for replay/backfill.
    """

    def __init__(self, history_size: int = 200) -> None:
        self._subscribers: set[asyncio.Queue[StreamEvent]] = set()
        self._history: deque[StreamEvent] = deque(maxlen=max(1, history_size))
        self._counter = itertools.count(1)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()

    # -- publishing -------------------------------------------------------------

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Record the loop used for thread-safe hand-off (idempotent)."""
        self._loop = loop

    def emit(
        self,
        event_type: StreamEventType,
        graph_id: str,
        entity_id: str | None = None,
        entity_type: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> StreamEvent:
        """Build, retain, and fan out one event. Returns the event."""
        event = StreamEvent(
            event_id=f"evt-{next(self._counter)}",
            event_type=event_type,
            graph_id=graph_id,
            entity_id=entity_id,
            entity_type=entity_type,
            payload=payload or {},
        )
        self.publish_update(event)
        return event

    def publish_update(self, event: StreamEvent) -> int:
        """Deliver an event to every active subscriber.

        Thread-safe: when the publishing thread is not the bound event loop
        thread, delivery is scheduled onto that loop.

        Args:
            event: The event to broadcast.

        Returns:
            The number of subscribers the event was queued for.
        """
        self._history.append(event)
        with self._lock:
            count = len(self._subscribers)
        loop = self._loop
        if loop is not None and loop.is_running():
            try:
                current = asyncio.get_running_loop()
            except RuntimeError:
                current = None
            if current is not loop:
                loop.call_soon_threadsafe(self._deliver, event)
                return count
        self._deliver(event)
        return count

    def _deliver(self, event: StreamEvent) -> None:
        """Non-blocking delivery; drops the oldest event on queue overflow."""
        with self._lock:
            queues = list(self._subscribers)
        for queue in queues:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                    queue.put_nowait(event)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    continue

    # -- subscribing ------------------------------------------------------------

    async def subscribe(
        self,
        event_types: Iterable[StreamEventType] | None = None,
        filter_fn: Callable[[StreamEvent], bool] | None = None,
        replay: bool = False,
        timeout: float | None = None,
    ) -> AsyncIterator[StreamEvent | None]:
        """Yield matching events as they are published.

        Args:
            event_types: Optional allowlist of event types.
            filter_fn: Optional predicate for custom filtering.
            replay: When true, buffered history is yielded first.
            timeout: Optional seconds to wait before yielding ``None`` (heartbeat).

        Yields:
            :class:`StreamEvent` instances matching the filters, or ``None`` on timeout.
        """
        wanted = set(event_types) if event_types else None
        queue: asyncio.Queue[StreamEvent] = asyncio.Queue(maxsize=_MAX_QUEUE)
        self.bind_loop(asyncio.get_running_loop())
        with self._lock:
            self._subscribers.add(queue)
        try:
            if replay:
                for past in list(self._history):
                    if self._matches(past, wanted, filter_fn):
                        yield past
            while True:
                if timeout is not None:
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=timeout)
                    except asyncio.TimeoutError:
                        yield None
                        continue
                else:
                    event = await queue.get()
                if event is not None and self._matches(event, wanted, filter_fn):
                    yield event
        finally:
            with self._lock:
                self._subscribers.discard(queue)

    @staticmethod
    def _matches(
        event: StreamEvent,
        wanted: set[StreamEventType] | None,
        filter_fn: Callable[[StreamEvent], bool] | None,
    ) -> bool:
        """True when the event passes the type allowlist and custom predicate."""
        if wanted and event.event_type not in wanted:
            return False
        return not filter_fn or bool(filter_fn(event))

    # -- introspection ----------------------------------------------------------

    @property
    def subscriber_count(self) -> int:
        """Number of currently attached subscribers."""
        with self._lock:
            return len(self._subscribers)

    def recent(self, limit: int = 20) -> list[StreamEvent]:
        """Most recent events, newest last."""
        if limit <= 0:
            return []
        return list(self._history)[-limit:]


STREAM_BUS = StreamBus()


def publish_ingestion_report(report: IngestionReport) -> list[StreamEvent]:
    """Emit real stream events derived from a completed ingestion report.

    Every event maps 1:1 onto a mutation recorded in the report, so consumers
    can never see an event for something that did not happen:

    - ``entity_created`` per id in ``documents_created``
    - ``entity_updated`` per written id that already existed
    - ``edge_created`` once, when edges were written
    - ``entity_deleted`` per id in ``documents_deleted``
    - ``ingestion_completed`` always, with the measured counters

    Args:
        report: The measured outcome of an ingest/update/delete call.

    Returns:
        The events that were published, in order (empty for a dry run).
    """
    events: list[StreamEvent] = []
    if report.dry_run:
        return events
    created = set(report.documents_created)
    for doc_id in report.documents_written:
        events.append(
            STREAM_BUS.emit(
                StreamEventType.ENTITY_CREATED if doc_id in created else StreamEventType.ENTITY_UPDATED,
                graph_id=report.graph_id,
                entity_id=doc_id,
                entity_type="Paper",
                payload={"document": doc_id},
            )
        )
    if report.edges_created:
        events.append(
            STREAM_BUS.emit(
                StreamEventType.EDGE_CREATED,
                graph_id=report.graph_id,
                payload={
                    "edges_created": report.edges_created,
                    "documents": list(report.documents_written),
                },
            )
        )
    for doc_id in report.documents_deleted:
        events.append(
            STREAM_BUS.emit(
                StreamEventType.ENTITY_DELETED,
                graph_id=report.graph_id,
                entity_id=doc_id,
                entity_type="Paper",
                payload={"document": doc_id},
            )
        )
    events.append(
        STREAM_BUS.emit(
            StreamEventType.INGESTION_COMPLETED,
            graph_id=report.graph_id,
            payload={
                "documents_written": report.documents_written,
                "documents_created": report.documents_created,
                "documents_deleted": report.documents_deleted,
                "documents_ingested": report.documents_ingested,
                "documents_skipped": report.documents_skipped,
                "triples_extracted": report.triples_extracted,
                "entities_created": report.entities_created,
                "entities_resolved": report.entities_resolved,
                "edges_created": report.edges_created,
                "duration_ms": report.duration_ms,
            },
        )
    )
    return events
