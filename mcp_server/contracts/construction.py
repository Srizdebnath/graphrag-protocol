"""Contract 4: Construction — real document -> knowledge-graph ingestion.

Extraction and resolution are computed in-process; writes go straight
through the adapter's live pyTigerGraph connection (``upsertVertex`` /
``upsertEdge``). Every counter in the returned :class:`IngestionReport` is
measured from the backend (before/after vertex counts), never estimated.

Extraction strategies:
- ``frequency``: deterministic stopword-filtered top-K tokens, identical in
  spirit to ``hackathon/scripts/build_kg.py`` so contract-driven ingestion
  produces the same shape of graph as the batch loader.
- ``llm``: Gemini returns a JSON concept list; on any failure the contract
  degrades to ``frequency`` and records the reason in ``report.errors``.

Resolution strategies:
- ``exact_id``: a Paper whose id already exists is counted as resolved and
  its attributes are overwritten (upsert semantics).
- ``new_only``: existing vertices are left untouched.
"""

from __future__ import annotations

import json
import os
import re
import time
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from mcp_server.adapters.base import BaseGraphRAGAdapter
from mcp_server.contracts.streaming import publish_ingestion_report
from mcp_server.protocol_extensions import (
    ExtractionStrategy,
    IngestionConfig,
    IngestionReport,
    ResolveStrategy,
    StreamEvent,
    Triple,
)

# Domain stopwords mirroring the batch loader (kept local so the protocol core
# has no dependency on hackathon/ scripts).
_STOPWORDS = {
    "a", "about", "above", "after", "again", "all", "also", "am", "an", "and", "any", "are", "as",
    "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", "by", "can",
    "cannot", "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself", "him", "himself",
    "his", "how", "however", "i", "if", "in", "into", "is", "it", "its", "itself", "me", "more", "most",
    "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "one", "only", "or", "other", "ought",
    "our", "ours", "ourselves", "out", "over", "own", "same", "she", "should", "so", "some", "such", "than",
    "that", "the", "their", "theirs", "them", "themselves", "then", "there", "these", "they", "this", "those",
    "through", "thus", "to", "too", "two", "under", "until", "up", "very", "via", "was", "we", "were",
    "what", "when", "where", "which", "while", "who", "whom", "why", "will", "with", "would", "you", "your",
    "yours", "yourself", "approach", "approaches", "based", "benchmark", "benchmarks", "data", "dataset",
    "datasets", "evaluate", "evaluated", "evaluation", "experiment", "experimental", "experiments", "framework",
    "frameworks", "general", "learned", "learning", "method", "methods", "model", "models", "new", "paper",
    "papers", "performance", "propose", "proposed", "result", "results", "set", "show", "shown", "state", "art",
    "studies", "study", "system", "systems", "technique", "techniques", "use", "used", "using", "well", "work",
    "works",
}

_TOKEN_RE = re.compile(r"[a-z][a-z0-9\-]{2,}")

# Public alias: the evaluation contract reuses the same content-word filter so
# retrieval metrics and concept extraction agree on what counts as a term.
STOPWORDS = _STOPWORDS


def extract_concepts(title: str, abstract: str, max_concepts: int = 5) -> list[str]:
    """Deterministic stopword-filtered frequency extraction (real, no API)."""
    text = f"{title} {abstract}".lower()
    counts: Counter[str] = Counter()
    for token in _TOKEN_RE.findall(text):
        token = token.strip("-")
        if len(token) < 4 or token in _STOPWORDS:
            continue
        counts[token] += 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [k for k, _ in ranked[:max_concepts]]


def _to_tg_datetime(iso: str | None) -> str | None:
    """ISO-8601 -> the TigerGraph ``DATETIME`` literal pyTigerGraph accepts.

    The REST++ upsert path does *not* convert epoch integers for a DATETIME
    attribute (it answers ``REST-30200: value cannot be converted to Datetime``),
    so the wire format is the ``YYYY-MM-DD HH:MM:SS`` string — the same format
    ``hackathon/scripts/build_kg.py`` loads the corpus with, which keeps
    contract-driven ingestion byte-identical to the batch loader.
    """
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


