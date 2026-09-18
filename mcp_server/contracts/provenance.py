"""Contract 5: Provenance.

Wraps a backend adapter's provenance primitives and adds self-contained
logic for auditing provenance completeness — the ratio of cited entities
to entities examined during traversal — plus a human-readable
recommendation.
"""

from __future__ import annotations

from mcp_server.adapters.base import BaseGraphRAGAdapter
from mcp_server.protocol import (
    Provenance,
    SubgraphContext,
    TraversalStep,
)


class ProvenanceContract:
    """Contract 5: citation tracing and trajectory auditing.

    Args:
        adapter: The backend adapter to interrogate. Must not be ``None``.
    """

    def __init__(self, adapter: BaseGraphRAGAdapter) -> None:
        """Initialize the contract.

        Args:
            adapter: A :class:`BaseGraphRAGAdapter` instance.

        Raises:
            ValueError: If ``adapter`` is ``None``.
        """
        if adapter is None:
            raise ValueError("ProvenanceContract requires a non-None adapter")
        self._adapter: BaseGraphRAGAdapter = adapter

    def trace_citation(self, fact_id_or_entity_id: str) -> Provenance:
        """Trace the full citation chain for a fact or entity.

        Delegates to the adapter's provenance-construction logic. If the
        adapter exposes a dedicated ``trace_citation`` method, it is used
        with the given identifier; otherwise the adapter's generic
        :meth:`BaseGraphRAGAdapter.get_provenance` is invoked.

        Args:
            fact_id_or_entity_id: The fact or entity to trace.

        Returns:
            A :class:`Provenance` describing the citation chain.

        Raises:
            ValueError: If the identifier is empty.
        """
        identifier = (fact_id_or_entity_id or "").strip()
        if not identifier:
            raise ValueError("trace_citation requires a non-empty identifier")

        trace = getattr(self._adapter, "trace_citation", None)
        if callable(trace):
            raw = trace(identifier)
            return self._coerce_provenance(raw)

        context = self._context_for_identifier(identifier)
        return self._adapter.get_provenance(context)

    def get_traversal_trajectory(
        self, query_id: str | None = None, context: SubgraphContext | None = None
    ) -> list[TraversalStep]:
        """Return the traversal log for a query or a given context.

        Args:
            query_id: Optional query identifier; used to look up a
                previously built provenance if the adapter supports it.
            context: Optional subgraph context whose provenance is used.

        Returns:
            An ordered list of :class:`TraversalStep`.

        Raises:
            ValueError: If neither ``query_id`` nor ``context`` is provided.
        """
        if context is not None:
            return list(context.provenance.traversal_log)

        if query_id:
            get_traj = getattr(self._adapter, "get_traversal_trajectory", None)
            if callable(get_traj):
                raw = get_traj(query_id)
                return [self._coerce_step(s) for s in self._iterable(raw)]

            provenance = self._provenance_for_query(query_id)
            return list(provenance.traversal_log)

        raise ValueError(
            "get_traversal_trajectory requires either a query_id or a context"
        )

    def get_source_documents(self, entity_id: str) -> list[str]:
        """Return the source documents supporting an entity.

        Args:
            entity_id: The entity whose source documents are requested.

        Returns:
            A list of source-document identifiers (deduplicated).

        Raises:
            ValueError: If the entity id is empty.
        """
        identifier = (entity_id or "").strip()
        if not identifier:
            raise ValueError("get_source_documents requires a non-empty entity id")

        get_docs = getattr(self._adapter, "get_source_documents", None)
        if callable(get_docs):
            raw = get_docs(identifier)
            docs = [str(d) for d in self._iterable(raw)]
            return self._dedup(docs)

        context = self._context_for_identifier(identifier)
        return list(self._adapter.get_provenance(context).source_documents)

    def audit_provenance_completeness(
        self, provenance: Provenance
    ) -> dict[str, float | str]:
        """Audit the completeness of a provenance trail.

        Computes the trajectory-completeness score: the ratio of entities
        actually cited to the total entities examined during traversal.
        A score is derived both from the ``visited_not_cited`` list and the
        ``total_entities_examined`` counter.

        Args:
            provenance: The :class:`Provenance` to audit.

        Returns:
            A dict with ``completeness`` (float in [0, 1]), plus a
            ``recommendation`` string and raw counts for transparency.
        """
        total_examined = provenance.total_entities_examined
        cited_ids = {
            step.entity
            for step in provenance.traversal_log
            if step.entity not in (provenance.visited_not_cited or [])
        }
        cited_count = len(cited_ids)

        if total_examined <= 0:
            # Prefer the derived cited count when the counter is missing.
            examined = max(total_examined, cited_count)
            if examined == 0:
                score = 1.0
            else:
                score = cited_count / examined
        else:
            score = cited_count / total_examined

        score = max(0.0, min(1.0, float(score)))
        recommendation = self._recommendation(score, cited_count, total_examined)

        return {
            "completeness": round(score, 4),
            "cited_entities": cited_count,
            "total_entities_examined": total_examined,
            "visited_not_cited": len(provenance.visited_not_cited or []),
            "recommendation": recommendation,
        }

    # -- helpers ----------------------------------------------------------------

    @staticmethod
    def _recommendation(score: float, cited: int, examined: int) -> str:
        """Build a human-readable recommendation from a completeness score.

        Args:
            score: The completeness score in [0, 1].
            cited: Number of cited entities.
            examined: Total entities examined.

        Returns:
            A recommendation string.
        """
        if score >= 0.9:
            return (
                "Complete: nearly all examined entities are reflected in the "
                "answer; high confidence in the retrieval trajectory."
            )
        if score >= 0.7:
            return (
                "Partial: a few examined entities were pruned from the final "
                "context; consider re-running with a higher top_k or depth."
            )
        return (
            f"Low completeness ({cited}/{examined} examined entities cited). "
            "Re-run with relaxed pruning or verify the traversal seeds."
        )

    def _context_for_identifier(self, identifier: str) -> SubgraphContext:
        """Build a minimal context so we can derive provenance for an id.

        Args:
            identifier: The entity/fact identifier.

        Returns:
            A :class:`SubgraphContext` centered on that identifier.
        """
        from mcp_server.protocol import Provenance, RetrievalMetrics

        empty_prov = Provenance(backend="unknown")
        empty_metrics = RetrievalMetrics()
        return SubgraphContext(
            operation="provenance",
            query={"identifier": identifier},
            provenance=empty_prov,
            metrics=empty_metrics,
        )

    def _provenance_for_query(self, query_id: str) -> Provenance:
        """Resolve provenance for a query id via the adapter if possible.

        Args:
            query_id: The query identifier.

        Returns:
            A :class:`Provenance`; an empty one if the adapter cannot
            resolve it.
        """
        get_prov = getattr(self._adapter, "get_provenance_for_query", None)
        if callable(get_prov):
            raw = get_prov(query_id)
            if raw is not None:
                return self._coerce_provenance(raw)
        return Provenance(backend="unknown")

    @staticmethod
    def _coerce_provenance(raw: Provenance | dict | None) -> Provenance:
        """Coerce raw adapter output into a :class:`Provenance`.

        Args:
            raw: A Provenance, its dict form, or ``None``.

        Returns:
            A :class:`Provenance`; an empty one for ``None``.
        """
        if isinstance(raw, Provenance):
            return raw
        if isinstance(raw, dict):
            return Provenance(**raw)
        if raw is None:
            return Provenance(backend="unknown")
        raise TypeError(f"Unsupported provenance type: {type(raw).__name__}")

    @staticmethod
    def _coerce_step(raw: TraversalStep | dict) -> TraversalStep:
        """Coerce a single traversal step.

        Args:
            raw: A :class:`TraversalStep` or its dict form.

        Returns:
            A :class:`TraversalStep`.
        """
        if isinstance(raw, TraversalStep):
            return raw
        if isinstance(raw, dict):
            return TraversalStep(**raw)
        raise TypeError(f"Unsupported traversal step type: {type(raw).__name__}")

    @staticmethod
    def _iterable(raw: object) -> list:
        """Coerce raw adapter output into a list.

        Args:
            raw: A list/tuple, a single object, or ``None``.

        Returns:
            A list of items.
        """
        if raw is None:
            return []
        if isinstance(raw, (list, tuple)):
            return list(raw)
        return [raw]

    @staticmethod
    def _dedup(items: list[str]) -> list[str]:
        """Deduplicate while preserving order.

        Args:
            items: Source list.

        Returns:
            Order-preserving deduplicated list.
        """
        seen: set[str] = set()
        out: list[str] = []
        for item in items:
            if item not in seen:
                seen.add(item)
                out.append(item)
        return out
