"""Contract 17: Batch Execution — parallel fan-out of multiple tool calls.

Allows clients (e.g. Claude Desktop, LangGraph) to execute up to 25 tool operations
in a single round-trip, avoiding high latency from sequential queries.
"""

from __future__ import annotations

import concurrent.futures
import time
from collections.abc import Callable
from typing import Any


class BatchContract:
    """Contract 17: concurrent batch execution of protocol operations."""

    MAX_BATCH_SIZE = 25

    def __init__(self, tool_executor: Callable[[str, dict[str, Any]], Any]) -> None:
        """Args:

        tool_executor: Callable ``(tool_name, arguments) -> result`` that executes a tool.
        """
        self._executor = tool_executor

    def execute_batch(self, calls: list[dict[str, Any]]) -> dict[str, Any]:
        """Execute a batch of tool calls concurrently.

        Args:
            calls: List of dicts, each with ``tool`` (str) and ``arguments`` (dict).

        Returns:
            Dict with ``total``, ``successful``, ``failed``, ``duration_ms``, and ``results`` list.
        """
        if not calls:
            return {"total": 0, "successful": 0, "failed": 0, "duration_ms": 0.0, "results": []}

        if len(calls) > self.MAX_BATCH_SIZE:
            raise ValueError(f"Batch size exceeds maximum limit of {self.MAX_BATCH_SIZE} calls")

        t0 = time.perf_counter()
        results: list[dict[str, Any] | None] = [None] * len(calls)

        def _run_single(idx: int, call: dict[str, Any]) -> tuple[int, dict[str, Any]]:
            tool_name = str(call.get("tool") or call.get("tool_name") or "").strip()
            args = call.get("arguments") or call.get("args") or {}
            single_t0 = time.perf_counter()

            if not tool_name:
                return idx, {
                    "tool": tool_name,
                    "status": "error",
                    "error": "Missing 'tool' name in batch call item",
                    "latency_ms": 0.0,
                }

            try:
                out = self._executor(tool_name, args)
                lat = round((time.perf_counter() - single_t0) * 1000, 2)
                return idx, {
                    "tool": tool_name,
                    "status": "success",
                    "result": out,
                    "latency_ms": lat,
                }
            except Exception as exc:  # noqa: BLE001
                lat = round((time.perf_counter() - single_t0) * 1000, 2)
                return idx, {
                    "tool": tool_name,
                    "status": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                    "latency_ms": lat,
                }

        max_workers = min(8, len(calls))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(_run_single, i, call) for i, call in enumerate(calls)]
            for future in concurrent.futures.as_completed(futures):
                idx, outcome = future.result()
                results[idx] = outcome

        successful = sum(1 for r in results if r and r.get("status") == "success")
        failed = len(calls) - successful
        duration_ms = round((time.perf_counter() - t0) * 1000, 2)

        return {
            "total": len(calls),
            "successful": successful,
            "failed": failed,
            "duration_ms": duration_ms,
            "results": results,
        }
