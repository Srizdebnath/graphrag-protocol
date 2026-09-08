"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";
import type { Entity } from "../../lib/types";

export interface GraphNode {
  id: string;
  name: string;
  type: string;
  val: number;
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
  const graphRef = useRef<unknown>(null);

  const graphData = useMemo(
    () => ({
      nodes: nodes.map((n) => ({ ...n, color: TYPE_COLORS[n.type] ?? "#6b7280" })),
      links: edges.map((e) => ({ source: e.source, target: e.target, label: e.label })),
    }),
    [nodes, edges],
  );

  const nodeCanvasObject = useCallback(
    (node: GraphNode & { color: string }, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const label = node.name;
      const fontSize = 12 / globalScale;
      ctx.font = `${fontSize}px Sans-Serif`;
      const textWidth = ctx.measureText(label).width;
      const bgDimensions = [textWidth + fontSize, fontSize + 4].map((v) => v / globalScale);

      ctx.fillStyle = "rgba(255,255,255,0.9)";
      ctx.beginPath();
      ctx.roundRect(
        (node as unknown as { x: number }).x - bgDimensions[0] / 2,
        (node as unknown as { y: number }).y - bgDimensions[1] / 2,
        bgDimensions[0],
        bgDimensions[1],
        4 / globalScale,
      );
      ctx.fill();

      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillStyle = node.color;
      ctx.fillText(label, (node as unknown as { x: number }).x, (node as unknown as { y: number }).y);

      ctx.beginPath();
      ctx.arc(
        (node as unknown as { x: number }).x,
        (node as unknown as { y: number }).y - bgDimensions[1] / 2 - 6 / globalScale,
        4 / globalScale,
        0,
        2 * Math.PI,
      );
      ctx.fillStyle = node.color;
      ctx.fill();
    },
    [],
  );

  useEffect(() => {
    let cancelled = false;

    async function init() {
      const container = containerRef.current;
      if (!container) return;

      const { default: ForceGraph2D } = await import("react-force-graph-2d");
      if (cancelled) return;

      type Graph2D = {
        graphData: (d: unknown) => Graph2D;
        nodeCanvasObject: (fn: unknown) => Graph2D;
        nodePointerAreaPaint: (fn: unknown) => Graph2D;
        linkLabel: (fn: unknown) => Graph2D;
        linkDirectionalArrowLength: (n: number) => Graph2D;
        linkDirectionalArrowRelPos: (n: number) => Graph2D;
        linkWidth: (n: number) => Graph2D;
        onNodeClick: (fn: unknown) => Graph2D;
        width: (n: number) => Graph2D;
        height: (n: number) => Graph2D;
      };

      const graph = (
        ForceGraph2D as unknown as (el: HTMLElement) => Graph2D
      )(container)
        .graphData(graphData)
        .nodeCanvasObject(nodeCanvasObject)
        .nodePointerAreaPaint(
          (node: GraphNode & { color: string }, color: string, ctx: CanvasRenderingContext2D) => {
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(
              (node as unknown as { x: number }).x,
              (node as unknown as { y: number }).y,
              8,
              0,
              2 * Math.PI,
            );
            ctx.fill();
          },
        )
        .linkLabel((link: { label: string }) => link.label)
        .linkDirectionalArrowLength(4)
        .linkDirectionalArrowRelPos(1)
        .linkWidth(1)
        .onNodeClick((node: GraphNode) => {
          const entity: Entity = {
            id: node.id,
            type: node.type,
            name: node.name,
            properties: {},
            relevance_score: 1,
            source_chunks: [],
          };
          onNodeClick(entity);
        })
        .width(container.clientWidth)
        .height(container.clientHeight);

      graphRef.current = graph;
    }

    init();

    return () => {
      cancelled = true;
    };
  }, [graphData, nodeCanvasObject, onNodeClick]);

  useEffect(() => {
    if (graphRef.current) {
      (graphRef.current as { graphData: (d: typeof graphData) => void }).graphData(graphData);
    }
  }, [graphData]);

  return <div ref={containerRef} className="h-full w-full" />;
}
