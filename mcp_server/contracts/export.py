"""Contract 16: Subgraph Export — portable graph serialization.

Exports a SubgraphContext into standard graph interchange formats:
- ``graphml``: XML GraphML format for Gephi, Cytoscape, NetworkX.
- ``cypher``: OpenCypher CREATE script for Neo4j / Memgraph import.
- ``json_ld``: W3C JSON-LD linked data representation.
- ``rdf_turtle``: W3C Turtle RDF triple format.
"""

from __future__ import annotations

import json
from typing import Any
from xml.sax import saxutils

from mcp_server.adapters.base import BaseGraphRAGAdapter
from mcp_server.protocol import SubgraphContext


class ExportContract:
    """Contract 16: export SubgraphContext into portable graph formats."""

    SUPPORTED_FORMATS = ("graphml", "cypher", "json_ld", "rdf_turtle")

    def __init__(self, adapter: BaseGraphRAGAdapter) -> None:
        if adapter is None:
            raise ValueError("ExportContract requires a non-None adapter")
        self._adapter = adapter

    def export(self, context: SubgraphContext, format: str = "graphml") -> dict[str, Any]:
        """Export a SubgraphContext to the specified format."""
        if context is None:
            raise ValueError("export requires a SubgraphContext")
        fmt = format.lower().strip().replace("-", "_")
        if fmt not in self.SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported format {format!r}. Supported formats: {list(self.SUPPORTED_FORMATS)}"
            )

        entities = context.results.get("entities") or []
        relationships = context.results.get("relationships") or []

        if fmt == "graphml":
            content = self._to_graphml(entities, relationships)
            mime = "application/xml"
        elif fmt == "cypher":
            content = self._to_cypher(entities, relationships)
            mime = "text/plain"
        elif fmt == "json_ld":
            content = self._to_json_ld(entities, relationships)
            mime = "application/ld+json"
        elif fmt == "rdf_turtle":
            content = self._to_rdf_turtle(entities, relationships)
            mime = "text/turtle"
        else:
            raise ValueError(f"Unknown format: {fmt}")

        return {
            "format": fmt,
            "mime_type": mime,
            "node_count": len(entities),
            "edge_count": len(relationships),
            "content": content,
        }

    # ------------------------------------------------------------------
    # Format Serializers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_graphml(entities: list[dict[str, Any]], relationships: list[dict[str, Any]]) -> str:
        esc = saxutils.escape
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<graphml xmlns="http://graphml.graphdrawing.org/xmlns"',
            '         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
            '         xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">',
            '  <key id="name" for="node" attr.name="name" attr.type="string"/>',
            '  <key id="type" for="node" attr.name="type" attr.type="string"/>',
            '  <key id="score" for="node" attr.name="score" attr.type="double"/>',
            '  <key id="weight" for="edge" attr.name="weight" attr.type="double"/>',
            '  <key id="type" for="edge" attr.name="type" attr.type="string"/>',
            '  <graph id="G" edgedefault="directed">',
        ]

        for e in entities:
            eid = esc(str(e.get("id") or ""))
            name = esc(str(e.get("name") or eid))
            etype = esc(str(e.get("type") or "Node"))
            score = float(e.get("relevance_score") or 0.0)
            lines.append(f'    <node id="{eid}">')
            lines.append(f'      <data key="name">{name}</data>')
            lines.append(f'      <data key="type">{etype}</data>')
            lines.append(f'      <data key="score">{score}</data>')
            lines.append("    </node>")

        for idx, r in enumerate(relationships):
            rid = esc(str(r.get("id") or f"e{idx}"))
            src = esc(str(r.get("source") or ""))
            tgt = esc(str(r.get("target") or ""))
            rtype = esc(str(r.get("type") or "RELATED_TO"))
            weight = float(r.get("weight") or 1.0)
            lines.append(f'    <edge id="{rid}" source="{src}" target="{tgt}">')
            lines.append(f'      <data key="type">{rtype}</data>')
            lines.append(f'      <data key="weight">{weight}</data>')
            lines.append("    </edge>")

        lines.append("  </graph>")
        lines.append("</graphml>")
        return "\n".join(lines)

    @staticmethod
    def _to_cypher(entities: list[dict[str, Any]], relationships: list[dict[str, Any]]) -> str:
        statements: list[str] = [
            "// GraphRAG Subgraph Cypher Export",
            "// Run in Neo4j / Memgraph Browser or Cypher Shell",
            "",
        ]

        # Escape helper
        def q(val: str) -> str:
            return json.dumps(str(val))

        for e in entities:
            eid = e.get("id") or ""
            name = e.get("name") or eid
            etype = e.get("type") or "Entity"
            clean_type = "".join(c for c in etype if c.isalnum() or c == "_") or "Entity"
            score = float(e.get("relevance_score") or 0.0)
            props = [f"id: {q(eid)}", f"name: {q(name)}", f"relevance_score: {score}"]
            statements.append(f"MERGE (n:`{clean_type}` {{id: {q(eid)}}}) ON CREATE SET n += {{{', '.join(props)}}};")

        statements.append("")
        for idx, r in enumerate(relationships):
            src = r.get("source") or ""
            tgt = r.get("target") or ""
            rtype = "".join(c for c in (r.get("type") or "RELATED_TO") if c.isalnum() or c == "_") or "RELATED_TO"
            weight = float(r.get("weight") or 1.0)
            statements.append(
                f"MATCH (a {{id: {q(src)}}}), (b {{id: {q(tgt)}}}) "
                f"MERGE (a)-[r:`{rtype}`]->(b) ON CREATE SET r.weight = {weight};"
            )

        return "\n".join(statements)

    @staticmethod
    def _to_json_ld(entities: list[dict[str, Any]], relationships: list[dict[str, Any]]) -> str:
        graph_nodes = []
        for e in entities:
            node = {
                "@id": f"urn:entity:{e.get('id')}",
                "@type": e.get("type") or "Thing",
                "name": e.get("name"),
                "relevanceScore": float(e.get("relevance_score") or 0.0),
            }
            props = e.get("properties") or {}
            for k, v in props.items():
                if k not in node:
                    node[k] = v
            graph_nodes.append(node)

        for r in relationships:
            src = f"urn:entity:{r.get('source')}"
            tgt = f"urn:entity:{r.get('target')}"
            rtype = r.get("type") or "relatedTo"
            # Attach relation to source node if present
            for node in graph_nodes:
                if node["@id"] == src:
                    if rtype not in node:
                        node[rtype] = []
                    node[rtype].append({"@id": tgt, "weight": float(r.get("weight") or 1.0)})
                    break

        doc = {
            "@context": {
                "@vocab": "https://schema.org/",
                "relevanceScore": "https://graphrag.io/ns#relevanceScore",
            },
            "@graph": graph_nodes,
        }
        return json.dumps(doc, indent=2)

    @staticmethod
    def _to_rdf_turtle(entities: list[dict[str, Any]], relationships: list[dict[str, Any]]) -> str:
        lines = [
            "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
            "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
            "@prefix grip: <https://grip-protocol.org/ns#> .",
            "@prefix ent: <https://grip-protocol.org/entity/> .",
            "",
        ]

        def safe_uri(id_str: str) -> str:
            clean = "".join(c if c.isalnum() or c in "_-:" else "_" for c in str(id_str))
            return f"ent:{clean}"

        for e in entities:
            subj = safe_uri(e.get("id") or "unknown")
            name = json.dumps(str(e.get("name") or ""))
            etype = json.dumps(str(e.get("type") or "Entity"))
            score = float(e.get("relevance_score") or 0.0)
            lines.append(f"{subj} a grip:Entity ;")
            lines.append(f"    rdfs:label {name} ;")
            lines.append(f"    grip:entityType {etype} ;")
            lines.append(f"    grip:relevanceScore {score} .")
            lines.append("")

        for r in relationships:
            src = safe_uri(r.get("source") or "")
            tgt = safe_uri(r.get("target") or "")
            rtype = "".join(c for c in (r.get("type") or "relatedTo") if c.isalnum() or c == "_")
            lines.append(f"{src} grip:{rtype} {tgt} .")

        return "\n".join(lines)
