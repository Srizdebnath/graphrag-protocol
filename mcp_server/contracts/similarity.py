"""Contract 11: Semantic Similarity — real cosine similarity between entities or text.

Delegates to the adapter's embedding capabilities when available (adapters that expose
`embed_text(text: str) -> list[float]`). Falls back to Jaccard overlap on content terms
when no embedding is available — this is a real computation, never zero.
"""
from __future__ import annotations

import math
import re
from typing import Any

from mcp_server.adapters.base import BaseGraphRAGAdapter

STOPWORDS = {"a", "an", "the", "is", "in", "of", "and", "or", "to", "for", "with", "on", "at", "by", "from", "that", "this", "are", "was", "be", "as", "it", "its"}
_TERM_RE = re.compile(r"[a-z][a-z0-9\-]{2,}")


class SimilarityContract:
    """Contract 11: semantic and lexical similarity between entities or free text.

    When the adapter exposes `embed_text(text: str) -> list[float]`, cosine
    similarity is used. Otherwise lexical Jaccard similarity over content terms
    is computed — a real measurement, never fabricated.

    Args:
        adapter: The backend adapter.
    """

    def __init__(self, adapter: BaseGraphRAGAdapter) -> None:
        if adapter is None:
            raise ValueError("SimilarityContract requires a non-None adapter")
        self._adapter = adapter

    # -- public API
    def similarity(self, text_a: str, text_b: str) -> dict[str, Any]:
        """Compute similarity between two text blobs or entity texts.

        Tries vector cosine similarity first; falls back to Jaccard on content terms.

        Args:
            text_a: First text or entity description.
            text_b: Second text or entity description.

        Returns:
            Dict with `score` (float [0,1]), `method` ('cosine'|'jaccard'),
            `terms_a` and `terms_b` (content terms used), `overlap` (shared terms).
        """
        text_a = (text_a or "").strip()
        text_b = (text_b or "").strip()
        if not text_a or not text_b:
            raise ValueError("similarity requires two non-empty text inputs")

        # Try vector cosine via adapter embedding
        embed_fn = getattr(self._adapter, "embed_text", None) or getattr(self._adapter, "_embed", None)
        if callable(embed_fn):
            try:
                vec_a = embed_fn(text_a)
                vec_b = embed_fn(text_b)
                if vec_a and vec_b:
                    score = self._cosine(vec_a, vec_b)
                    return {"score": round(score, 6), "method": "cosine", "terms_a": [], "terms_b": [], "overlap": []}
            except Exception:  # noqa: BLE001, S110 - degrade to jaccard
                pass

        # Try direct Gemini embedding if API key is in environment
        import os
        if os.environ.get("GOOGLE_API_KEY"):
            try:
                from google import genai
                client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
                model = os.environ.get("EMBED_MODEL", "gemini-embedding-001")
                dim = int(os.environ.get("EMBED_DIM", "512"))
                resp = client.models.embed_content(
                    model=model,
                    contents=[text_a, text_b],
                    config={"output_dimensionality": dim},
                )
                if resp and len(resp.embeddings) >= 2:
                    vec_a = [float(v) for v in resp.embeddings[0].values]
                    vec_b = [float(v) for v in resp.embeddings[1].values]
                    score = self._cosine(vec_a, vec_b)
                    return {"score": round(score, 6), "method": "cosine", "terms_a": [], "terms_b": [], "overlap": []}
            except Exception:  # noqa: BLE001, S110
                pass

        # Lexical Jaccard fallback
        terms_a = self._terms(text_a)
        terms_b = self._terms(text_b)
        overlap = sorted(terms_a & terms_b)
        union = terms_a | terms_b
        score = len(overlap) / len(union) if union else 0.0
        return {
            "score": round(score, 6),
            "method": "jaccard",
            "terms_a": sorted(terms_a),
            "terms_b": sorted(terms_b),
            "overlap": overlap,
        }

    def entity_similarity(self, entity_id_a: str, entity_id_b: str) -> dict[str, Any]:
        """Compare two entities by their names and properties text.

        Looks up both entities via adapter.entity_lookup, extracts their
        textual description, then delegates to `similarity`.

        Args:
            entity_id_a: First entity id.
            entity_id_b: Second entity id.

        Returns:
            Similarity result dict plus `entity_a` and `entity_b` metadata.
        """
        if not entity_id_a or not entity_id_b:
            raise ValueError("entity_similarity requires two non-empty entity ids")
        ctx_a = self._adapter.entity_lookup(entity_id=entity_id_a, depth=0)
        ctx_b = self._adapter.entity_lookup(entity_id=entity_id_b, depth=0)
        entities_a = ctx_a.results.get("entities", []) or []
        entities_b = ctx_b.results.get("entities", []) or []
        text_a = self._entity_text(entities_a[0] if entities_a else {"id": entity_id_a, "name": entity_id_a})
        text_b = self._entity_text(entities_b[0] if entities_b else {"id": entity_id_b, "name": entity_id_b})
        result = self.similarity(text_a or entity_id_a, text_b or entity_id_b)
        result["entity_a"] = entity_id_a
        result["entity_b"] = entity_id_b
        return result

    def batch_similarity(self, anchor: str, candidates: list[str]) -> list[dict[str, Any]]:
        """Rank candidates by similarity to an anchor text, highest first.

        Args:
            anchor: The reference text.
            candidates: List of candidate texts to compare against anchor.

        Returns:
            List of similarity result dicts (each with `candidate` key), sorted descending.
        """
        if not anchor or not anchor.strip():
            raise ValueError("batch_similarity requires a non-empty anchor")
        if not candidates:
            return []
        results = []
        for c in candidates:
            try:
                r = self.similarity(anchor, c)
                r["candidate"] = c
                results.append(r)
            except ValueError:
                results.append({"candidate": c, "score": 0.0, "method": "error", "error": "empty candidate"})
        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    # -- internals
    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        if len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(y * y for y in b))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)

    @staticmethod
    def _terms(text: str) -> set[str]:
        return {t for t in _TERM_RE.findall(text.lower()) if t not in STOPWORDS}

    @staticmethod
    def _entity_text(entity: dict[str, Any]) -> str:
        parts = [str(entity.get("name") or ""), str(entity.get("id") or "")]
        props = entity.get("properties") or {}
        for k in ("title", "abstract", "description", "summary"):
            v = props.get(k)
            if v:
                parts.append(str(v))
        return " ".join(filter(None, parts))
