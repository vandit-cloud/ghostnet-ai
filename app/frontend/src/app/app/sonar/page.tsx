"use client";

import Link from "next/link";

import { AppShell } from "@/components/AppShell";
import { PriorityBadge } from "@/components/Badges";
import { EmptyState, LoadingSkeleton } from "@/components/States";
import { useDetections } from "@/features/detections/hooks";
import { formatConfidence } from "@/utils/format";

const PRIORITY_RANK: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };

export default function SonarIndexPage() {
  const { data, isLoading } = useDetections({ review_status: "pending", page_size: 8 });
  const pending = [...(data?.items ?? [])].sort(
    (a, b) => (PRIORITY_RANK[a.priority] ?? 9) - (PRIORITY_RANK[b.priority] ?? 9)
  );

  return (
    <AppShell title="Sonar Investigation">
      <div className="space-y-6">
        <EmptyState
          title="Select a detection to investigate."
          description="Open a detection from the detection list or dashboard to view its sonar evidence workspace."
          action={
            <Link href="/app/detections" className="mt-2 text-sm text-cyan-accent hover:underline">
              Go to Detections
            </Link>
          }
        />

        <section className="panel p-4">
          <h3 className="mb-3 text-sm font-semibold text-slate-200">Highest-priority pending review</h3>
          {isLoading ? (
            <LoadingSkeleton rows={3} />
          ) : pending.length === 0 ? (
            <p className="text-sm text-slate-500">Nothing pending review right now.</p>
          ) : (
            <ul className="space-y-2">
              {pending.slice(0, 5).map((d) => (
                <li key={d.id}>
                  <Link
                    href={`/app/sonar/${d.id}`}
                    className="flex items-center justify-between gap-3 rounded-md border border-abyss-700 px-3 py-2 text-sm transition hover:border-cyan-accent/40"
                  >
                    <span className="text-slate-200">{d.detection_ref}</span>
                    <span className="flex items-center gap-3 text-xs text-slate-500">
                      {formatConfidence(d.calibrated_confidence)}
                      <PriorityBadge priority={d.priority} />
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </AppShell>
  );
}
