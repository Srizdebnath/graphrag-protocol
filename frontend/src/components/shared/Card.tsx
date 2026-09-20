import type { ReactNode } from "react";

interface CardProps {
  title?: string;
  subtitle?: string;
  children: ReactNode;
  className?: string;
}

export default function Card({ title, subtitle, children, className = "" }: CardProps) {
  return (
    <div className={`rounded-xl border-3 border-black bg-white shadow-brutal transition-all ${className}`}>
      {(title || subtitle) && (
        <div className="border-b-3 border-black bg-[#FEF08A] px-5 py-3">
          {title && (
            <h3 className="text-sm font-black uppercase tracking-wider text-black">{title}</h3>
          )}
          {subtitle && (
            <p className="mt-0.5 text-xs font-semibold text-black/75">{subtitle}</p>
          )}
        </div>
      )}
      <div className="p-5">{children}</div>
    </div>
  );
}
