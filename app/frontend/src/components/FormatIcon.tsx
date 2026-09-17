export function FormatIcon({ format }: { format: string }) {
  const f = format.toLowerCase();
  if (f === "csv") {
    return (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" className="inline-block text-slate-400" aria-hidden>
        <rect x="3" y="4" width="18" height="16" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
        <path d="M3 10h18M9 4v16M15 4v16" stroke="currentColor" strokeWidth="1.2" />
      </svg>
    );
  }
  if (f === "json") {
    return (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" className="inline-block text-slate-400" aria-hidden>
        <path
          d="M8 4c-2 0-2.5 1-2.5 3v3c0 1.2-.5 2-2 2 1.5 0 2 .8 2 2v3c0 2 .5 3 2.5 3M16 4c2 0 2.5 1 2.5 3v3c0 1.2.5 2 2 2-1.5 0-2 .8-2 2v3c0 2-.5 3-2.5 3"
          stroke="currentColor"
          strokeWidth="1.4"
          strokeLinecap="round"
        />
      </svg>
    );
  }
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" className="inline-block text-slate-400" aria-hidden>
      <path d="M6 3h9l5 5v13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z" stroke="currentColor" strokeWidth="1.5" />
      <path d="M15 3v5h5" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}
