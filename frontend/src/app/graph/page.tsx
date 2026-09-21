"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { getGraphVisualization } from "../../lib/api";
import type { Entity, Relationship, SubgraphContext } from "../../lib/types";
import type { GraphNode, GraphEdge } from "../../components/graph/GraphView";
import EntityDetails from "../../components/graph/EntityDetails";
import LoadingSpinner from "../../components/shared/LoadingSpinner";
import ErrorState from "../../components/shared/ErrorState";

const GraphView = dynamic(() => import("../../components/graph/GraphView"), {
  ssr: false,
  loading: () => <LoadingSpinner label="Initializing 3D graph canvas..." />,
});

export default function GraphPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null);

  useEffect(() => {
    let cancelled = false;

    getGraphVisualization()
      .then((ctx: SubgraphContext) => {
        if (cancelled) return;

        const n: GraphNode[] = ctx.results.entities.map((e: Entity) => ({
          id: e.id,
          name: e.name,
          type: e.type,
          val: Math.max(4, e.relevance_score * 16),
        }));

        const e: GraphEdge[] = ctx.results.relationships.map((r: Relationship) => ({
          source: r.source,
          target: r.target,
          label: r.type,
        }));

        setNodes(n);
        setEdges(e);
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
    <div className="flex h-[calc(100vh-4rem)] flex-col lg:flex-row">
      {/* Graph panel */}
      <div className="relative flex-1 bg-[#F7F5EE]">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-[#F7F5EE]">
            <LoadingSpinner label="Loading graph visualization..." />
          </div>
        )}
        {error && (
          <div className="absolute inset-4">
            <ErrorState message={error} hint="Make sure the backend server is running at http://localhost:8000" />
          </div>
        )}
        {!loading && !error && nodes.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center font-mono text-xs font-black uppercase tracking-wider text-black/50">
            No graph data available. The backend may be unreachable.
          </div>
        )}
        {!loading && !error && nodes.length > 0 && (
          <GraphView nodes={nodes} edges={edges} onNodeClick={setSelectedEntity} />
        )}
      </div>

      {/* Side panel */}
      <div className="h-72 w-full border-t-4 border-black bg-white shadow-brutal lg:h-full lg:w-96 lg:border-t-0 lg:border-l-4">
        <EntityDetails entity={selectedEntity} onClose={() => setSelectedEntity(null)} />
      </div>
    </div>
  );
}