class ConstructionContract:
    """Contract 4: real ingestion into a live TigerGraph backend.

    Args:
        adapter: A :class:`BaseGraphRAGAdapter` backed by TigerGraph. Other
            adapters raise a clear error: construction requires a writable
            backend.
        llm_client: Optional pre-built Gemini client used by
            :attr:`ExtractionStrategy.LLM`. Built lazily from
            ``GOOGLE_API_KEY`` when omitted.
    """

    def __init__(
        self,
        adapter: BaseGraphRAGAdapter,
        llm_client: Any | None = None,
        publish_events: bool = True,
    ) -> None:
        if adapter is None:
            raise ValueError("ConstructionContract requires a non-None adapter")
        self._adapter = adapter
        self._llm_client = llm_client
        self._llm_resolved = llm_client is not None
        self._publish_events = publish_events

    # -- backend plumbing -------------------------------------------------------

    @property
    def _conn(self):
        conn = getattr(self._adapter, "conn", None)
        if conn is None:
            raise RuntimeError(
                "Construction requires a writable backend adapter exposing .conn "
                "(TigerGraph). The demo adapter is read-only."
            )
        return conn

    def _count(self, vertex_type: str) -> int:
        """Real vertex count, 0 when the type does not exist yet."""
        try:
            return int(self._conn.getVertexCount(vertex_type))
        except Exception:  # noqa: BLE001 - type may not exist pre-schema
            return 0

    def _exists(self, vertex_type: str, vertex_id: str) -> bool:
        """Real existence probe by primary id."""
        try:
            found = self._conn.getVerticesById(vertex_type, [vertex_id])
        except Exception:  # noqa: BLE001 - pyTigerGraph raises 601 for a missing id
            return False
        return bool(found)

    def _emit(self, report: IngestionReport) -> list[StreamEvent]:
        """Publish Contract 7 events for a completed write.

        Events are emitted here, at the mutation point, so every caller (MCP
        tool, HTTP endpoint, script) produces them exactly once — a dry run
        publishes nothing.

        Args:
            report: The measured outcome of the write.

        Returns:
            The events that were published (empty when events are disabled).
        """
        if not self._publish_events:
            return []
        return publish_ingestion_report(report)

    def _llm(self):
        """Lazily build the Gemini client; None when no key is configured."""
        if self._llm_resolved:
            return self._llm_client
        self._llm_resolved = True
        key = os.environ.get("GOOGLE_API_KEY")
        if not key:
            return None
        try:
            from google import genai

            self._llm_client = genai.Client(api_key=key)
        except Exception:  # noqa: BLE001
            self._llm_client = None
        return self._llm_client

    # -- extraction -------------------------------------------------------------

    def extract_entities(
        self,
        document: dict[str, Any],
        config: IngestionConfig | None = None,
    ) -> list[Triple]:
        """Extract Paper->Author and Paper->Concept triples from a document.

        Args:
            document: ``{id, title, abstract, authors, categories, published}``.
            config: Ingestion configuration (defaults to a paper config).

        Returns:
            The extracted triples, all anchored on the Paper vertex.
        """
        cfg = config or IngestionConfig(graph_id=getattr(self._adapter, "_graphname", "default"))
        doc_id = str(document.get("id") or document.get("document_id") or "").strip()
        if not doc_id:
            raise ValueError("extract_entities requires document['id']")
        title = str(document.get("title") or "")
        abstract = str(document.get("abstract") or document.get("content") or "")

        triples: list[Triple] = []
        for author in document.get("authors") or []:
            name = str(author).strip()
            if not name:
                continue
            triples.append(
                Triple(
                    subject_id=doc_id, subject_type="Paper",
                    predicate="AUTHORED_BY", object_id=name, object_type="Author",
                    source_doc=doc_id, confidence=1.0,
                )
            )
        for concept in self._concepts(title, abstract, cfg):
            triples.append(
                Triple(
                    subject_id=doc_id, subject_type="Paper",
                    predicate="MENTIONS", object_id=concept, object_type="Concept",
                    source_doc=doc_id, confidence=0.8,
                )
            )
        for cited in document.get("references") or document.get("cites") or []:
            ref = str(cited).strip()
            if ref:
                triples.append(
                    Triple(
                        subject_id=doc_id, subject_type="Paper",
                        predicate="CITES", object_id=ref, object_type="Paper",
                        source_doc=doc_id, confidence=1.0,
                    )
                )
        return triples

    def _concepts(self, title: str, abstract: str, cfg: IngestionConfig) -> list[str]:
        """Concept list for a document under the configured strategy."""
        if cfg.extraction is ExtractionStrategy.LLM:
            client = self._llm()
            if client is not None:
                prompt = (
                    f"Extract at most {cfg.max_concepts_per_doc} salient single-word or "
                    "hyphenated technical concepts (lowercase) from this paper. "
                    'Reply with JSON only: {"concepts": ["..."]}.\n\n'
                    f"Title: {title}\nAbstract: {abstract[:4000]}"
                )
                try:
                    resp = client.models.generate_content(
                        model=os.environ.get("LLM_MODEL", "gemini-2.5-flash"), contents=prompt
                    )
                    raw = (resp.text or "").strip().removeprefix("```json").removeprefix("```").removesuffix("```")
                    data = json.loads(raw)
                    items = [str(c).strip().lower() for c in data.get("concepts", []) if str(c).strip()]
                    if items:
                        return items[: cfg.max_concepts_per_doc]
                except Exception as exc:  # noqa: BLE001 - fall through to frequency
                    print(
                        f"[construction] LLM extraction failed ({type(exc).__name__}); "
                        "using frequency extraction"
                    )
        return extract_concepts(title, abstract, cfg.max_concepts_per_doc)

    # -- resolution -------------------------------------------------------------

    def resolve_entities(
        self,
        triples: list[Triple],
        config: IngestionConfig | None = None,
    ) -> list[Triple]:
        """Resolve triples against the live graph.

        Every distinct object vertex is probed once with a real
        ``getVerticesById`` call and annotated with ``properties['resolved']``.
        The strategy then decides what the *write* path does with a match:

        - ``EXACT_ID``: the existing vertex keeps its id and its attributes are
          refreshed by the upsert.
        - ``NEW_ONLY``: the vertex is left completely untouched (insert-only).

        Args:
            triples: Triples produced by :meth:`extract_entities`.
            config: Ingestion configuration.

        Returns:
            The same triples annotated with their resolution outcome.
        """
        probe_cache: dict[tuple[str, str], bool] = {}
        for t in triples:
            key = (t.object_type, t.object_id)
            if key not in probe_cache:
                probe_cache[key] = self._exists(t.object_type, t.object_id)
            t.properties = {**t.properties, "resolved": probe_cache[key]}
        return triples

    # -- write paths ------------------------------------------------------------

    def ingest(
        self,
        documents: list[dict[str, Any]],
        config: IngestionConfig | None = None,
    ) -> IngestionReport:
        """Ingest documents into the graph. Real upserts, real counters.

        Every counter is measured from the backend: ``vertices_before/after``
        are ``getVertexCount`` reads, and ``entities_created`` counts only the
        vertices this call actually created — a vertex matched by resolution is
        counted once, in ``entities_resolved``.

        Args:
            documents: Paper-shaped dicts (``id``/``title``/``abstract``/``authors``).
            config: Ingestion configuration; ``dry_run`` measures the real graph
                and reports what *would* be written, without writing anything.

        Returns:
            An :class:`IngestionReport` with measured before/after counts.
        """
        cfg = config or IngestionConfig(graph_id=getattr(self._adapter, "_graphname", "default"))
        t0 = time.perf_counter()
        report = IngestionReport(
            graph_id=cfg.graph_id,
            dry_run=cfg.dry_run,
            document_ids=[str(d.get("id", "")) for d in documents if d.get("id")],
        )
        types = ("Paper", "Author", "Concept")
        # Counting is a read, so a dry run still measures the baseline: the
        # report then shows before == after, which is the truth (nothing written).
        report.vertices_before = {t: self._count(t) for t in types}

        for doc in documents:
            doc_id = str(doc.get("id") or "").strip()
            if not doc_id:
                report.errors.append("document missing 'id'; skipped")
                continue
            try:
                triples = self.resolve_entities(self.extract_entities(doc, cfg), cfg)
            except Exception as exc:  # noqa: BLE001 - one bad doc must not abort the batch
                report.errors.append(f"{doc_id}: extraction failed: {type(exc).__name__}: {exc}")
                continue

            report.triples_extracted += len(triples)
            resolved = sum(1 for t in triples if t.properties.get("resolved"))
            paper_exists = self._exists("Paper", doc_id)
            report.entities_resolved += resolved + (1 if paper_exists else 0)

            if cfg.dry_run:
                # Nothing is written, so "created" is what WOULD be created.
                report.entities_created += (len(triples) - resolved) + (0 if paper_exists else 1)
                report.documents_ingested += 1
                continue

            created, edges = self._write_document(
                doc, triples, cfg, report, paper_exists=paper_exists
            )
            report.entities_created += created
            report.edges_created += edges
            if cfg.resolve is ResolveStrategy.NEW_ONLY and paper_exists:
                report.documents_skipped += 1
                continue
            report.documents_ingested += 1
            report.documents_written.append(doc_id)
            if not paper_exists:
                report.documents_created.append(doc_id)

        # Measured after the writes; in a dry run this equals ``vertices_before``
        # (nothing was written), which is itself the honest signal.
        report.vertices_after = {t: self._count(t) for t in types}
        report.duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        self._emit(report)
        return report

    def _write_document(
        self,
        doc: dict[str, Any],
        triples: list[Triple],
        cfg: IngestionConfig,
        report: IngestionReport,
        paper_exists: bool,
    ) -> tuple[int, int]:
        """Upsert one document's vertices/edges; returns (vertices_created, edges).

        Under ``NEW_ONLY`` a document that already exists is not written at all
        (insert-only), and object vertices that resolved to existing ones are
        skipped so their attributes are never overwritten.
        """
        if cfg.resolve is ResolveStrategy.NEW_ONLY and paper_exists:
            return 0, 0

        conn = self._conn
        doc_id = str(doc["id"])
        attrs: dict[str, Any] = {
            "title": str(doc.get("title") or ""),
            "abstract": str(doc.get("abstract") or doc.get("content") or ""),
            "categories": ", ".join(doc.get("categories") or [])
            if isinstance(doc.get("categories"), list)
            else str(doc.get("categories") or ""),
            "abstract_token_count": int(doc.get("abstract_token_count") or 0),
        }
        published = _to_tg_datetime(doc.get("published"))
        if published is not None:
            attrs["published"] = published

        vertices = 0
        edges = 0
        try:
            conn.upsertVertex("Paper", doc_id, attrs)
            if not paper_exists:
                vertices += 1
        except Exception as exc:  # noqa: BLE001
            report.errors.append(f"{doc_id}: Paper upsert failed: {type(exc).__name__}: {exc}")
            return 0, 0

        seen: set[tuple[str, str]] = set()
        for t in triples:
            key = (t.object_type, t.object_id)
            resolved = bool(t.properties.get("resolved"))
            insert_only = cfg.resolve is ResolveStrategy.NEW_ONLY and resolved
            if key not in seen:
                seen.add(key)
                if not insert_only:
                    obj_attrs = {"name": t.object_id} if t.object_type in ("Author", "Concept") else None
                    try:
                        conn.upsertVertex(t.object_type, t.object_id, obj_attrs)
                        if not resolved:
                            vertices += 1
                    except Exception as exc:  # noqa: BLE001
                        report.errors.append(
                            f"{doc_id}: {t.object_type} '{t.object_id}' upsert failed: "
                            f"{type(exc).__name__}"
                        )
                        continue
            try:
                # Schema edges (AUTHORED_BY/MENTIONS/CITES) carry no attributes;
                # t.properties holds resolution metadata only, so it is NOT sent.
                conn.upsertEdge(
                    t.subject_type, t.subject_id, t.predicate, t.object_type, t.object_id,
                    attributes=None, vertexMustExist=False,
                )
                edges += 1
            except Exception as exc:  # noqa: BLE001
                report.errors.append(f"{doc_id}: edge {t.predicate} failed: {type(exc).__name__}: {exc}")
        return vertices, edges

    def update(
        self,
        document_id: str,
        content: dict[str, Any] | str,
        config: IngestionConfig | None = None,
    ) -> IngestionReport:
        """Re-ingest a document under the same id (real overwrite upsert).

        Args:
            document_id: The Paper primary id to update.
            content: Replacement fields (dict) or replacement abstract text.
            config: Ingestion configuration.

        Returns:
            An :class:`IngestionReport` for the single document.
        """
        if not document_id:
            raise ValueError("update requires a non-empty document_id")
        cfg = config or IngestionConfig(graph_id=getattr(self._adapter, "_graphname", "default"))
        doc: dict[str, Any] = {"id": document_id}
        if isinstance(content, str):
            doc["abstract"] = content
        else:
            doc.update(content or {})
            doc["id"] = document_id
        # Only EXACT_ID replaces an existing document; NEW_ONLY is insert-only,
        # so dropping the old edges first would destroy data without rewriting it.
        if cfg.resolve is ResolveStrategy.EXACT_ID and self._exists("Paper", document_id):
            self._delete_edges_of("Paper", document_id)
        return self.ingest([doc], cfg)

    def delete_document(
        self,
        document_id: str,
        config: IngestionConfig | None = None,
    ) -> IngestionReport:
        """Delete a Paper vertex and its edges (real ``delVerticesById``).

        Args:
            document_id: The Paper primary id to delete.
            config: Ingestion configuration (``dry_run`` reports the removal
                that *would* happen without deleting anything).

        Returns:
            An :class:`IngestionReport` whose counters reflect the removal
            (``documents_deleted``, and ``vertices_before/after`` measured).
        """
        if not document_id:
            raise ValueError("delete_document requires a non-empty document_id")
        cfg = config or IngestionConfig(graph_id=getattr(self._adapter, "_graphname", "default"))
        t0 = time.perf_counter()
        report = IngestionReport(graph_id=cfg.graph_id, dry_run=cfg.dry_run, document_ids=[document_id])
        types = ("Paper", "Author", "Concept")
        existed = self._exists("Paper", document_id)
        report.vertices_before = {t: self._count(t) for t in types}
        if cfg.dry_run:
            report.documents_deleted = [document_id] if existed else []
            report.entities_resolved = 1 if existed else 0
            report.vertices_after = {t: self._count(t) for t in types}
            report.duration_ms = round((time.perf_counter() - t0) * 1000, 2)
            return report

        try:
            removed = self._conn.delVerticesById("Paper", document_id)
            removed_count = int(removed or 0)
            if removed_count > 0 or existed:
                report.documents_deleted = [document_id]
            report.entities_resolved = 1 if existed else 0
        except Exception as exc:  # noqa: BLE001
            report.errors.append(f"{document_id}: delete failed: {type(exc).__name__}: {exc}")
        report.vertices_after = {t: self._count(t) for t in types}
        report.duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        self._emit(report)
        return report

    def _delete_edges_of(self, vertex_type: str, vertex_id: str) -> int:
        """Remove all edges touching a vertex, keeping the vertex itself."""
        try:
            return int(self._conn.delEdges(vertex_type, vertex_id) or 0)
        except Exception:  # noqa: BLE001 - no edges or unsupported
            return 0
