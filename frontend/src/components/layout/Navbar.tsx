"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Menu, X } from "lucide-react";

const links = [
  { href: "/", label: "Home" },
  { href: "/connect", label: "Connect IDEs", highlight: true },
  { href: "/docs", label: "Docs" },
  { href: "/protocol", label: "Contracts (20)" },
  { href: "/query", label: "Query Lab" },
  { href: "/benchmark", label: "Benchmarks" },
  { href: "/graph", label: "Graph" },
  { href: "/ingest", label: "Ingest" },
];

export default function Navbar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <nav className="sticky top-0 z-50 border-b-4 border-black bg-[#FFE600] shadow-[0_4px_0_0_#000]">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4">
        {/* Brand Logo */}
        <div className="flex items-center gap-4">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 -rotate-1 rounded-lg border-2 border-black bg-black px-3 py-1.5 font-mono text-sm font-black uppercase tracking-wider text-[#FFE600] shadow-brutal-sm transition-transform hover:rotate-0"
          >
            <span className="text-[#55EFC4]">GRIP</span> {"//"} PROTOCOL
          </Link>

          {/* Desktop Nav Links */}
          <div className="hidden lg:flex items-center gap-1.5">
            {links.map((link) => {
              const active =
                link.href === "/"
                  ? pathname === "/"
                  : pathname.startsWith(link.href);
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`relative rounded-md border-2 border-black px-2.5 py-1 font-mono text-xs font-black uppercase tracking-wider transition-all ${
                    active
                      ? "bg-black text-white shadow-brutal-xs translate-x-[-1px] translate-y-[-1px]"
                      : link.highlight
                      ? "bg-[#55EFC4] text-black shadow-brutal-xs hover:bg-[#48d6af] hover:translate-x-[-1px] hover:translate-y-[-1px]"
                      : "bg-white text-black shadow-brutal-xs hover:bg-yellow-100 hover:translate-x-[-1px] hover:translate-y-[-1px]"
                  }`}
                >
                  {link.label}
                  {link.highlight && !active && (
                    <span className="absolute -top-1.5 -right-1.5 h-2.5 w-2.5 rounded-full bg-red-500 border border-black animate-pulse" />
                  )}
                </Link>
              );
            })}
          </div>
        </div>

        {/* Right Status Pill & Mobile Menu Toggle */}
        <div className="flex items-center gap-3">
          <span className="hidden sm:inline-flex items-center gap-1.5 rounded-md border-2 border-black bg-white px-2.5 py-1 font-mono text-[11px] font-black uppercase shadow-brutal-xs">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            v0.4.0 ON PYPI
          </span>

          {/* Mobile Menu Button */}
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            type="button"
            className="lg:hidden rounded-lg border-2 border-black bg-white p-1.5 shadow-brutal-xs active:translate-x-[1px] active:translate-y-[1px]"
          >
            {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {/* Mobile Nav Drawer */}
      {mobileOpen && (
        <div className="lg:hidden border-t-2 border-black bg-[#F7F5EE] p-4 space-y-2">
          {links.map((link) => {
            const active =
              link.href === "/"
                ? pathname === "/"
                : pathname.startsWith(link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setMobileOpen(false)}
                className={`block rounded-lg border-2 border-black px-4 py-2 font-mono text-xs font-black uppercase ${
                  active
                    ? "bg-black text-white shadow-brutal-xs"
                    : link.highlight
                    ? "bg-[#55EFC4] text-black shadow-brutal-xs"
                    : "bg-white text-black shadow-brutal-xs"
                }`}
              >
                {link.label}
              </Link>
            );
          })}
        </div>
      )}
    </nav>
  );
}
