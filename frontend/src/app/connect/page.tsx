"use client";

import { useState } from "react";
import CodeBlock from "../../components/shared/CodeBlock";
import Card from "../../components/shared/Card";
import Badge from "../../components/shared/Badge";
import {
  Boxes,
  Key,
  ShieldCheck,
  CheckCircle2,
  ExternalLink,
  Zap,
} from "lucide-react";

interface IDEGuide {
  id: string;
  name: string;
  badge: string;
  badgeColor: "green" | "blue" | "purple" | "amber" | "red";
  description: string;
  configFile: string;
  installCommand: string;
  configJson: string;
  envVars: { key: string; desc: string; sample: string }[];
  steps: { title: string; detail: string; command?: string }[];
  verificationPrompt: string;
}

const GUIDES: IDEGuide[] = [
  {
    id: "claude-code",
    name: "Claude Code",
    badge: "Official CLI",
    badgeColor: "purple",
    description:
      "Anthropic's official terminal agent. Connects directly via stdio transport using `claude mcp add`.",
    configFile: "~/.claude.json or project .claude/mcp.json",
    installCommand: "pip install -U grip-protocol",
    configJson: JSON.stringify(
      {
        mcpServers: {
          grip: {
            command: "grip",
            args: ["--transport", "stdio"],
            env: {
              TIGERGRAPH_HOST: "https://your-tigergraph-host.i.tgcloud.io",
              TIGERGRAPH_USERNAME: "tigergraph",
              TIGERGRAPH_PASSWORD: "your_password",
              TIGERGRAPH_SECRET: "your_secret_alias",
              GOOGLE_API_KEY: "AIzaSy...",
            },
          },
        },
      },
      null,
      2
    ),
    envVars: [
      { key: "TIGERGRAPH_HOST", desc: "TigerGraph Cloud or local instance URI", sample: "https://tg-instance.i.tgcloud.io" },
      { key: "TIGERGRAPH_SECRET", desc: "TigerGraph REST++ auth secret or token", sample: "your_secret_here" },
      { key: "GOOGLE_API_KEY", desc: "Gemini API key for embeddings & synthesis", sample: "AIzaSy..." },
    ],
    steps: [
      {
        title: "1. Install GRIP package",
        detail: "Install GRIP globally via pip or pipx so the `grip` CLI command is available on your PATH.",
        command: "pip install -U grip-protocol",
      },
      {
        title: "2. Add to Claude Code via CLI",
        detail: "Run the one-line command to register the GRIP MCP server with Claude Code:",
        command:
          "claude mcp add grip grip --transport stdio",
      },
      {
        title: "3. Pass Environment Variables",
        detail:
          "Provide credentials inline or set them in your active shell / ~/.claude.json environment configuration.",
        command:
          'claude mcp add grip -e TIGERGRAPH_HOST="https://..." -e TIGERGRAPH_SECRET="..." -e GOOGLE_API_KEY="..." grip',
      },
      {
        title: "4. Verify Connection",
        detail: "Launch Claude Code and check that all 50 tools are available:",
        command: "claude\n/mcp",
      },
    ],
    verificationPrompt:
      "Please call graphrag_status to verify the knowledge graph backend, then call graphrag_search for 'self-attention mechanism' and summarize the top retrieved papers.",
  },
  {
    id: "cursor",
    name: "Cursor IDE",
    badge: "Most Popular",
    badgeColor: "blue",
    description:
      "Add GRIP as an MCP server in Cursor Settings > Features > MCP or via workspace `.cursor/mcp.json`.",
    configFile: ".cursor/mcp.json",
    installCommand: "pip install -U grip-protocol",
    configJson: JSON.stringify(
      {
        mcpServers: {
          grip: {
            command: "grip",
            args: ["--transport", "stdio"],
            env: {
              TIGERGRAPH_HOST: "https://your-instance.i.tgcloud.io",
              TIGERGRAPH_USERNAME: "tigergraph",
              TIGERGRAPH_PASSWORD: "your_password",
              TIGERGRAPH_SECRET: "your_secret",
              GOOGLE_API_KEY: "AIzaSy...",
            },
          },
        },
      },
      null,
      2
    ),
    envVars: [
      { key: "TIGERGRAPH_HOST", desc: "TigerGraph REST++ endpoint", sample: "https://tg-instance.i.tgcloud.io" },
      { key: "TIGERGRAPH_SECRET", desc: "Secret generated in TigerGraph Admin Portal", sample: "secret_token_123" },
      { key: "GOOGLE_API_KEY", desc: "Gemini 2.5 Flash / Embeddings API Key", sample: "AIzaSy..." },
    ],
    steps: [
      {
        title: "1. Install GRIP",
        detail: "Install the wheel in your system or project virtual environment:",
        command: "pip install -U grip-protocol",
      },
      {
        title: "2. Create `.cursor/mcp.json`",
        detail: "Create or edit `.cursor/mcp.json` in your repository root with the configuration shown below.",
      },
      {
        title: "3. Enable in Settings",
        detail: "Open Cursor Settings -> Features -> MCP -> Click 'Refresh' or restart Cursor. You should see 'grip (50 tools)' with a green status badge.",
      },
      {
        title: "4. Prompt Cursor Composer",
        detail: "In Cursor Composer (Ctrl+I / Cmd+I), prompt Cursor with agent mode enabled to invoke GRIP tools.",
      },
    ],
    verificationPrompt:
      "Check graphrag_schema to see all entity types in our graph, then expand the neighborhood around paper '2608.30052' using graphrag_neighborhood.",
  },
  {
    id: "cline",
    name: "Cline",
    badge: "Autonomous Agent",
    badgeColor: "green",
    description:
      "Autonomous coding agent extension for VS Code. Fully supports all 50 GRIP tools for multi-step reasoning.",
    configFile: "~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json",
    installCommand: "pipx install grip-protocol",
    configJson: JSON.stringify(
      {
        mcpServers: {
          "grip-graphrag": {
            command: "grip",
            args: ["--transport", "stdio"],
            env: {
              TIGERGRAPH_HOST: "https://tg-instance.i.tgcloud.io",
              TIGERGRAPH_USERNAME: "tigergraph",
              TIGERGRAPH_PASSWORD: "your_password",
              TIGERGRAPH_SECRET: "your_secret",
              GOOGLE_API_KEY: "AIzaSy...",
            },
            disabled: false,
            autoApprove: [
              "graphrag_search",
              "graphrag_schema",
              "graphrag_status",
              "graphrag_entity",
              "graphrag_neighborhood",
              "graphrag_stats_summary"
            ],
          },
        },
      },
      null,
      2
    ),
    envVars: [
      { key: "TIGERGRAPH_HOST", desc: "TigerGraph endpoint", sample: "https://your-tg.i.tgcloud.io" },
      { key: "TIGERGRAPH_SECRET", desc: "TigerGraph secret alias", sample: "my_secret_token" },
      { key: "GOOGLE_API_KEY", desc: "Gemini API key", sample: "AIzaSy..." },
    ],
    steps: [
      {
        title: "1. Install GRIP CLI",
        detail: "We recommend `pipx install grip-protocol` for global executable isolation:",
        command: "pipx install grip-protocol",
      },
      {
        title: "2. Open Cline MCP Settings",
        detail: "In VS Code, click the Cline robot icon in sidebar -> click the Server icon (MCP Servers) -> 'Configure MCP Servers'.",
      },
      {
        title: "3. Paste Server Config",
        detail: "Paste the `grip-graphrag` JSON block into `cline_mcp_settings.json` and save.",
      },
      {
        title: "4. Auto-Approve Read Tools",
        detail: "Add safe read operations (search, schema, entity) to `autoApprove` for seamless agent workflows.",
      },
    ],
    verificationPrompt:
      "Run graphrag_agent_investigate on query: 'Which neural architectures address long context memory?' and extract verified evidence chains.",
  },
  {
    id: "opencode",
    name: "OpenCode & Roo Code",
    badge: "Open Source",
    badgeColor: "amber",
    description:
      "Open-source VS Code agentic extensions (Roo Code / Roo-Cline / OpenCode) with full MCP protocol compliance.",
    configFile: "~/.vscode/extensions/.../roo_mcp_settings.json",
    installCommand: "pip install -U grip-protocol",
    configJson: JSON.stringify(
      {
        mcpServers: {
          grip: {
            command: "grip",
            args: ["--transport", "stdio"],
            env: {
              TIGERGRAPH_HOST: "https://tg-instance.i.tgcloud.io",
              TIGERGRAPH_USERNAME: "tigergraph",
              TIGERGRAPH_PASSWORD: "your_password",
              TIGERGRAPH_SECRET: "your_secret",
              GOOGLE_API_KEY: "AIzaSy...",
            },
          },
        },
      },
      null,
      2
    ),
    envVars: [
      { key: "TIGERGRAPH_HOST", desc: "Target Graph Backend", sample: "https://tg.tgcloud.io" },
      { key: "GOOGLE_API_KEY", desc: "Gemini Model & Embedding Key", sample: "AIzaSy..." },
    ],
    steps: [
      {
        title: "1. Install GRIP",
        detail: "Ensure `grip` is installed in your python path:",
        command: "pip install grip-protocol",
      },
      {
        title: "2. Add to MCP Settings",
        detail: "Open Roo Code Settings -> MCP Tab -> Click 'Edit MCP Settings' -> Add `grip`.",
      },
      {
        title: "3. Test In Roo Chat",
        detail: "Ask Roo to call `graphrag_status` to confirm connection.",
      },
    ],
    verificationPrompt:
      "Introspect our graph using graphrag_schema, then tell me the top vertex types and their counts.",
  },
  {
    id: "codex-openai",
    name: "OpenAI Codex & Custom GPTs",
    badge: "HTTP / SSE",
    badgeColor: "green",
    description:
      "Connect OpenAI Agents, Assistant API, or Custom GPTs via GRIP's built-in Streamable HTTP or SSE transport.",
    configFile: "Native HTTP endpoint or OpenAPI manifest",
    installCommand: "grip --transport streamable-http --port 8000",
    configJson: JSON.stringify(
      {
        openapi: "3.1.0",
        info: {
          title: "GRIP Knowledge Graph MCP API",
          version: "0.4.0",
        },
        servers: [
          {
            url: "http://localhost:8000",
            description: "GRIP Streamable HTTP Server",
          },
        ],
      },
      null,
      2
    ),
    envVars: [
      { key: "TIGERGRAPH_HOST", desc: "TigerGraph REST++ endpoint", sample: "https://..." },
      { key: "GOOGLE_API_KEY", desc: "Gemini API key", sample: "AIzaSy..." },
    ],
    steps: [
      {
        title: "1. Launch GRIP in Streamable HTTP Mode",
        detail: "Start the GRIP MCP server with HTTP/SSE transport listening on host & port:",
        command: "grip --transport streamable-http --host 0.0.0.0 --port 8000",
      },
      {
        title: "2. Expose via Tunnel (Optional)",
        detail: "If connecting external cloud agents (e.g. OpenAI Actions / LangSmith), tunnel the port:",
        command: "ngrok http 8000",
      },
      {
        title: "3. Register Tools in OpenAI Agent",
        detail: "Point your OpenAI assistant or LangChain/LangGraph agent to `http://localhost:8000/mcp`.",
      },
    ],
    verificationPrompt:
      "Execute a batch search using graphrag_batch comparing queries 'transformers' and 'graph neural networks'.",
  },
  {
    id: "windsurf",
    name: "Windsurf",
    badge: "Codeium Agent",
    badgeColor: "blue",
    description:
      "Codeium's agentic IDE (Cascade). Add GRIP to `~/.codeium/windsurf/mcp_config.json` for live graph context.",
    configFile: "~/.codeium/windsurf/mcp_config.json",
    installCommand: "pip install -U grip-protocol",
    configJson: JSON.stringify(
      {
        mcpServers: {
          grip: {
            command: "grip",
            args: ["--transport", "stdio"],
            env: {
              TIGERGRAPH_HOST: "https://your-instance.i.tgcloud.io",
              TIGERGRAPH_USERNAME: "tigergraph",
              TIGERGRAPH_PASSWORD: "your_password",
              TIGERGRAPH_SECRET: "your_secret",
              GOOGLE_API_KEY: "AIzaSy...",
            },
          },
        },
      },
      null,
      2
    ),
    envVars: [
      { key: "TIGERGRAPH_HOST", desc: "TigerGraph endpoint", sample: "https://tg-instance.i.tgcloud.io" },
      { key: "GOOGLE_API_KEY", desc: "Gemini API key", sample: "AIzaSy..." },
    ],
    steps: [
      {
        title: "1. Install GRIP",
        detail: "Install `grip-protocol` in your environment:",
        command: "pip install grip-protocol",
      },
      {
        title: "2. Edit Windsurf MCP Config",
        detail: "Open `~/.codeium/windsurf/mcp_config.json` and insert the `grip` server specification.",
      },
      {
        title: "3. Refresh Windsurf Cascade",
        detail: "Open Cascade chat -> click hammer / tools icon to see all 50 graphrag_* tools available.",
      },
    ],
    verificationPrompt:
      "Search the graph with graphrag_search for 'GNN recommendations' with format_text='markdown'.",
  },
  {
    id: "zed",
    name: "Zed Editor",
    badge: "Rust Powered",
    badgeColor: "purple",
    description:
      "High performance editor with native Model Context Protocol context server support.",
    configFile: "~/.config/zed/settings.json",
    installCommand: "pip install -U grip-protocol",
    configJson: JSON.stringify(
      {
        context_servers: {
          grip: {
            command: {
              path: "grip",
              args: ["--transport", "stdio"],
              env: {
                TIGERGRAPH_HOST: "https://your-instance.i.tgcloud.io",
                TIGERGRAPH_USERNAME: "tigergraph",
                TIGERGRAPH_PASSWORD: "your_password",
                TIGERGRAPH_SECRET: "your_secret",
                GOOGLE_API_KEY: "AIzaSy...",
              },
            },
          },
        },
      },
      null,
      2
    ),
    envVars: [
      { key: "TIGERGRAPH_HOST", desc: "TigerGraph URI", sample: "https://tg-instance.i.tgcloud.io" },
      { key: "GOOGLE_API_KEY", desc: "Gemini API key", sample: "AIzaSy..." },
    ],
    steps: [
      {
        title: "1. Install GRIP",
        detail: "Ensure `grip` is installed in your python environment:",
        command: "pip install grip-protocol",
      },
      {
        title: "2. Update Zed Settings",
        detail: "Press `Cmd+,` or edit `~/.config/zed/settings.json` and add `context_servers` block.",
      },
      {
        title: "3. Engage in Zed Assistant",
        detail: "Open Zed Assistant (`Cmd+?`), type `/prompt` and query using graph context.",
      },
    ],
    verificationPrompt:
      "Check graph statistics with graphrag_stats_summary and summarize graph density.",
  },
  {
    id: "python-langgraph",
    name: "Python SDK / LangGraph",
    badge: "Programmatic",
    badgeColor: "amber",
    description:
      "Direct programmatic integration using Python MCP client, LangGraph, CrewAI, or LlamaIndex.",
    configFile: "agent.py",
    installCommand: "pip install grip-protocol mcp langchain-community langgraph",
    configJson: `# agent_graphrag.py
import asyncio
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    server_params = StdioServerParameters(
        command="grip",
        args=["--transport", "stdio"],
        env={**os.environ}
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Call any of the 50 GRIP tools
            res = await session.call_tool("graphrag_search", {
                "query": "self-attention transformer mechanisms",
                "top_k": 5
            })
            print(res.content[0].text)

if __name__ == "__main__":
    asyncio.run(main())
`,
    envVars: [
      { key: "TIGERGRAPH_HOST", desc: "Backend host", sample: "https://..." },
      { key: "GOOGLE_API_KEY", desc: "Gemini key", sample: "AIzaSy..." },
    ],
    steps: [
      {
        title: "1. Install Dependencies",
        detail: "Install grip-protocol and official mcp client SDK:",
        command: "pip install grip-protocol mcp",
      },
      {
        title: "2. Run Script",
        detail: "Execute your script with TigerGraph & Gemini environment variables set:",
        command: "python agent_graphrag.py",
      },
    ],
    verificationPrompt:
      "Run python agent_graphrag.py to see real-time subgraph retrieval results.",
  },
];

