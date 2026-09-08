import type { PipelineResult } from "../../lib/types";
import Card from "../shared/Card";
import Badge from "../shared/Badge";

export interface DecoratedPipeline extends PipelineResult {
  name: string;
  subtitle: string;
  accent: string;
}

interface PipelineResultCardProps {
  pipeline: DecoratedPipeline;
}

export default function PipelineResultCard({ pipeline }: PipelineResultCardProps) {
  return (
    <Card className="flex flex-col">
      <div className="mb-2 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-gray-900">{pipeline.name}</h3>
          <p className="text-xs text-gray-500">{pipeline.subtitle}</p>
        </div>
        <Badge color={pipeline.retrieval_method === "none" ? "gray" : "blue"}>
          {pipeline.retrieval_method}
        </Badge>
      </div>

      <div className={`mb-3 h-1 rounded-full ${pipeline.accent}`} />

      <p className="mb-4 flex-1 whitespace-pre-wrap text-sm leading-relaxed text-gray-800">
        {pipeline.answer}
      </p>

      <div className="grid grid-cols-3 gap-2 border-t border-gray-100 pt-3 text-center">
        <div>
          <p className="text-lg font-bold text-gray-900">
            {pipeline.tokens_total.toLocaleString()}
          </p>
          <p className="text-xs text-gray-500">Tokens</p>
        </div>
        <div>
          <p className="text-lg font-bold text-gray-900">
            {pipeline.latency_ms.toFixed(0)}
            <span className="text-sm font-normal text-gray-500">ms</span>
          </p>
          <p className="text-xs text-gray-500">Latency</p>
        </div>
        <div>
          <p className="text-lg font-bold text-gray-900">
            {pipeline.context_tokens?.toLocaleString() ?? "—"}
          </p>
          <p className="text-xs text-gray-500">Context</p>
        </div>
      </div>

      {(pipeline.entities_used !== undefined ||
        pipeline.graph_hops !== undefined) && (
        <div className="mt-2 flex justify-center gap-2 border-t border-gray-100 pt-2">
          {pipeline.entities_used !== undefined && (
            <Badge color="amber">{pipeline.entities_used} entities</Badge>
          )}
          {pipeline.graph_hops !== undefined && (
            <Badge color="amber">{pipeline.graph_hops} hops</Badge>
          )}
        </div>
      )}
    </Card>
  );
}
