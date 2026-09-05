"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { PriorityBadge, ReviewStatusBadge, UncertaintyLabel } from "@/components/Badges";
import { MeterBar } from "@/components/MeterBar";
import type { Detection } from "@/types";
import {
  formatConfidence,
  formatCoordinate,
  formatDateTime,
  formatDetectionClassWithDetector,
} from "@/utils/format";

const PRIORITY_RANK: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };

type SortKey = "confidence" | "priority" | "timestamp";

function sortValue(d: Detection, key: SortKey): number {
  if (key === "confidence") return d.calibrated_confidence ?? -1;
  if (key === "priority") return -(PRIORITY_RANK[d.priority] ?? 9);
  return new Date(d.created_at).getTime();
}

/** `showSurvey` defaults on: the table is reachable from the sidebar with no
 * scope, and rows from four surveys in one undifferentiated list is most of
 * why a freshly processed survey feels like it produced nothing (B2 in
 * docs/KNOWN_ISSUES.md). Pages that are already scoped to one survey pass
 * false rather than repeat the same name down every row. */
export function DetectionTable({
  detections,
  showSurvey = true,
}: {
  detections: Detection[];
  showSurvey?: boolean;
}) {
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 } | null>(null);

  const rows = useMemo(() => {
    if (!sort) return detections;
    const sorted = [...detections].sort((a, b) => (sortValue(a, sort.key) - sortValue(b, sort.key)) * sort.dir);
    return sorted;
  }, [detections, sort]);

  function toggleSort(key: SortKey) {
    setSort((curr) => {
      if (curr?.key !== key) return { key, dir: -1 };
      if (curr.dir === -1) return { key, dir: 1 };
      return null;
    });
  }

  function SortHeader({ sortKey, children }: { sortKey: SortKey; children: React.ReactNode }) {
    const active = sort?.key === sortKey;
    return (
      <th className="px-4 py-3">
        <button
          type="button"
          onClick={() => toggleSort(sortKey)}
          className="flex items-center gap-1 uppercase tracking-wide hover:text-cyan-accent"
        >
          {children}
          <span className="text-[10px]">{active ? (sort!.dir === -1 ? "▼" : "▲") : ""}</span>
        </button>
      </th>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-abyss-600">
      <table className="w-full text-sm">
        <thead className="bg-abyss-800/60 text-left text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-3">Detection ID</th>
            {showSurvey && <th className="px-4 py-3">Survey</th>}
            <th className="px-4 py-3">Class</th>
            <SortHeader sortKey="confidence">Confidence</SortHeader>
            <th className="px-4 py-3">Uncertainty</th>
            <SortHeader sortKey="priority">Priority</SortHeader>
            <th className="px-4 py-3">Location</th>
            <th className="px-4 py-3">Review Status</th>
            <SortHeader sortKey="timestamp">Timestamp</SortHeader>
          </tr>
        </thead>
        <tbody>
          {rows.map((d) => (
            <tr key={d.id} className="border-t border-abyss-700 hover:bg-abyss-800/40">
              <td className="px-4 py-3">
                <Link href={`/app/detections/${d.id}`} className="font-mono font-medium text-cyan-accent hover:underline">
                  {d.detection_ref}
                </Link>
              </td>
              {showSurvey && (
                <td className="px-4 py-3">
                  <Link
                    href={`/app/surveys/${d.survey_id}`}
                    className="text-slate-300 hover:text-cyan-accent hover:underline"
                  >
                    {d.survey_name ?? "—"}
                  </Link>
                </td>
              )}
              {/* Contract class plus the detector's finer call. The contract
                  stores four values and collapses wreck/plane/debris/crab pot
                  into `debris`, so this column alone read "Debris" for every
                  row on a survey of aircraft. */}
              <td className="px-4 py-3 text-slate-300">
                {formatDetectionClassWithDetector(d.detection_class, d.evidence_summary)}
              </td>
              <td className="px-4 py-3">
                <MeterBar value={d.calibrated_confidence} label={formatConfidence(d.calibrated_confidence)} />
              </td>
              <td className="px-4 py-3">
                <UncertaintyLabel level={d.uncertainty} />
              </td>
              <td className="px-4 py-3">
                <PriorityBadge priority={d.priority} />
              </td>
              <td className="px-4 py-3 font-mono tabular-nums text-slate-400">
                {d.latitude !== null && d.longitude !== null
                  ? `${formatCoordinate(d.latitude)}, ${formatCoordinate(d.longitude)}`
                  : "—"}
              </td>
              <td className="px-4 py-3">
                <ReviewStatusBadge status={d.review_status} />
              </td>
              <td className="px-4 py-3 font-mono tabular-nums text-slate-500">{formatDateTime(d.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
