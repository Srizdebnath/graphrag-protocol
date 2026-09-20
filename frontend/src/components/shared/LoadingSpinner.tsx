interface LoadingSpinnerProps {
  label?: string;
}

export default function LoadingSpinner({ label = "Loading..." }: LoadingSpinnerProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-12">
      <div className="h-10 w-10 animate-spin rounded-lg border-3 border-black bg-[#FFE600] shadow-brutal-sm" />
      <p className="font-mono text-xs font-black uppercase tracking-wider text-black">{label}</p>
    </div>
  );
}
