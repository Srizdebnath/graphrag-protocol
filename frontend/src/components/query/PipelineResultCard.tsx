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
    <Card className="flex flex-col justify-between">
      <div>
        <div className="mb-3 flex items-start justify-between gap-2">
          <div>
            <h3 className="font-mono text-sm font-black uppercase text-black">{pipeline.name}</h3>
            <p className="font-mono text-xs font-semibold text-black/70">{pipeline.subtitle}</p>
          </div>
          <Badge color={pipeline.retrieval_method === "none" ? "gray" : pipeline.retrieval_method === "vector" ? "blue" : "green"}>
            {pipeline.retrieval_method}
          </Badge>
        </div>

        <div className={`mb-4 h-2 w-full rounded-full border-2 border-black ${pipeline.accent} shadow-brutal-xs`} />

        <p className="mb-6 whitespace-pre-wrap font-sans text-sm font-medium leading-relaxed text-black/90">
          {pipeline.answer}
        </p>
      </div>

      <div className="space-y-3 border-t-3 border-black pt-4">
        <div className="grid grid-cols-3 gap-2">
          <div className="rounded-lg border-2 border-black bg-yellow-50 p-2 text-center shadow-brutal-xs">
            <p className="font-mono text-base font-black text-black">
              {pipeline.tokens_total.toLocaleString()}
            </p>
            <p className="font-mono text-[10px] font-black uppercase text-black/70">Tokens</p>
          </div>
          <div className="rounded-lg border-2 border-black bg-blue-50 p-2 text-center shadow-brutal-xs">
            <p className="font-mono text-base font-black text-black">
              {pipeline.latency_ms.toFixed(0)}<span className="text-xs">ms</span>
            </p>
            <p className="font-mono text-[10px] font-black uppercase text-black/70">Latency</p>
          </div>
          <div className="rounded-lg border-2 border-black bg-green-50 p-2 text-center shadow-brutal-xs">
            <p className="font-mono text-base font-black text-black">
              {pipeline.context_tokens?.toLocaleString() ?? "—"}
            </p>
            <p className="font-mono text-[10px] font-black uppercase text-black/70">Context</p>
          </div>
        </div>

        {(pipeline.entities_used !== undefined ||
          pipeline.graph_hops !== undefined) && (
          <div className="flex flex-wrap justify-center gap-2 pt-1">
            {pipeline.entities_used !== undefined && (
              <Badge color="amber">{pipeline.entities_used} entities</Badge>
            )}
            {pipeline.graph_hops !== undefined && (
              <Badge color="amber">{pipeline.graph_hops} hops</Badge>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}
