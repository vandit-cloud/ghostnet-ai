"use client";

import { useState } from "react";
import { ALERT } from "@/utils/palette";

const PRIORITY_ITEMS: { label: string; color: string }[] = [
  { label: "Critical", color: ALERT.critical },
  { label: "High", color: ALERT.high },
  { label: "Medium", color: ALERT.medium },
  { label: "Low", color: ALERT.low },
];

const CLASS_ITEMS: { label: string; code: string }[] = [
  { label: "Ghost Net", code: "G" },
  { label: "Debris", code: "D" },
  { label: "Natural Object", code: "O" },
  { label: "Unknown", code: "?" },
];

/** Collapsed by default so it never competes with the map for attention -
 * a permanently-open legend box was flagged as visual clutter. */
export function MapLegend() {
  const [open, setOpen] = useState(false);

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="rounded-lg border border-abyss-600 bg-abyss-900/90 px-3 py-2 text-xs font-medium text-slate-300 backdrop-blur hover:border-cyan-accent/40 hover:text-cyan-accent"
      >
        Legend
      </button>
    );
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-abyss-600 bg-abyss-900/90 p-3 text-xs text-slate-300 backdrop-blur">
      <div className="flex items-center justify-between">
        <p className="font-semibold uppercase tracking-wide text-slate-500">Legend</p>
        <button
          type="button"
          onClick={() => setOpen(false)}
          aria-label="Collapse legend"
          className="text-slate-500 hover:text-cyan-accent"
        >
          ✕
        </button>
      </div>
      <div>
        <p className="mb-1.5 font-semibold uppercase tracking-wide text-slate-500">Priority</p>
        <div className="flex flex-col gap-1">
          {PRIORITY_ITEMS.map((item) => (
            <div key={item.label} className="flex items-center gap-2">
              <span className="h-3 w-3 rounded-full border border-abyss-950" style={{ backgroundColor: item.color }} />
              {item.label}
            </div>
          ))}
        </div>
      </div>
      <div>
        <p className="mb-1.5 font-semibold uppercase tracking-wide text-slate-500">Class</p>
        <div className="flex flex-col gap-1">
          {CLASS_ITEMS.map((item) => (
            <div key={item.label} className="flex items-center gap-2">
              <span className="flex h-3.5 w-3.5 items-center justify-center rounded-full bg-slate-500/40 text-[9px] font-bold text-slate-100">
                {item.code}
              </span>
              {item.label}
            </div>
          ))}
        </div>
      </div>
      <div className="flex items-center gap-2 border-t border-abyss-700 pt-2">
        <span className="h-0.5 w-4 border-t-2 border-dashed border-imperial" />
        Survey track
      </div>
      <div className="flex items-center gap-2">
        <span className="h-3 w-3 rounded-full border border-cyan-accent/50 bg-cyan-accent/10" />
        Position uncertainty
      </div>
      <div className="flex items-center gap-2">
        <span className="h-2 w-4 rounded-sm bg-imperial/20" />
        Sonar coverage
      </div>
    </div>
  );
}
