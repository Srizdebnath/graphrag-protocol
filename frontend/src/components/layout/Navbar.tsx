"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Home" },
  { href: "/query", label: "Query" },
  { href: "/benchmark", label: "Benchmark" },
  { href: "/protocol", label: "Protocol" },
  { href: "/graph", label: "Graph" },
  { href: "/ingest", label: "Ingest & Stream" },
];

export default function Navbar() {
  const pathname = usePathname();

  return (
    <nav className="sticky top-0 z-50 border-b-4 border-black bg-[#FFE600] shadow-[0_4px_0_0_#000]">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4">
        <div className="flex items-center gap-6">
          <Link
            href="/"
            className="inline-block -rotate-1 rounded-md border-2 border-black bg-black px-3 py-1 font-mono text-sm font-black uppercase tracking-wider text-[#FFE600] shadow-brutal-sm transition-transform hover:rotate-0"
          >
            GRIP // PROTOCOL
          </Link>
          <div className="hidden sm:flex items-center gap-2">
            {links.map((link) => {
              const active = link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`rounded-md border-2 border-black px-3 py-1.5 font-mono text-xs font-black uppercase tracking-wider transition-all ${
                    active
                      ? "bg-black text-white shadow-brutal-sm translate-x-[-1px] translate-y-[-1px]"
                      : "bg-white text-black shadow-brutal-sm hover:bg-yellow-100 hover:translate-x-[-2px] hover:translate-y-[-2px] active:translate-x-[1px] active:translate-y-[1px]"
                  }`}
                >
                  {link.label}
                </Link>
              );
            })}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="hidden md:inline-flex items-center gap-1.5 rounded-md border-2 border-black bg-white px-2.5 py-1 font-mono text-[11px] font-black uppercase shadow-brutal-xs">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            LIVE PROTOCOL
          </span>
        </div>
      </div>
    </nav>
  );
}
