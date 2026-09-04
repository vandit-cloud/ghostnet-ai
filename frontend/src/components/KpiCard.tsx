import clsx from "clsx";

import { Panel } from "@/components/Panel";

export function KpiCard({
  label,
  value,
  tone = "neutral",
  live = false,
  hint,
}: {
  label: string;
  value: string | number;
  tone?: "neutral" | "critical" | "high" | "positive";
  live?: boolean;
  hint?: string;
}) {
  const toneStyles: Record<string, string> = {
    neutral: "text-slate-100",
    critical: "text-alert-critical",
    high: "text-alert-high",
    positive: "text-emerald-300",
  };
  const badgeStyles: Record<string, string> = {
    neutral: "border-abyss-600/80 text-slate-400",
    critical: "border-alert-critical/35 bg-alert-critical/10 text-alert-critical",
    high: "border-alert-high/35 bg-alert-high/10 text-alert-high",
    positive: "border-emerald-500/35 bg-emerald-500/10 text-emerald-300",
  };
  const badgeLabel =
    live ? "Live" : tone === "neutral" ? "Stable" : tone === "critical" ? "Priority" : tone === "high" ? "Elevated" : "Verified";

  return (
    <Panel glow={tone === "critical" ? "critical" : live ? "cyan" : "none"} className="min-h-[148px] p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] uppercase tracking-[0.28em] text-slate-400">{label}</p>
          <p className={clsx("mt-3 font-mono text-3xl font-semibold tabular-nums", toneStyles[tone])}>{value}</p>
        </div>
        <span
          className={clsx(
            "rounded-full border px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.24em]",
            live ? "border-cyan-accent/35 bg-cyan-accent/10 text-cyan-accent" : badgeStyles[tone]
          )}
        >
          {badgeLabel}
        </span>
      </div>
      {hint ? <p className="mt-4 max-w-[24ch] text-sm leading-6 text-slate-400">{hint}</p> : null}
    </Panel>
  );
}
