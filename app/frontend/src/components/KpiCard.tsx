import clsx from "clsx";

import { Panel } from "@/components/Panel";

/* The KPI tile, in Atlantic.
 *
 * The number is the element. It is set in the display face at 56px in atlantic
 * blue -- not in the mono face at 30px as before -- because on a paper ground a
 * big quiet numeral carries further than a small bright one, and because this
 * is the same treatment the landing page gives its four hero statistics. The
 * label above and the hint below both recede to mono and ink-3.
 *
 * Only a tone that genuinely means something changes the ground: `critical`
 * takes the imperial fill so a priority tile is unmistakable in a row of five.
 * The rest stay paper and carry their tone in the badge alone. */
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
  const valueTone: Record<string, string> = {
    neutral: "text-atlantic",
    critical: "text-paper",
    high: "text-alert-high",
    positive: "text-emerald-500",
  };

  const badgeTone: Record<string, string> = {
    neutral: "border-rule text-ink-3",
    critical: "border-skytint/40 bg-skytint/20 text-skytint",
    high: "border-alert-high/50 text-alert-high",
    positive: "border-emerald-500/50 text-emerald-500",
  };

  const badgeLabel = live
    ? "Live"
    : tone === "neutral"
      ? "Stable"
      : tone === "critical"
        ? "Priority"
        : tone === "high"
          ? "Elevated"
          : "Verified";

  const accent = tone === "critical";

  return (
    <Panel tone={accent ? "accent" : live ? "tint" : "none"} className="min-h-[148px] p-[18px]">
      <div className="flex items-start justify-between gap-3">
        <p
          className={clsx(
            "font-mono text-[10.5px] uppercase tracking-[0.13em]",
            accent ? "text-skytint/75" : "text-ink-3"
          )}
        >
          {label}
        </p>
        <span
          className={clsx(
            "shrink-0 border px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.12em]",
            live && !accent ? "border-imperial bg-imperial text-paper" : badgeTone[tone]
          )}
        >
          {badgeLabel}
        </span>
      </div>

      {/* 56px is right for a numeral and wrong for a word. The dashboard passes
          the job STAGE through here ("DETECTION"), which needs 203px at that
          size against a 174px tile in the five-column grid -- and `.panel` has
          `overflow: hidden`, so it sheared the last letter off with no ellipsis
          and no scrollbar. Size by what the value actually is. */}
      <p
        className={clsx(
          "mt-2.5 font-display font-extrabold tabular-nums",
          typeof value === "number"
            ? "text-[56px] leading-[0.84]"
            : "break-words text-[30px] leading-[0.92]",
          valueTone[tone]
        )}
      >
        {value}
      </p>

      {hint ? (
        <p
          className={clsx(
            "mt-2 max-w-[28ch] text-[12.5px] font-light leading-[1.55]",
            accent ? "text-paper/74" : "text-ink-3"
          )}
        >
          {hint}
        </p>
      ) : null}
    </Panel>
  );
}
