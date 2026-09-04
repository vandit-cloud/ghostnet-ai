export function MeterBar({ value, label }: { value: number | null; label: string }) {
  if (value === null) {
    return <span className="text-slate-500">{label}</span>;
  }

  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-20 shrink-0 overflow-hidden rounded-full border border-abyss-600/70 bg-abyss-700/70">
        <div className="h-full rounded-full bg-gradient-to-r from-cyan-dim via-cyan-accent to-foam-500" style={{ width: `${pct}%` }} />
      </div>
      <span className="font-mono text-xs tabular-nums text-slate-300">{label}</span>
    </div>
  );
}
