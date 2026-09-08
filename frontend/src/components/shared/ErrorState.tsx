interface ErrorStateProps {
  message: string;
  hint?: string;
}

export default function ErrorState({ message, hint }: ErrorStateProps) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-4">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 flex h-5 w-5 flex-none items-center justify-center rounded-full bg-red-600 text-xs font-bold text-white">
          !
        </span>
        <div>
          <p className="text-sm font-semibold text-red-800">Error</p>
          <p className="mt-1 text-sm text-red-700">{message}</p>
          {hint && <p className="mt-1 text-xs text-red-600">{hint}</p>}
        </div>
      </div>
    </div>
  );
}
