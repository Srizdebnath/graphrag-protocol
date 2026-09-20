import type { BenchmarkResult, GraphSchema, SubgraphContext } from "./types";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options?.headers || {}),
      },
    });
  } catch (err) {
    throw new Error(
      `Cannot reach backend at ${API_URL}${path}. Is the server running? (${(err as Error).message})`
    );
  }

  if (!res.ok) {
    throw new Error(
      `Backend returned ${res.status} ${res.statusText} for ${path}`
    );
  }

  return (await res.json()) as T;
}

export async function runQuery(
  query: string
): Promise<{
  pipeline_1: BenchmarkResult["pipeline_1"];
  pipeline_2: BenchmarkResult["pipeline_2"];
  pipeline_3: BenchmarkResult["pipeline_3"];
}> {
  return request("/query", {
    method: "POST",
    body: JSON.stringify({ query }),
  });
}

export async function getBenchmarkResults(): Promise<BenchmarkResult[]> {
  return request("/benchmark/results");
}

export async function getGraphSchema(): Promise<GraphSchema> {
  return request("/schema");
}

export async function getGraphVisualization(
  entityId?: string
): Promise<SubgraphContext> {
  return request("/graph/visualize", {
    method: "POST",
    body: JSON.stringify(entityId ? { entity_id: entityId } : {}),
  });
}

export async function ingestDocument(
  doc: {
    id: string;
    text: string;
    properties?: Record<string, unknown>;
  },
  adminToken: string,
  dryRun: boolean = false
): Promise<Record<string, unknown>> {
  return request("/ingest", {
    method: "POST",
    headers: {
      "X-Admin-Token": adminToken,
    },
    body: JSON.stringify({
      documents: [doc],
      dry_run: dryRun,
    }),
  });
}

export function getStreamUrl(eventTypes?: string): string {
  const base = `${API_URL}/stream/events`;
  return eventTypes ? `${base}?event_types=${encodeURIComponent(eventTypes)}` : base;
}
