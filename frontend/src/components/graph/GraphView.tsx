"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Entity } from "../../lib/types";

// Dynamic import with SSR disabled prevents canvas/window SSR mismatch
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
});

export interface GraphNode {
  id: string;
  name: string;
  type: string;
  val: number;
  color?: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  label: string;
}

interface GraphViewProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onNodeClick: (entity: Entity) => void;
}

const TYPE_COLORS: Record<string, string> = {
  Paper: "#3b82f6",
  Author: "#10b981",
  Method: "#f59e0b",
  Dataset: "#ef4444",
  Concept: "#8b5cf6",
  Institution: "#ec4899",
};

export default function GraphView({ nodes, edges, onNodeClick }: GraphViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    function updateDimensions() {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.clientWidth || 800,
          height: containerRef.current.clientHeight || 600,
        });
      }
    }

    updateDimensions();
    window.addEventListener("resize", updateDimensions);
    return () => window.removeEventListener("resize", updateDimensions);
  }, []);

  const graphData = useMemo(
    () => ({
      nodes: nodes.map((n) => ({ ...n, color: TYPE_COLORS[n.type] ?? "#6b7280" })),
      links: edges.map((e) => ({ source: e.source, target: e.target, label: e.label })),
    }),
    [nodes, edges],
  );

  const nodeCanvasObject = useCallback(
    (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const label = node.name || node.id;
      const fontSize = Math.max(8, 12 / globalScale);
      ctx.font = `${fontSize}px Sans-Serif`;
      const textWidth = ctx.measureText(label).width;
      const bgDimensions = [textWidth + fontSize, fontSize + 4].map((v) => v / globalScale);

      ctx.fillStyle = "rgba(255,255,255,0.9)";
      ctx.beginPath();
      ctx.roundRect(
        node.x - bgDimensions[0] / 2,
        node.y - bgDimensions[1] / 2,
        bgDimensions[0],
        bgDimensions[1],
        4 / globalScale,
      );
      ctx.fill();

      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillStyle = node.color || "#000000";
      ctx.fillText(label, node.x, node.y);

      ctx.beginPath();
      ctx.arc(
        node.x,
        node.y - bgDimensions[1] / 2 - 6 / globalScale,
        4 / globalScale,
        0,
        2 * Math.PI,
      );
      ctx.fillStyle = node.color || "#000000";
      ctx.fill();
    },
    [],
  );

  const nodePointerAreaPaint = useCallback(
    (node: any, color: string, ctx: CanvasRenderingContext2D) => {
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(node.x, node.y, 8, 0, 2 * Math.PI);
      ctx.fill();
    },
    [],
  );

  const handleNodeClick = useCallback(
    (node: any) => {
      const entity: Entity = {
        id: String(node.id),
        type: node.type || "Entity",
        name: node.name || String(node.id),
        properties: {},
        relevance_score: 1,
        source_chunks: [],
      };
      onNodeClick(entity);
    },
    [onNodeClick],
  );

  return (
    <div ref={containerRef} className="h-full w-full relative">
      {mounted && (
        <ForceGraph2D
          width={dimensions.width}
          height={dimensions.height}
          graphData={graphData}
          nodeCanvasObject={nodeCanvasObject}
          nodePointerAreaPaint={nodePointerAreaPaint}
          linkLabel={(link: any) => link.label}
          linkDirectionalArrowLength={4}
          linkDirectionalArrowRelPos={1}
          linkWidth={1}
          onNodeClick={handleNodeClick}
        />
      )}
    </div>
  );
}
