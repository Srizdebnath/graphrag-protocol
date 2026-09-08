import Link from "next/link";

const features = [
  {
    title: "Query Comparison",
    desc: "Run questions through LLM-only, Basic RAG, and GraphRAG pipelines side by side.",
    href: "/query",
  },
  {
    title: "Benchmark Results",
    desc: "View aggregate metrics, accuracy radar, cost accumulation, and a sortable results table.",
    href: "/benchmark",
  },
  {
    title: "Protocol Explorer",
    desc: "Inspect the graph schema and the 10 protocol contracts.",
    href: "/protocol",
  },
  {
    title: "Graph Visualization",
    desc: "Explore entities and relationships with an interactive force-directed graph.",
    href: "/graph",
  },
];

export default function Home() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-16">
      <h1 className="mb-2 text-3xl font-bold tracking-tight text-gray-900">
        GraphRAG Protocol
      </h1>
      <p className="mb-10 max-w-2xl text-base text-gray-500">
        A universal interface for graph-augmented retrieval — connect any agent to any GraphRAG
        backend. The dashboard lets you compare pipelines, view benchmarks, explore the schema, and
        visualise the knowledge graph.
      </p>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {features.map((f) => (
          <Link
            key={f.href}
            href={f.href}
            className="group rounded-lg border border-gray-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md"
          >
            <h2 className="mb-1 text-sm font-semibold text-gray-900 group-hover:text-blue-600">
              {f.title} →
            </h2>
            <p className="text-xs leading-relaxed text-gray-500">{f.desc}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
