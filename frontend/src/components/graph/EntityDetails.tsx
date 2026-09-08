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
      <div className="flex h-full items-center justify-center text-sm text-gray-400">
        Click a node to view details
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-bold text-gray-900">{entity.name}</h3>
          <p className="text-xs text-gray-500">{entity.id}</p>
        </div>
        <button
          onClick={onClose}
          className="ml-2 rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
        >
          ✕
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 text-sm">
        <div className="mb-3 flex items-center gap-2">
          <Badge color={typeColors[entity.type] ?? "gray"}>{entity.type}</Badge>
          <span className="text-xs text-gray-500">
            relevance {(entity.relevance_score * 100).toFixed(0)}%
          </span>
        </div>

        {Object.keys(entity.properties).length > 0 && (
          <div className="mb-4">
            <h4 className="mb-1 text-xs font-semibold uppercase text-gray-500">Properties</h4>
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
              {Object.entries(entity.properties).map(([k, v]) => (
                <Fragment key={k}>
                  <dt className="text-xs font-medium text-gray-500">{k}</dt>
                  <dd className="truncate text-xs text-gray-800">{String(v)}</dd>
                </Fragment>
              ))}
            </dl>
          </div>
        )}

        {entity.source_chunks.length > 0 && (
          <div>
            <h4 className="mb-1 text-xs font-semibold uppercase text-gray-500">Source Chunks</h4>
            <ul className="list-disc space-y-1 pl-4">
              {entity.source_chunks.map((chunk, i) => (
                <li key={i} className="break-all text-xs text-gray-600">
                  {chunk}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