export default function ConnectPage() {
  const [selectedId, setSelectedId] = useState<string>("claude-code");

  const guide = GUIDES.find((g) => g.id === selectedId) || GUIDES[0];

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 space-y-10">
      {/* Header */}
      <div className="rounded-2xl border-4 border-black bg-white p-8 shadow-brutal-xl space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge color="amber">STEP-BY-STEP SETUP</Badge>
          <Badge color="green">v0.4.0 VERIFIED</Badge>
          <Badge color="blue">50 MCP TOOLS</Badge>
        </div>
        <h1 className="text-3xl md:text-5xl font-black uppercase tracking-tight text-black">
          Connect GRIP MCP to Your Agentic IDE
        </h1>
        <p className="max-w-3xl font-mono text-sm md:text-base font-bold text-black/80 leading-relaxed">
          Enterprise GraphRAG across every major AI IDE and developer agent. Choose
          your environment below for step-by-step instructions, copyable configuration
          files, environment variables, and verification prompts.
        </p>
      </div>

      {/* IDE Tabs Selector */}
      <div className="flex flex-wrap gap-2 border-b-4 border-black pb-4">
        {GUIDES.map((g) => {
          const active = g.id === selectedId;
          return (
            <button
              key={g.id}
              onClick={() => setSelectedId(g.id)}
              type="button"
              className={`flex items-center gap-2 rounded-xl border-3 border-black px-4 py-2.5 font-mono text-xs md:text-sm font-black uppercase tracking-wider transition-all ${
                active
                  ? "bg-[#FFE600] text-black shadow-brutal translate-x-[-2px] translate-y-[-2px]"
                  : "bg-white text-black shadow-brutal-xs hover:bg-yellow-50 hover:translate-x-[-1px] hover:translate-y-[-1px]"
              }`}
            >
              <span>{g.name}</span>
              <span
                className={`rounded border border-black px-1.5 py-0.2 text-[10px] ${
                  active ? "bg-black text-[#FFE600]" : "bg-gray-100 text-black"
                }`}
              >
                {g.badge}
              </span>
            </button>
          );
        })}
      </div>

      {/* Guide Content Display */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left column: Steps & Config */}
        <div className="lg:col-span-7 space-y-6">
          <Card
            title={`${guide.name} Integration Guide`}
            subtitle={guide.description}
            className="border-3 border-black"
          >
            <div className="space-y-6">
              {/* Step list */}
              <div className="space-y-4">
                {guide.steps.map((step, idx) => (
                  <div
                    key={step.title}
                    className="rounded-xl border-2 border-black bg-[#F7F5EE] p-4 shadow-brutal-xs space-y-2"
                  >
                    <div className="flex items-center gap-2">
                      <span className="flex h-6 w-6 items-center justify-center rounded-md border border-black bg-[#FFE600] font-mono text-xs font-black">
                        {idx + 1}
                      </span>
                      <h4 className="font-mono text-xs font-black uppercase text-black">
                        {step.title}
                      </h4>
                    </div>
                    <p className="font-mono text-xs font-semibold text-black/75">
                      {step.detail}
                    </p>
                    {step.command && (
                      <CodeBlock code={step.command} language="bash" />
                    )}
                  </div>
                ))}
              </div>

              {/* Config File Box */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-black uppercase text-black flex items-center gap-1.5">
                    <Boxes className="h-4 w-4" />
                    Configuration Payload:
                  </span>
                  <span className="font-mono text-[11px] font-bold text-black/60">
                    File: {guide.configFile}
                  </span>
                </div>
                <CodeBlock
                  code={guide.configJson}
                  language={guide.id === "python-langgraph" ? "python" : "json"}
                  filename={guide.configFile}
                />
              </div>
            </div>
          </Card>

          {/* Test Verification Box */}
          <div className="rounded-xl border-3 border-black bg-[#55EFC4] p-6 shadow-brutal space-y-3">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-black" />
              <h3 className="font-mono text-sm font-black uppercase text-black">
                Verification Prompt to Test in {guide.name}
              </h3>
            </div>
            <p className="font-mono text-xs font-bold text-black/80">
              Paste this prompt into your agent to verify all tool capabilities, schema discovery, and graph retrieval:
            </p>
            <div className="rounded-lg border-2 border-black bg-white p-4 font-mono text-xs font-bold text-black shadow-brutal-xs">
              &ldquo;{guide.verificationPrompt}&rdquo;
            </div>
          </div>
        </div>

        {/* Right column: Environment variables & Tool surface summary */}
        <div className="lg:col-span-5 space-y-6">
          {/* Environment Variables Card */}
          <Card
            title="Required Environment Variables"
            subtitle="Configure these credentials in your shell, .env, or IDE config"
          >
            <div className="space-y-3">
              {guide.envVars.map((env) => (
                <div
                  key={env.key}
                  className="rounded-lg border-2 border-black bg-[#F7F5EE] p-3 shadow-brutal-xs space-y-1"
                >
                  <div className="flex items-center justify-between">
                    <code className="rounded bg-black px-1.5 py-0.5 font-mono text-[11px] font-black text-[#FFE600]">
                      {env.key}
                    </code>
                    <Key className="h-3.5 w-3.5 text-black/60" />
                  </div>
                  <p className="font-mono text-[11px] font-bold text-black/70">
                    {env.desc}
                  </p>
                  <p className="font-mono text-[10px] text-black/50 truncate">
                    Ex: {env.sample}
                  </p>
                </div>
              ))}

              <div className="rounded-lg border-2 border-dashed border-black bg-white p-3 font-mono text-[11px] font-bold text-black/70">
                <span className="font-black text-black">PRO TIP:</span> Place a <code>.env</code> file in your workspace root. GRIP automatically parses `.env` on startup.
              </div>
            </div>
          </Card>

          {/* 50 Tools Quick Reference Pill Card */}
          <div className="rounded-xl border-3 border-black bg-white p-5 shadow-brutal space-y-4">
            <div className="flex items-center justify-between border-b-2 border-black pb-2">
              <h3 className="font-mono text-xs font-black uppercase text-black flex items-center gap-1.5">
                <Zap className="h-4 w-4 text-black" />
                Included 50 MCP Tools
              </h3>
              <Badge color="green">v0.4.0</Badge>
            </div>

            <div className="space-y-2 text-xs font-mono">
              <div className="flex justify-between items-center py-1 border-b border-black/10">
                <span className="font-bold">Retrieval (C1)</span>
                <span className="text-black/60">graphrag_search, local, global, hybrid</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-black/10">
                <span className="font-bold">Schema &amp; Stats (C3)</span>
                <span className="text-black/60">graphrag_schema, entity_types, sample</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-black/10">
                <span className="font-bold">Agentic Harness</span>
                <span className="text-black/60">graphrag_agent_investigate</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-black/10">
                <span className="font-bold">Conflict Resolution (C19)</span>
                <span className="text-black/60">graphrag_resolve_conflicts</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-black/10">
                <span className="font-bold">Provenance Audit (C5)</span>
                <span className="text-black/60">graphrag_provenance, trajectory</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-black/10">
                <span className="font-bold">Batch Runner (C17)</span>
                <span className="text-black/60">graphrag_batch (up to 25 calls)</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-black/10">
                <span className="font-bold">Construction / Ingest (C4)</span>
                <span className="text-black/60">graphrag_ingest, delete_doc</span>
              </div>
            </div>

            <a
              href="/protocol"
              className="inline-flex w-full items-center justify-center gap-1.5 rounded-lg border-2 border-black bg-[#FFE600] py-2 font-mono text-xs font-black uppercase text-black shadow-brutal-xs hover:translate-x-[-1px] hover:translate-y-[-1px] transition-all"
            >
              <span>Explore All 20 Contracts</span>
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          </div>

          {/* Production Grade Banner */}
          <div className="rounded-xl border-3 border-black bg-[#A29BFE] p-5 shadow-brutal space-y-2">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-black" />
              <h4 className="font-mono text-xs font-black uppercase text-black">
                Production-Grade Backend
              </h4>
            </div>
            <p className="font-mono text-[11px] font-bold text-black/80 leading-relaxed">
              Every tool returns real data executed directly against your active TigerGraph or Neo4j backend. Responses adhere strictly to RFC JSON schemas.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
