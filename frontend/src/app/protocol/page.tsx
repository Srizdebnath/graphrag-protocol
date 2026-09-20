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
    <div className="mx-auto max-w-7xl px-4 py-8 space-y-8">
      <div>
        <h1 className="text-2xl font-black uppercase tracking-tight text-black">Protocol Explorer</h1>
        <p className="mt-1 font-mono text-xs font-bold text-black/70">
          Introspect active TigerGraph schema, vertex/edge definitions, and 10 formal protocol contracts.
        </p>
      </div>

      {loading && <LoadingSpinner label="Fetching graph schema..." />}
      {error && <ErrorState message={error} hint="Make sure the backend server is running at http://localhost:8000" />}

      {!loading && !error && !schema && (
        <div className="rounded-xl border-3 border-dashed border-black bg-white/70 py-16 text-center font-mono text-xs font-black uppercase tracking-wider text-black/60 shadow-brutal-sm">
          Schema not available. Backend may be unreachable.
        </div>
      )}

      {schema && (
        <div className="space-y-8">
          {/* Statistics */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {[
              { label: "Total Vertices", value: schema.statistics.total_vertices.toLocaleString(), bg: "bg-[#E0E7FF]" },
              { label: "Total Edges", value: schema.statistics.total_edges.toLocaleString(), bg: "bg-[#DCFCE7]" },
              {
                label: "Density / Avg Degree",
                value: schema.statistics.density !== undefined
                  ? schema.statistics.density.toFixed(4)
                  : (schema.statistics.avg_degree ?? 0).toFixed(2),
                bg: "bg-[#FEF08A]",
              },
              {
                label: "Connected Components",
                value: (schema.statistics.connected_components ?? schema.statistics.components ?? 0).toLocaleString(),
                bg: "bg-[#FCE7F3]",
              },
            ].map((s) => (
              <div
                key={s.label}
                className={`rounded-xl border-3 border-black ${s.bg} p-4 shadow-brutal transition-transform hover:translate-x-[-2px] hover:translate-y-[-2px]`}
              >
                <p className="font-mono text-xs font-black uppercase tracking-wider text-black/70">{s.label}</p>
                <p className="mt-1 font-mono text-2xl font-black text-black">{s.value}</p>
              </div>
            ))}
          </div>

          {/* Entity / Vertex Types */}
          {(() => {
            const vtypes = schema.vertex_types || schema.entity_types || [];
            return (
              <Card title="Vertex Types" subtitle={`${vtypes.length} vertex types in active knowledge graph`}>
                <div className="overflow-x-auto rounded-lg border-2 border-black shadow-brutal-sm">
                  <table className="w-full text-left text-sm">
                    <thead className="border-b-3 border-black bg-[#FFE600]">
                      <tr>
                        <th className="px-3.5 py-3 font-mono text-xs font-black uppercase tracking-wider text-black">Type</th>
                        <th className="px-3.5 py-3 font-mono text-xs font-black uppercase tracking-wider text-black">Count</th>
                        <th className="px-3.5 py-3 font-mono text-xs font-black uppercase tracking-wider text-black">Attributes</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y-2 divide-black/10 bg-white font-mono text-xs">
                      {vtypes.map((et) => {
                        const typeName = et.type || et.name || "Unknown";
                        return (
                          <tr key={typeName} className="hover:bg-yellow-50/80 transition-colors">
                            <td className="px-3.5 py-2.5 font-bold text-black">{typeName}</td>
                            <td className="px-3.5 py-2.5 font-bold text-black/80">{(et.count || 0).toLocaleString()}</td>
                            <td className="px-3.5 py-2.5">
                              <div className="flex flex-wrap gap-1">
                                {Object.entries(et.attributes || {}).map(([k, v]) => (
                                  <Badge key={k} color="gray">
                                    {k}: {String(v)}
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
              <Card title="Edge Types" subtitle={`${etypes.length} relationship types connecting entities`}>
                <div className="overflow-x-auto rounded-lg border-2 border-black shadow-brutal-sm">
                  <table className="w-full text-left text-sm">
                    <thead className="border-b-3 border-black bg-[#FFE600]">
                      <tr>
                        <th className="px-3.5 py-3 font-mono text-xs font-black uppercase tracking-wider text-black">Type</th>
                        <th className="px-3.5 py-3 font-mono text-xs font-black uppercase tracking-wider text-black">Source → Target</th>
                        <th className="px-3.5 py-3 font-mono text-xs font-black uppercase tracking-wider text-black">Count</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y-2 divide-black/10 bg-white font-mono text-xs">
                      {etypes.map((rt) => {
                        const typeName = rt.type || rt.name || "Unknown";
                        const src = rt.source_type || rt.source || "*";
                        const tgt = rt.target_type || rt.target || "*";
                        return (
                          <tr key={typeName} className="hover:bg-yellow-50/80 transition-colors">
                            <td className="px-3.5 py-2.5 font-bold text-black">{typeName}</td>
                            <td className="px-3.5 py-2.5 font-bold text-black/80">
                              {src} &rarr; {tgt}
                            </td>
                            <td className="px-3.5 py-2.5 font-bold text-black">{(rt.count || 0).toLocaleString()}</td>
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
      <div className="space-y-4 pt-4">
        <div>
          <h2 className="text-xl font-black uppercase tracking-tight text-black">10 Protocol Wire Contracts</h2>
          <p className="mt-0.5 font-mono text-xs font-bold text-black/70">
            Formal JSON Schema specifications defining interoperability interfaces
          </p>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {CONTRACTS.map((c, idx) => {
            const colors = ["bg-[#E0E7FF]", "bg-[#FEF08A]", "bg-[#DCFCE7]", "bg-[#FCE7F3]", "bg-[#FED7AA]", "bg-[#CCFBF1]"];
            const bg = colors[idx % colors.length];
            return (
              <div
                key={c.id}
                className={`rounded-xl border-3 border-black ${bg} p-5 shadow-brutal transition-transform hover:translate-x-[-2px] hover:translate-y-[-2px] hover:shadow-brutal-lg`}
              >
                <div className="flex items-start gap-3">
                  <span className="rounded-md border-2 border-black bg-black px-2 py-0.5 font-mono text-xs font-black text-[#FFE600] shadow-brutal-xs">
                    {c.id}
                  </span>
                  <div>
                    <h3 className="font-mono text-sm font-black uppercase text-black">{c.name}</h3>
                    <p className="mt-1 font-mono text-xs font-semibold leading-relaxed text-black/80">{c.description}</p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
