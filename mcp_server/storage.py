"""Persistent storage for GraphRAG Protocol: jobs, event log, and cache state.

Replaces ephemeral in-memory dicts with a real, zero-mock SQLite database
stored at `.graphrag_store.sqlite3`. Survives server restarts, handles concurrent
reads/writes with WAL mode, and provides atomic transactions.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_DEFAULT_DB_PATH = os.environ.get(
    "GRAPHRAG_DB_PATH",
    str(Path(__file__).resolve().parent.parent / ".graphrag_store.sqlite3"),
)


class PersistentStorage:
    """Thread-safe SQLite storage for jobs, stream events, and cached results."""

    _instance: PersistentStorage | None = None
    _lock = threading.Lock()

    def __init__(self, db_path: str = _DEFAULT_DB_PATH) -> None:
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    @classmethod
    def get_instance(cls, db_path: str = _DEFAULT_DB_PATH) -> PersistentStorage:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(db_path)
            return cls._instance

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            self._local.conn = conn
        return self._local.conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        with conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    graph_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    document_count INTEGER DEFAULT 0,
                    report_json TEXT,
                    error TEXT
                );

                CREATE TABLE IF NOT EXISTS event_log (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    graph_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    entity_id TEXT,
                    entity_type TEXT,
                    payload_json TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_event_timestamp ON event_log(timestamp);
                CREATE INDEX IF NOT EXISTS idx_event_type ON event_log(event_type);

                CREATE TABLE IF NOT EXISTS query_cache (
                    cache_key TEXT PRIMARY KEY,
                    tool_name TEXT NOT NULL,
                    graph_id TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    ttl_seconds REAL NOT NULL,
                    result_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_cache_created ON query_cache(created_at);
                """
            )

    # ------------------------------------------------------------------
    # Job Persistence
    # ------------------------------------------------------------------

    def save_job(
        self,
        job_id: str,
        status: str,
        graph_id: str,
        document_count: int = 0,
        report: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        with conn:
            conn.execute(
                """
                INSERT INTO jobs (job_id, status, graph_id, created_at, updated_at, document_count, report_json, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    status=excluded.status,
                    updated_at=excluded.updated_at,
                    document_count=excluded.document_count,
                    report_json=COALESCE(excluded.report_json, jobs.report_json),
                    error=COALESCE(excluded.error, jobs.error);
                """,
                (
                    job_id,
                    status,
                    graph_id,
                    now,
                    now,
                    document_count,
                    json.dumps(report) if report else None,
                    error,
                ),
            )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT job_id, status, graph_id, created_at, updated_at, document_count, report_json, error
            FROM jobs WHERE job_id = ?
            """,
            (job_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "job_id": row[0],
            "status": row[1],
            "graph_id": row[2],
            "created_at": row[3],
            "updated_at": row[4],
            "document_count": row[5],
            "report": json.loads(row[6]) if row[6] else None,
            "error": row[7],
        }

    # ------------------------------------------------------------------
    # Event Log Persistence (Real event replay)
    # ------------------------------------------------------------------

    def append_event(
        self,
        event_id: str,
        event_type: str,
        graph_id: str,
        timestamp: str,
        entity_id: str | None = None,
        entity_type: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        conn = self._get_conn()
        with conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO event_log (event_id, event_type, graph_id, timestamp, entity_id, entity_type, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    event_type,
                    graph_id,
                    timestamp,
                    entity_id,
                    entity_type,
                    json.dumps(payload or {}),
                ),
            )

    def get_events(
        self,
        limit: int = 50,
        event_types: list[str] | None = None,
        graph_id: str | None = None,
        since_timestamp: str | None = None,
    ) -> list[dict[str, Any]]:
        conn = self._get_conn()
        cursor = conn.cursor()
        clauses = []
        params: list[Any] = []

        if event_types:
            placeholders = ",".join("?" for _ in event_types)
            clauses.append(f"event_type IN ({placeholders})")
            params.extend(event_types)
        if graph_id:
            clauses.append("graph_id = ?")
            params.append(graph_id)
        if since_timestamp:
            clauses.append("timestamp >= ?")
            params.append(since_timestamp)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"""
            SELECT event_id, event_type, graph_id, timestamp, entity_id, entity_type, payload_json
            FROM event_log
            {where}
            ORDER BY timestamp DESC
            LIMIT ?
        """
        params.append(max(1, min(limit, 1000)))
        cursor.execute(query, params)
        rows = cursor.fetchall()

        events = []
        for r in rows:
            events.append(
                {
                    "event_id": r[0],
                    "event_type": r[1],
                    "graph_id": r[2],
                    "timestamp": r[3],
                    "entity_id": r[4],
                    "entity_type": r[5],
                    "payload": json.loads(r[6]) if r[6] else {},
                }
            )
        return events

    # ------------------------------------------------------------------
    # Query Result Cache Persistence
    # ------------------------------------------------------------------

    def cache_get(self, cache_key: str) -> dict[str, Any] | None:
        import time

        now = time.monotonic()
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT result_json, created_at, ttl_seconds FROM query_cache WHERE cache_key = ?
            """,
            (cache_key,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        res_json, created_at, ttl_seconds = row
        if now - created_at > ttl_seconds:
            self.cache_delete(cache_key)
            return None
        try:
            return json.loads(res_json)
        except Exception:  # noqa: BLE001
            return None

    def cache_set(
        self, cache_key: str, tool_name: str, graph_id: str, result: dict[str, Any], ttl_seconds: float = 300.0
    ) -> None:
        import time

        now = time.monotonic()
        conn = self._get_conn()
        with conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO query_cache (cache_key, tool_name, graph_id, created_at, ttl_seconds, result_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (cache_key, tool_name, graph_id, now, ttl_seconds, json.dumps(result)),
            )

    def cache_delete(self, cache_key: str) -> None:
        conn = self._get_conn()
        with conn:
            conn.execute("DELETE FROM query_cache WHERE cache_key = ?", (cache_key,))

    def cache_clear_for_graph(self, graph_id: str) -> int:
        conn = self._get_conn()
        with conn:
            cur = conn.execute("DELETE FROM query_cache WHERE graph_id = ?", (graph_id,))
            return cur.rowcount
