"use client";

import { useEffect, useState, useRef } from "react";
import Card from "../../components/shared/Card";
import Badge from "../../components/shared/Badge";
import ErrorState from "../../components/shared/ErrorState";
import { ingestDocument, getStreamUrl } from "../../lib/api";

interface StreamEventItem {
  event_id: string;
  event_type: string;
  timestamp: string;
  graph_id?: string;
  payload: Record<string, unknown>;
}

interface IngestionReportData {
  documents_written?: string[];
  entities_created?: number;
  entities_resolved?: number;
  relationships_created?: number;
  duration_ms?: number;
  triples?: unknown[];
  errors?: string[];
}

export default function IngestPage() {
  // Ingest form state
  const [docId, setDocId] = useState("2609.99999");
  const [title, setTitle] = useState("Unified GraphRAG with Zero-Mock Guarantees");
  const [text, setText] = useState(
    "We present a universal GraphRAG interoperability protocol featuring real GSQL execution, verifiable provenance, and streaming mutation feeds."
  );
  const [authors, setAuthors] = useState("Alice Smith, Bob Jones");
  const [adminToken, setAdminToken] = useState("");
  const [dryRun, setDryRun] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [ingestResult, setIngestResult] = useState<IngestionReportData | null>(null);
  const [ingestError, setIngestError] = useState<string | null>(null);

  // SSE Stream state
  const [events, setEvents] = useState<StreamEventItem[]>([]);
  const [streamStatus, setStreamStatus] = useState<"connected" | "disconnected" | "connecting">("connecting");
  const [filterType, setFilterType] = useState<string>("");
  const eventSourceRef = useRef<EventSource | null>(null);

  // Load admin token from localStorage if saved
  useEffect(() => {
    const saved = localStorage.getItem("graphrag_admin_token");
    if (saved) setAdminToken(saved);
  }, []);

  // Connect to SSE stream
  useEffect(() => {
    setStreamStatus("connecting");
    const url = getStreamUrl(filterType || undefined);
    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.onopen = () => {
      setStreamStatus("connected");
    };

    es.onmessage = (e) => {
      try {
        const parsed: StreamEventItem = JSON.parse(e.data);
        setEvents((prev) => [parsed, ...prev.slice(0, 49)]);
      } catch {
        // Ignore ping or non-json comments
      }
    };

    es.onerror = () => {
      setStreamStatus("disconnected");
    };

    return () => {
      es.close();
    };
  }, [filterType]);

  const handleIngest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!adminToken) {
      setIngestError("Admin token is required (Contract 10). Set GRAPHRAG_ADMIN_TOKEN.");
      return;
    }
    setIngesting(true);
    setIngestError(null);
    setIngestResult(null);

    // Save token to localStorage for convenience
    localStorage.setItem("graphrag_admin_token", adminToken);

    try {
      const authorList = authors.split(",").map((a) => a.trim()).filter(Boolean);
      const res = await ingestDocument(
        {
          id: docId,
          text: `${title}\n\n${text}`,
          properties: {
            title,
            authors: authorList,
            published: new Date().toISOString(),
          },
        },
        adminToken,
        dryRun
      );
      setIngestResult(res as IngestionReportData);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to ingest document";
      setIngestError(msg);
    } finally {
      setIngesting(false);
    }
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 space-y-8">
      <div>
        <h1 className="text-2xl font-black uppercase tracking-tight text-black">
          Document Ingestion &amp; Live Mutation Feed
        </h1>
        <p className="mt-1 font-mono text-xs font-bold text-black/70">
          Contract 4 (Construction) real writes into TigerGraph &amp; Contract 7 (Streaming) live SSE bus.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left column: Ingestion Form */}
        <div className="lg:col-span-6 space-y-6">
          <Card title="Contract 4: Ingest Document" subtitle="Extracts concepts, resolves entities, and updates graph">
            <form onSubmit={handleIngest} className="space-y-4">
              <div>
                <label className="block font-mono text-xs font-black uppercase text-black">Document ID (arXiv ID)</label>
                <input
                  type="text"
                  value={docId}
                  onChange={(e) => setDocId(e.target.value)}
                  className="mt-1 w-full rounded-lg border-2 border-black bg-white px-3 py-2 font-mono text-sm shadow-brutal-xs focus:outline-none focus:shadow-brutal-sm transition-all"
                  required
                />
              </div>

              <div>
                <label className="block font-mono text-xs font-black uppercase text-black">Title</label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="mt-1 w-full rounded-lg border-2 border-black bg-white px-3 py-2 font-sans text-sm font-semibold shadow-brutal-xs focus:outline-none focus:shadow-brutal-sm transition-all"
                  required
                />
              </div>

              <div>
                <label className="block font-mono text-xs font-black uppercase text-black">Authors (comma-separated)</label>
                <input
                  type="text"
                  value={authors}
                  onChange={(e) => setAuthors(e.target.value)}
                  className="mt-1 w-full rounded-lg border-2 border-black bg-white px-3 py-2 font-sans text-sm font-semibold shadow-brutal-xs focus:outline-none focus:shadow-brutal-sm transition-all"
                  required
                />
              </div>

              <div>
                <label className="block font-mono text-xs font-black uppercase text-black">Text / Abstract</label>
                <textarea
                  rows={4}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  className="mt-1 w-full rounded-lg border-2 border-black bg-white px-3 py-2 font-sans text-sm shadow-brutal-xs focus:outline-none focus:shadow-brutal-sm transition-all"
                  required
                />
              </div>

              <div>
                <label className="block font-mono text-xs font-black uppercase text-black">Admin Token (X-Admin-Token)</label>
                <input
                  type="password"
                  value={adminToken}
                  onChange={(e) => setAdminToken(e.target.value)}
                  placeholder="Set in .env as GRAPHRAG_ADMIN_TOKEN"
                  className="mt-1 w-full rounded-lg border-2 border-black bg-white px-3 py-2 font-mono text-sm shadow-brutal-xs focus:outline-none focus:shadow-brutal-sm transition-all"
                  required
                />
              </div>

              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 font-mono text-xs font-bold text-black cursor-pointer">
                  <input
                    type="checkbox"
                    checked={dryRun}
                    onChange={(e) => setDryRun(e.target.checked)}
                    className="h-4 w-4 rounded border-2 border-black text-black focus:ring-0"
                  />
                  <span>Dry Run (simulate writes)</span>
                </label>
              </div>

              <button
                type="submit"
                disabled={ingesting}
                className="w-full rounded-xl border-3 border-black bg-[#86EFAC] px-5 py-3 font-mono text-sm font-black uppercase tracking-wider text-black shadow-brutal hover:translate-x-[-2px] hover:translate-y-[-2px] hover:shadow-brutal-lg active:translate-x-[2px] active:translate-y-[2px] active:shadow-brutal-sm disabled:opacity-50 transition-all"
              >
                {ingesting ? "Ingesting..." : dryRun ? "Simulate Ingestion" : "Ingest into TigerGraph"}
              </button>
            </form>

            {ingestError && (
              <div className="mt-4">
                <ErrorState message={ingestError} />
              </div>
            )}

            {ingestResult && (
              <div className="mt-4 rounded-xl border-2 border-black bg-[#FEF08A] p-4 shadow-brutal-sm space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-black uppercase tracking-wider text-black">Ingestion Report</span>
                  <Badge color={ingestResult.errors?.length ? "red" : "green"}>
                    {ingestResult.errors?.length ? "Errors Reported" : "Success"}
                  </Badge>
                </div>
                <div className="grid grid-cols-2 gap-2 font-mono text-xs text-black/80">
                  <div>Documents Written: <span className="font-black text-black">{ingestResult.documents_written?.length || 0}</span></div>
                  <div>Entities Created: <span className="font-black text-black">{ingestResult.entities_created}</span></div>
                  <div>Entities Resolved: <span className="font-black text-black">{ingestResult.entities_resolved}</span></div>
                  <div>Edges Created: <span className="font-black text-black">{ingestResult.relationships_created}</span></div>
                  <div>Duration: <span className="font-black text-black">{(ingestResult.duration_ms || 0).toFixed(1)}ms</span></div>
                  <div>Triples: <span className="font-black text-black">{ingestResult.triples?.length || 0}</span></div>
                </div>
              </div>
            )}
          </Card>
        </div>

        {/* Right column: SSE Live Stream */}
        <div className="lg:col-span-6 space-y-6">
          <Card
            title="Contract 7: Live Mutation Stream"
            subtitle="Real-time Server-Sent Events (SSE) from the graph event bus"
          >
            <div className="flex items-center justify-between pb-3 border-b-2 border-black">
              <div className="flex items-center gap-2">
                <span
                  className={`inline-block h-3 w-3 rounded-full border border-black ${
                    streamStatus === "connected"
                      ? "bg-[#4ADE80] animate-pulse"
                      : streamStatus === "connecting"
                      ? "bg-[#FACC15] animate-pulse"
                      : "bg-[#F87171]"
                  }`}
                />
                <span className="font-mono text-xs font-black uppercase text-black">{streamStatus}</span>
              </div>
              <div className="flex items-center gap-2">
                <label className="font-mono text-xs font-black uppercase text-black/70">Filter:</label>
                <select
                  value={filterType}
                  onChange={(e) => setFilterType(e.target.value)}
                  className="rounded-md border-2 border-black bg-white px-2 py-1 font-mono text-xs font-bold shadow-brutal-xs focus:outline-none"
                >
                  <option value="">All Events</option>
                  <option value="entity_created">entity_created</option>
                  <option value="entity_updated">entity_updated</option>
                  <option value="edge_created">edge_created</option>
                  <option value="ingestion_completed">ingestion_completed</option>
                </select>
              </div>
            </div>

            <div className="mt-4 space-y-3 max-h-[500px] overflow-y-auto pr-1">
              {events.length === 0 ? (
                <div className="py-16 text-center font-mono text-xs font-bold uppercase tracking-wider text-black/50">
                  {streamStatus === "connected"
                    ? "Listening for graph mutation events... Trigger an ingestion on the left!"
                    : "Connecting to SSE stream..."}
                </div>
              ) : (
                events.map((ev, idx) => (
                  <div
                    key={ev.event_id || idx}
                    className="rounded-lg border-2 border-black bg-white p-3 shadow-brutal-xs hover:shadow-brutal-sm transition-all space-y-1.5"
                  >
                    <div className="flex items-center justify-between text-xs">
                      <Badge color="blue">{ev.event_type}</Badge>
                      <span className="font-mono text-[10px] font-bold text-black/60">
                        {new Date(ev.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                    <pre className="rounded-md border-2 border-black/20 bg-yellow-50/50 p-2 font-mono text-[11px] text-black overflow-x-auto">
                      {JSON.stringify(ev.payload, null, 2)}
                    </pre>
                  </div>
                ))
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
