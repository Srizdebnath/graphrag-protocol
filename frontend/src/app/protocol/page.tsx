"use client";

import { useEffect, useState } from "react";
import { getGraphSchema } from "../../lib/api";
import type { GraphSchema } from "../../lib/types";
import LoadingSpinner from "../../components/shared/LoadingSpinner";
import ErrorState from "../../components/shared/ErrorState";
import Card from "../../components/shared/Card";
import Badge from "../../components/shared/Badge";

const CONTRACTS = [
  { name: "Retrieval", id: "C1", description: "7 retrieval operations — local, global, hybrid, entity, path, neighborhood, community." },
  { name: "Subgraph Context", id: "C2", description: "Standard response envelope — entities, relationships, paths, communities, text chunks." },
  { name: "Schema Discovery", id: "C3", description: "Graph introspection — vertex types, edge types, attributes, statistics." },
  { name: "Ingestion", id: "C4", description: "Document ingestion pipeline — chunk, extract, resolve, populate." },
  { name: "Provenance", id: "C5", description: "Citation tracing — full chain from answer back to source documents." },
  { name: "Federation", id: "C6", description: "Multi-backend config — register, federated search, cross-graph entity linking." },
  { name: "Streaming", id: "C7", description: "Real-time graph change events — entity created, edge updated, community recomputed." },
  { name: "Prompt Format", id: "C8", description: "Context → LLM text formatting — Markdown, structured JSON, XML, YAML." },
  { name: "Evaluation", id: "C9", description: "Standard metrics — token count, latency, precision@k, LLM-as-Judge, BERTScore." },
  { name: "Access Control", id: "C10", description: "Authorization model — permission checks, allowed operations per user/graph." },
];

export default function ProtocolPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [schema, setSchema] = useState<GraphSchema | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    getGraphSchema()
      .then((data) => {
        if (!cancelled) setSchema(data);
      })
      .catch((err) => {
        if (!cancelled) setError((err as Error).message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <h1 className="mb-2 text-xl font-bold text-gray-900">Protocol Explorer</h1>
      <p className="mb-6 text-sm text-gray-500">Graph schema and the 10 protocol contracts.</p>

      {loading && <LoadingSpinner label="Fetching graph schema..." />}
      {error && <ErrorState message={error} hint="Make sure the backend server is running at http://localhost:8000" />}

      {!loading && !error && !schema && (
        <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 py-16 text-center text-sm text-gray-400">
          Schema not available. Backend may be unreachable.
        </div>
      )}

      {schema && (
        <div className="space-y-6">
          {/* Statistics */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {[
              { label: "Total Vertices", value: schema.statistics.total_vertices.toLocaleString() },
              { label: "Total Edges", value: schema.statistics.total_edges.toLocaleString() },
              {
                label: "Density / Avg Degree",
                value: schema.statistics.density !== undefined
                  ? schema.statistics.density.toFixed(4)
                  : (schema.statistics.avg_degree ?? 0).toFixed(2),
              },
              {
                label: "Connected Components",
                value: (schema.statistics.connected_components ?? schema.statistics.components ?? 0).toLocaleString(),
              },
            ].map((s) => (
              <Card key={s.label}>
                <p className="text-xs text-gray-500">{s.label}</p>
                <p className="mt-1 text-xl font-bold text-gray-900">{s.value}</p>
              </Card>
            ))}
          </div>

          {/* Entity / Vertex Types */}
          {(() => {
            const vtypes = schema.vertex_types || schema.entity_types || [];
            return (
              <Card title="Vertex Types" subtitle={`${vtypes.length} types in the graph`}>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="border-b border-gray-200 bg-gray-50">
                      <tr>
                        <th className="px-3 py-2 text-xs font-semibold text-gray-600">Type</th>
                        <th className="px-3 py-2 text-xs font-semibold text-gray-600">Count</th>
                        <th className="px-3 py-2 text-xs font-semibold text-gray-600">Attributes</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {vtypes.map((et) => {
                        const typeName = et.type || et.name || "Unknown";
                        return (
                          <tr key={typeName} className="hover:bg-gray-50/50">
                            <td className="px-3 py-2 font-medium text-gray-900">{typeName}</td>
                            <td className="px-3 py-2 text-gray-700">{(et.count || 0).toLocaleString()}</td>
                            <td className="px-3 py-2">
                              <div className="flex flex-wrap gap-1">
                                {Object.entries(et.attributes || {}).map(([k, v]) => (
                                  <Badge key={k} color="gray">
                                    {k}: {v}
                                  </Badge>
                                ))}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </Card>
            );
          })()}

          {/* Edge / Relationship Types */}
          {(() => {
            const etypes = schema.edge_types || schema.relationship_types || [];
            return (
              <Card title="Edge Types" subtitle={`${etypes.length} relationship types`}>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="border-b border-gray-200 bg-gray-50">
                      <tr>
                        <th className="px-3 py-2 text-xs font-semibold text-gray-600">Type</th>
                        <th className="px-3 py-2 text-xs font-semibold text-gray-600">Source → Target</th>
                        <th className="px-3 py-2 text-xs font-semibold text-gray-600">Count</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {etypes.map((rt) => {
                        const typeName = rt.type || rt.name || "Unknown";
                        const src = rt.source_type || rt.source || "*";
                        const tgt = rt.target_type || rt.target || "*";
                        return (
                          <tr key={typeName} className="hover:bg-gray-50/50">
                            <td className="px-3 py-2 font-medium text-gray-900">{typeName}</td>
                            <td className="px-3 py-2 text-gray-700">
                              {src} → {tgt}
                            </td>
                            <td className="px-3 py-2 text-gray-700">{(rt.count || 0).toLocaleString()}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </Card>
            );
          })()}
        </div>
      )}

      {/* Contracts — always shown */}
      <div className="mt-8">
        <h2 className="mb-4 text-lg font-bold text-gray-900">Protocol Contracts</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {CONTRACTS.map((c) => (
            <Card key={c.id}>
              <div className="flex items-start gap-3">
                <Badge color="blue">{c.id}</Badge>
                <div>
                  <h3 className="text-sm font-semibold text-gray-900">{c.name}</h3>
                  <p className="mt-1 text-xs leading-relaxed text-gray-600">{c.description}</p>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
