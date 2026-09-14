/* The confidence meter.
 *
 * Flat, square, and one colour. It was a rounded capsule with a three-stop
 * gradient sweeping cyan through foam, which is the opposite of both rules the
 * direction actually states: square edges and flat fills. The mockup's queue
 * meters are a 4px imperial rule against an ink-4 remainder, and that is what
 * this is now.
 *
 * The number stays beside the bar rather than inside it. Length is a fast
 * comparison across a column and a poor way to read an exact value, so the two
 * do different jobs. */
export function MeterBar({ value, label }: { value: number | null; label: string }) {
  if (value === null) {
    return <span className="text-ink-3">{label}</span>;
  }

  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return (
    <div className="flex items-center gap-2">
      <div
        className="h-1 w-20 shrink-0 overflow-hidden bg-rule-2"
        role="meter"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
      >
        <div className="h-full bg-imperial" style={{ width: `${pct}%` }} />
      </div>
      <span className="font-mono text-xs tabular-nums text-ink-2">{label}</span>
    </div>
  );
}
