"use client";

import { useEffect, useState } from "react";
import { getGraphVisualization } from "../../lib/api";
import type { Entity, Relationship, SubgraphContext } from "../../lib/types";
import GraphView, { type GraphNode, type GraphEdge } from "../../components/graph/GraphView";
import EntityDetails from "../../components/graph/EntityDetails";
import LoadingSpinner from "../../components/shared/LoadingSpinner";
import ErrorState from "../../components/shared/ErrorState";

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
    <div className="flex h-[calc(100vh-3.5rem)] flex-col lg:flex-row">
      {/* Graph panel */}
      <div className="relative flex-1">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-50">
            <LoadingSpinner label="Loading graph visualization..." />
          </div>
        )}
        {error && (
          <div className="absolute inset-4">
            <ErrorState message={error} hint="Make sure the backend server is running at http://localhost:8000" />
          </div>
        )}
        {!loading && !error && nodes.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center text-sm text-gray-400">
            No graph data available. The backend may be unreachable.
          </div>
        )}
        {!loading && !error && nodes.length > 0 && (
          <GraphView nodes={nodes} edges={edges} onNodeClick={setSelectedEntity} />
        )}
      </div>

      {/* Side panel */}
      <div className="h-64 w-full border-t border-gray-200 bg-white lg:h-full lg:w-80 lg:border-t-0 lg:border-l">
        <EntityDetails entity={selectedEntity} onClose={() => setSelectedEntity(null)} />
      </div>
    </div>
  );
}
