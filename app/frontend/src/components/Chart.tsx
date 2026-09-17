import { ATLANTIC, IMPERIAL } from "@/utils/palette";

export function BarListChart({
  data,
  labelKey,
  valueKey,
}: {
  data: Record<string, string | number>[];
  labelKey: string;
  valueKey: string;
}) {
  if (data.length === 0) {
    return <p className="text-sm text-slate-500">No data yet.</p>;
  }
  const max = Math.max(...data.map((d) => Number(d[valueKey]) || 0), 1);

  return (
    <div className="space-y-2">
      {data.map((row, i) => (
        <div key={i} className="rounded-2xl border border-abyss-600/60 bg-skytint/42 px-3 py-3">
          <div className="mb-2 flex items-center justify-between gap-3 text-sm">
            <span className="truncate text-slate-300">{row[labelKey]}</span>
            <span className="shrink-0 font-mono text-xs tabular-nums text-slate-400">{row[valueKey]}</span>
          </div>
          <div className="h-2.5 bg-abyss-700/80">
            <div
              className="h-2.5 bg-imperial"
              style={{ width: `${(Number(row[valueKey]) / max) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

export function TrendSparkline({ data }: { data: { date: string; count: number }[] }) {
  if (data.length === 0) {
    return <p className="text-sm text-slate-500">No detections in the last 14 days.</p>;
  }

  const max = Math.max(...data.map((d) => d.count), 1);
  const width = 320;
  const height = 60;
  const padding = 6;
  const stepX = data.length > 1 ? (width - padding * 2) / (data.length - 1) : 0;

  const coords = data.map((d, i) => ({
    x: padding + i * stepX,
    y: padding + (1 - d.count / max) * (height - padding * 2),
  }));

  const points = coords.map((c) => `${c.x},${c.y}`).join(" ");
  const areaPath = `M ${padding} ${height - padding} L ${points.replaceAll(" ", " L ")} L ${width - padding} ${height - padding} Z`;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-16 w-full" preserveAspectRatio="none">
      <defs>
        <linearGradient id="trend-fill" x1="0%" x2="0%" y1="0%" y2="100%">
          <stop offset="0%" stopColor={IMPERIAL} stopOpacity="0.18" />
          <stop offset="100%" stopColor={IMPERIAL} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={areaPath} fill="url(#trend-fill)" />
      {coords.length > 1 ? <polyline points={points} fill="none" stroke={IMPERIAL} strokeWidth={2} /> : null}
      {coords.map((c, i) => (
        <circle key={i} cx={c.x} cy={c.y} r={coords.length === 1 ? 3 : 2.4} fill={ATLANTIC} />
      ))}
    </svg>
  );
}
