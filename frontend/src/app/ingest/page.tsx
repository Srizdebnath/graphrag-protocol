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
        <h1 className="text-2xl font-bold tracking-tight text-gray-900">
          Document Ingestion & Live Mutation Feed
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          Contract 4 (Construction) real writes into TigerGraph & Contract 7 (Streaming) live SSE bus.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left column: Ingestion Form */}
        <div className="lg:col-span-6 space-y-6">
          <Card title="Contract 4: Ingest Document" subtitle="Extracts concepts, resolves entities, and updates graph">
            <form onSubmit={handleIngest} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-700">Document ID (arXiv ID)</label>
                <input
                  type="text"
                  value={docId}
                  onChange={(e) => setDocId(e.target.value)}
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-gray-900 focus:outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700">Title</label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-gray-900 focus:outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700">Authors (comma-separated)</label>
                <input
                  type="text"
                  value={authors}
                  onChange={(e) => setAuthors(e.target.value)}
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-gray-900 focus:outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700">Text / Abstract</label>
                <textarea
                  rows={4}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-gray-900 focus:outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700">Admin Token (X-Admin-Token)</label>
                <input
                  type="password"
                  value={adminToken}
                  onChange={(e) => setAdminToken(e.target.value)}
                  placeholder="Set in .env as GRAPHRAG_ADMIN_TOKEN"
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm font-mono focus:border-gray-900 focus:outline-none"
                  required
                />
              </div>

              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={dryRun}
                    onChange={(e) => setDryRun(e.target.checked)}
                    className="rounded border-gray-300 text-gray-900 focus:ring-gray-900"
                  />
                  <span>Dry Run (simulate writes)</span>
                </label>
              </div>

              <button
                type="submit"
                disabled={ingesting}
                className="w-full rounded-md bg-gray-900 px-4 py-2 text-sm font-semibold text-white hover:bg-gray-800 disabled:opacity-50 transition-colors"
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
              <div className="mt-4 p-4 rounded-md bg-gray-50 border border-gray-200 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-gray-700">Ingestion Report</span>
                  <Badge color={ingestResult.errors?.length ? "red" : "green"}>
                    {ingestResult.errors?.length ? "Errors Reported" : "Success"}
                  </Badge>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs text-gray-600">
                  <div>Documents Written: <span className="font-semibold text-gray-900">{ingestResult.documents_written?.length || 0}</span></div>
                  <div>Entities Created: <span className="font-semibold text-gray-900">{ingestResult.entities_created}</span></div>
                  <div>Entities Resolved: <span className="font-semibold text-gray-900">{ingestResult.entities_resolved}</span></div>
                  <div>Edges Created: <span className="font-semibold text-gray-900">{ingestResult.relationships_created}</span></div>
                  <div>Duration: <span className="font-semibold text-gray-900">{(ingestResult.duration_ms || 0).toFixed(1)}ms</span></div>
                  <div>Triples: <span className="font-semibold text-gray-900">{ingestResult.triples?.length || 0}</span></div>
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
            <div className="flex items-center justify-between pb-3 border-b border-gray-100">
              <div className="flex items-center gap-2">
                <span
                  className={`inline-block h-2.5 w-2.5 rounded-full ${
                    streamStatus === "connected"
                      ? "bg-green-500 animate-pulse"
                      : streamStatus === "connecting"
                      ? "bg-amber-500 animate-pulse"
                      : "bg-red-500"
                  }`}
                />
                <span className="text-xs font-medium text-gray-600 capitalize">{streamStatus}</span>
              </div>
              <div className="flex items-center gap-2">
                <label className="text-xs text-gray-500">Filter:</label>
                <select
                  value={filterType}
                  onChange={(e) => setFilterType(e.target.value)}
                  className="rounded border border-gray-300 px-2 py-1 text-xs focus:border-gray-900 focus:outline-none"
                >
                  <option value="">All Events</option>
                  <option value="entity_created">entity_created</option>
                  <option value="entity_updated">entity_updated</option>
                  <option value="edge_created">edge_created</option>
                  <option value="ingestion_completed">ingestion_completed</option>
                </select>
              </div>
            </div>

            <div className="mt-4 space-y-3 max-h-[500px] overflow-y-auto pr-2">
              {events.length === 0 ? (
                <div className="py-12 text-center text-xs text-gray-400">
                  {streamStatus === "connected"
                    ? "Listening for graph mutation events... Trigger an ingestion on the left!"
                    : "Connecting to SSE stream..."}
                </div>
              ) : (
                events.map((ev, idx) => (
                  <div
                    key={ev.event_id || idx}
                    className="p-3 rounded-md border border-gray-200 bg-white hover:border-gray-300 transition-colors space-y-1.5"
                  >
                    <div className="flex items-center justify-between text-xs">
                      <Badge color="blue">{ev.event_type}</Badge>
                      <span className="text-gray-400 font-mono text-[10px]">
                        {new Date(ev.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                    <pre className="text-[11px] font-mono text-gray-700 bg-gray-50 p-2 rounded overflow-x-auto">
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
