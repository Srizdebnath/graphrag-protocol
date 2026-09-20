interface BadgeProps {
  children: React.ReactNode;
  color?: "green" | "red" | "blue" | "amber" | "gray" | "purple";
  className?: string;
}

const colorClasses: Record<NonNullable<BadgeProps["color"]>, string> = {
  green: "bg-[#86EFAC] text-black",
  red: "bg-[#FDA4AF] text-black",
  blue: "bg-[#93C5FD] text-black",
  amber: "bg-[#FDE047] text-black",
  gray: "bg-[#E5E7EB] text-black",
  purple: "bg-[#D8B4FE] text-black",
};

export default function Badge({ children, color = "gray", className = "" }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-md border-2 border-black px-2 py-0.5 font-mono text-[11px] font-black uppercase tracking-wider shadow-brutal-xs ${colorClasses[color]} ${className}`}
    >
      {children}
    </span>
  );
}
