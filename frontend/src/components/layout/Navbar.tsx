"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Menu, X, Copy, Check, ExternalLink } from "lucide-react";

interface NavLink {
  href: string;
  label: string;
  badge?: string;
  highlight?: boolean;
}

const mainLinks: NavLink[] = [
  { href: "/connect", label: "Connect IDEs", badge: "8 IDEs", highlight: true },
  { href: "/protocol", label: "Contracts", badge: "20 RFCs" },
  { href: "/docs#tools", label: "50 Tools", badge: "MCP" },
  { href: "/docs", label: "Docs" },
  { href: "/query", label: "Query Lab" },
  { href: "/benchmark", label: "Benchmarks" },
  { href: "/graph", label: "Graph 3D" },
  { href: "/ingest", label: "Ingest" },
];

export default function Navbar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const copyInstallCommand = () => {
    navigator.clipboard.writeText("pip install grip-protocol");
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <nav className="sticky top-0 z-50 border-b-4 border-black bg-[#FFE600] shadow-[0_4px_0_0_#000]">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-3 px-4">
        {/* Brand Logo & Version */}
        <div className="flex items-center gap-2.5 shrink-0">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 -rotate-1 rounded-lg border-2 border-black bg-black px-3 py-1.5 font-mono text-sm font-black uppercase tracking-wider text-[#FFE600] shadow-brutal-sm transition-transform hover:rotate-0 hover:scale-105 active:scale-95"
          >
            <span className="text-[#55EFC4]">GRIP</span> {"//"} PROTOCOL
          </Link>
          <a
            href="https://pypi.org/project/grip-protocol/0.4.0/"
            target="_blank"
            rel="noopener noreferrer"
            className="hidden sm:inline-flex items-center gap-1.5 rounded-md border-2 border-black bg-white px-2 py-0.5 font-mono text-[10px] font-black uppercase text-black shadow-brutal-xs hover:bg-emerald-100 hover:translate-x-[-1px] hover:translate-y-[-1px] transition-all"
            title="View v0.4.0 on PyPI"
          >
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            <span>v0.4.0</span>
            <ExternalLink className="h-2.5 w-2.5 text-black/60" />
          </a>
        </div>

        {/* Desktop Nav Links */}
        <div className="hidden xl:flex items-center gap-1.5">
          {mainLinks.map((link) => {
            const active =
              link.href === "/"
                ? pathname === "/"
                : link.href.startsWith("/docs#")
                ? pathname === "/docs"
                : pathname.startsWith(link.href);

            return (
              <Link
                key={link.href}
                href={link.href}
                className={`relative inline-flex items-center gap-1 rounded-md border-2 border-black px-2.5 py-1 font-mono text-xs font-black uppercase tracking-wider transition-all ${
                  active && !link.href.includes("#")
                    ? "bg-black text-white shadow-brutal-xs translate-x-[-1px] translate-y-[-1px]"
                    : link.highlight
                    ? "bg-[#55EFC4] text-black shadow-brutal-xs hover:bg-[#48d6af] hover:translate-x-[-1px] hover:translate-y-[-1px]"
                    : "bg-white text-black shadow-brutal-xs hover:bg-yellow-100 hover:translate-x-[-1px] hover:translate-y-[-1px]"
                }`}
              >
                <span>{link.label}</span>
                {link.badge && (
                  <span
                    className={`rounded border border-black px-1 py-0.2 text-[9px] font-black leading-tight ${
                      active && !link.href.includes("#")
                        ? "bg-[#FFE600] text-black"
                        : link.highlight
                        ? "bg-black text-[#55EFC4]"
                        : "bg-black/10 text-black"
                    }`}
                  >
                    {link.badge}
                  </span>
                )}
                {link.highlight && !active && (
                  <span className="absolute -top-1.5 -right-1.5 h-2.5 w-2.5 rounded-full bg-red-500 border border-black animate-pulse" />
                )}
              </Link>
            );
          })}
        </div>

        {/* Compressed Desktop Links for standard laptops (lg to xl) */}
        <div className="hidden lg:flex xl:hidden items-center gap-1">
          <Link
            href="/connect"
            className="rounded-md border-2 border-black bg-[#55EFC4] px-2 py-1 font-mono text-xs font-black uppercase shadow-brutal-xs hover:bg-[#48d6af]"
          >
            Connect IDEs
          </Link>
          <Link
            href="/protocol"
            className="rounded-md border-2 border-black bg-white px-2 py-1 font-mono text-xs font-black uppercase shadow-brutal-xs hover:bg-yellow-100"
          >
            Contracts (20)
          </Link>
          <Link
            href="/docs"
            className="rounded-md border-2 border-black bg-white px-2 py-1 font-mono text-xs font-black uppercase shadow-brutal-xs hover:bg-yellow-100"
          >
            Docs &amp; Tools
          </Link>
          <Link
            href="/query"
            className="rounded-md border-2 border-black bg-white px-2 py-1 font-mono text-xs font-black uppercase shadow-brutal-xs hover:bg-yellow-100"
          >
            Query
          </Link>
          <Link
            href="/benchmark"
            className="rounded-md border-2 border-black bg-white px-2 py-1 font-mono text-xs font-black uppercase shadow-brutal-xs hover:bg-yellow-100"
          >
            Benchmarks
          </Link>
          <Link
            href="/graph"
            className="rounded-md border-2 border-black bg-white px-2 py-1 font-mono text-xs font-black uppercase shadow-brutal-xs hover:bg-yellow-100"
          >
            Graph
          </Link>
          <Link
            href="/ingest"
            className="rounded-md border-2 border-black bg-white px-2 py-1 font-mono text-xs font-black uppercase shadow-brutal-xs hover:bg-yellow-100"
          >
            Ingest
          </Link>
        </div>

        {/* Right Action Buttons */}
        <div className="flex items-center gap-2">
          {/* Quick Install Copy Pill */}
          <button
            onClick={copyInstallCommand}
            type="button"
            className="hidden md:inline-flex items-center gap-1.5 rounded-lg border-2 border-black bg-black px-2.5 py-1 font-mono text-xs font-black uppercase text-white shadow-brutal-xs hover:bg-slate-900 active:translate-x-[1px] active:translate-y-[1px] transition-all"
            title="Click to copy pip install command"
          >
            {copied ? (
              <>
                <Check className="h-3.5 w-3.5 text-[#55EFC4]" />
                <span className="text-[#55EFC4]">COPIED!</span>
              </>
            ) : (
              <>
                <Copy className="h-3.5 w-3.5 text-[#FFE600]" />
                <span className="text-zinc-200">pip install grip</span>
              </>
            )}
          </button>

          {/* GitHub Repo Button */}
          <a
            href="https://github.com/Srizdebnath/graphrag-protocol"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded-lg border-2 border-black bg-white px-2.5 py-1 font-mono text-xs font-black uppercase text-black shadow-brutal-xs hover:bg-yellow-100 active:translate-x-[1px] active:translate-y-[1px] transition-all"
            title="GitHub Repository"
          >
            <svg
              className="h-3.5 w-3.5 fill-current"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                fillRule="evenodd"
                clipRule="evenodd"
                d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
              />
            </svg>
            <span className="hidden sm:inline">GitHub</span>
          </a>

          {/* Mobile Menu Button */}
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            type="button"
            className="lg:hidden rounded-lg border-2 border-black bg-white p-1.5 shadow-brutal-xs active:translate-x-[1px] active:translate-y-[1px]"
            aria-label="Toggle navigation menu"
          >
            {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {/* Mobile Nav Drawer */}
      {mobileOpen && (
        <div className="lg:hidden border-t-3 border-black bg-[#F7F5EE] p-4 space-y-2.5">
          {/* Mobile Install Snippet */}
          <div className="flex items-center justify-between rounded-lg border-2 border-black bg-black p-3 text-white shadow-brutal-xs">
            <span className="font-mono text-xs font-bold text-[#FFE600]">pip install grip-protocol</span>
            <button
              onClick={copyInstallCommand}
              type="button"
              className="rounded border border-white bg-white/10 px-2 py-1 font-mono text-[10px] font-black uppercase text-[#55EFC4]"
            >
              {copied ? "Copied!" : "Copy"}
            </button>
          </div>

          <div className="grid grid-cols-2 gap-2">
            {mainLinks.map((link) => {
              const active =
                link.href === "/"
                  ? pathname === "/"
                  : link.href.startsWith("/docs#")
                  ? pathname === "/docs"
                  : pathname.startsWith(link.href);

              return (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={() => setMobileOpen(false)}
                  className={`flex items-center justify-between rounded-lg border-2 border-black px-3 py-2 font-mono text-xs font-black uppercase transition-all ${
                    active && !link.href.includes("#")
                      ? "bg-black text-white shadow-brutal-xs"
                      : link.highlight
                      ? "bg-[#55EFC4] text-black shadow-brutal-xs"
                      : "bg-white text-black shadow-brutal-xs hover:bg-yellow-100"
                  }`}
                >
                  <span>{link.label}</span>
                  {link.badge && (
                    <span className="rounded bg-black/10 px-1 text-[9px]">
                      {link.badge}
                    </span>
                  )}
                </Link>
              );
            })}
          </div>

          {/* External links in mobile menu */}
          <div className="flex items-center gap-2 pt-2 border-t-2 border-black/20">
            <a
              href="https://pypi.org/project/grip-protocol/0.4.0/"
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 text-center rounded-lg border-2 border-black bg-white py-2 font-mono text-xs font-black uppercase shadow-brutal-xs"
            >
              PyPI v0.4.0 &rarr;
            </a>
            <a
              href="https://github.com/Srizdebnath/graphrag-protocol"
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 text-center rounded-lg border-2 border-black bg-white py-2 font-mono text-xs font-black uppercase shadow-brutal-xs"
            >
              GitHub &rarr;
            </a>
          </div>
        </div>
      )}
    </nav>
  );
}
