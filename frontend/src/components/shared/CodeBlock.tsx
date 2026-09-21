"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";

interface CodeBlockProps {
  code: string;
  language?: string;
  filename?: string;
  className?: string;
}

export default function CodeBlock({
  code,
  language = "bash",
  filename,
  className = "",
}: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy code: ", err);
    }
  };

  return (
    <div
      className={`rounded-xl border-3 border-black bg-black text-white shadow-brutal overflow-hidden ${className}`}
    >
      <div className="flex items-center justify-between border-b-2 border-white/20 bg-[#1e1e1e] px-4 py-2">
        <div className="flex items-center gap-2">
          <div className="flex gap-1.5">
            <span className="h-3 w-3 rounded-full border border-black bg-[#FF7675]" />
            <span className="h-3 w-3 rounded-full border border-black bg-[#FFE600]" />
            <span className="h-3 w-3 rounded-full border border-black bg-[#55EFC4]" />
          </div>
          {filename && (
            <span className="ml-2 font-mono text-xs font-bold text-[#FFE600]">
              {filename}
            </span>
          )}
          {!filename && language && (
            <span className="ml-2 font-mono text-xs font-bold uppercase tracking-wider text-white/60">
              {language}
            </span>
          )}
        </div>

        <button
          onClick={handleCopy}
          type="button"
          className="flex items-center gap-1.5 rounded-md border border-black bg-white px-2.5 py-1 font-mono text-[11px] font-black uppercase text-black shadow-brutal-xs hover:bg-[#FFE600] active:translate-x-[1px] active:translate-y-[1px] transition-all"
          title="Copy code to clipboard"
        >
          {copied ? (
            <>
              <Check className="h-3.5 w-3.5 text-emerald-600" />
              <span>COPIED!</span>
            </>
          ) : (
            <>
              <Copy className="h-3.5 w-3.5" />
              <span>COPY</span>
            </>
          )}
        </button>
      </div>

      <pre className="overflow-x-auto p-4 font-mono text-xs md:text-sm leading-relaxed text-[#55EFC4]">
        <code>{code}</code>
      </pre>
    </div>
  );
}
