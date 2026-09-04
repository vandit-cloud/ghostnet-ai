"use client";

import { useState } from "react";

import type { ReviewStatus } from "@/types";

const DECISIONS: { value: ReviewStatus; label: string; tone: string }[] = [
  { value: "accepted_artificial", label: "Accept Artificial", tone: "border-emerald-500/50 text-emerald-300 hover:bg-emerald-500/10" },
  { value: "rejected_natural", label: "Reject Natural", tone: "border-slate-500/50 text-slate-300 hover:bg-slate-500/10" },
  { value: "unknown", label: "Mark Unknown", tone: "border-alert-medium/50 text-alert-medium hover:bg-alert-medium/10" },
];

export function ReviewPanel({
  onSubmit,
  isSubmitting,
}: {
  onSubmit: (decision: ReviewStatus, note: string) => void;
  isSubmitting: boolean;
}) {
  const [note, setNote] = useState("");
  const [selected, setSelected] = useState<ReviewStatus | null>(null);

  return (
    <div className="space-y-4 panel p-4">
      <h3 className="text-sm font-semibold text-slate-200">Review Decision</h3>
      <div className="flex flex-wrap gap-2">
        {DECISIONS.map((d) => (
          <button
            key={d.value}
            onClick={() => setSelected(d.value)}
            className={`rounded-md border px-3 py-1.5 text-sm transition ${d.tone} ${
              selected === d.value ? "ring-1 ring-cyan-accent" : ""
            }`}
          >
            {d.label}
          </button>
        ))}
      </div>

      <div>
        <label htmlFor="note" className="mb-1 block text-xs text-slate-500">
          Note
        </label>
        <textarea
          id="note"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={3}
          className="w-full rounded-md border border-abyss-600 bg-abyss-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-accent focus:shadow-glow-cyan"
          placeholder="Add context for this decision (optional)"
        />
      </div>

      <button
        disabled={!selected || isSubmitting}
        onClick={() => selected && onSubmit(selected, note)}
        className="w-full rounded-md bg-cyan-accent py-2 text-sm font-medium text-abyss-950 hover:bg-cyan-accent/90 disabled:opacity-50"
      >
        {isSubmitting ? "Saving…" : "Save Review"}
      </button>
    </div>
  );
}
