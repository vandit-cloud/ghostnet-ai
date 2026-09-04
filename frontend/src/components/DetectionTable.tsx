"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { PriorityBadge, ReviewStatusBadge, UncertaintyLabel } from "@/components/Badges";
import { MeterBar } from "@/components/MeterBar";
import type { Detection } from "@/types";
import { formatConfidence, formatCoordinate, formatDateTime } from "@/utils/format";

const PRIORITY_RANK: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };

type SortKey = "confidence" | "priority" | "timestamp";

function sortValue(d: Detection, key: SortKey): number {
  if (key === "confidence") return d.calibrated_confidence ?? -1;
  if (key === "priority") return -(PRIORITY_RANK[d.priority] ?? 9);
  return new Date(d.created_at).getTime();
}

export function DetectionTable({ detections }: { detections: Detection[] }) {
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
              <td className="px-4 py-3 capitalize text-slate-300">{d.detection_class.replace("_", " ")}</td>
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
