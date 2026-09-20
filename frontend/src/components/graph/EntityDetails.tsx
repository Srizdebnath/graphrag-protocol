import { Fragment } from "react";
import type { Entity } from "../../lib/types";
import Badge from "../shared/Badge";

interface EntityDetailsProps {
  entity: Entity | null;
  onClose: () => void;
}

const typeColors: Record<string, "green" | "blue" | "amber" | "red" | "gray"> = {
  Paper: "blue",
  Author: "green",
  Method: "amber",
  Dataset: "red",
  Concept: "gray",
};

export default function EntityDetails({ entity, onClose }: EntityDetailsProps) {
  if (!entity) {
    return (
      <div className="flex h-full items-center justify-center font-mono text-xs font-black uppercase tracking-wider text-black/50 p-6 text-center">
        Click a node on the canvas to inspect entity attributes &amp; provenance
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b-3 border-black bg-[#FEF08A] px-4 py-3">
        <div className="min-w-0">
          <h3 className="truncate font-mono text-sm font-black uppercase text-black">{entity.name}</h3>
          <p className="font-mono text-xs font-semibold text-black/70">{entity.id}</p>
        </div>
        <button
          onClick={onClose}
          className="ml-2 rounded-md border-2 border-black bg-white px-2 py-0.5 font-mono text-xs font-black text-black shadow-brutal-xs hover:bg-yellow-100 active:translate-x-[1px] active:translate-y-[1px] transition-all"
        >
          ✕
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 text-sm space-y-4">
        <div className="flex items-center gap-2">
          <Badge color={typeColors[entity.type] ?? "gray"}>{entity.type}</Badge>
          <span className="font-mono text-xs font-black uppercase text-black">
            Relevance: {(entity.relevance_score * 100).toFixed(0)}%
          </span>
        </div>

        {Object.keys(entity.properties).length > 0 && (
          <div className="rounded-lg border-2 border-black bg-yellow-50/50 p-3 shadow-brutal-xs">
            <h4 className="mb-2 font-mono text-xs font-black uppercase tracking-wider text-black">Properties</h4>
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 font-mono text-xs">
              {Object.entries(entity.properties).map(([k, v]) => (
                <Fragment key={k}>
                  <dt className="font-bold text-black/70">{k}:</dt>
                  <dd className="truncate font-black text-black">{String(v)}</dd>
                </Fragment>
              ))}
            </dl>
          </div>
        )}

        {entity.source_chunks.length > 0 && (
          <div className="rounded-lg border-2 border-black bg-white p-3 shadow-brutal-xs">
            <h4 className="mb-2 font-mono text-xs font-black uppercase tracking-wider text-black">Source Chunks</h4>
            <ul className="space-y-1 pl-1 font-mono text-xs">
              {entity.source_chunks.map((chunk, i) => (
                <li key={i} className="break-all text-black/80 border-b border-black/10 pb-1">
                  &bull; {chunk}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
