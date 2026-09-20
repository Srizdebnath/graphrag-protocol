interface ErrorStateProps {
  message: string;
  hint?: string;
}

export default function ErrorState({ message, hint }: ErrorStateProps) {
  return (
    <div className="rounded-xl border-3 border-black bg-[#FDA4AF] p-5 shadow-brutal text-black">
      <div className="flex items-start gap-3.5">
        <span className="flex h-7 w-7 flex-none items-center justify-center rounded-md border-2 border-black bg-black font-mono text-sm font-black text-[#FFE600] shadow-brutal-xs">
          !
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-mono text-xs font-black uppercase tracking-wider text-black">Execution Error</p>
          <p className="mt-1 text-sm font-bold leading-snug text-black">{message}</p>
          {hint && (
            <p className="mt-2 inline-block rounded border-2 border-black bg-white px-2.5 py-1 font-mono text-xs font-semibold text-black shadow-brutal-xs">
              Hint: {hint}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
