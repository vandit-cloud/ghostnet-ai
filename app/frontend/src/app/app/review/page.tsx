"use client";

import Link from "next/link";
import { useState } from "react";
import clsx from "clsx";

import { AppShell } from "@/components/AppShell";
import { PriorityBadge, UncertaintyLabel } from "@/components/Badges";
import { MeterBar } from "@/components/MeterBar";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/States";
import { useDetections } from "@/features/detections/hooks";
import type { ReviewStatus } from "@/types";
import { formatConfidence, formatDateTime } from "@/utils/format";

const CATEGORIES: { value: ReviewStatus; label: string }[] = [
  { value: "pending", label: "Pending" },
  { value: "unknown", label: "Unknown" },
  { value: "accepted_artificial", label: "Accepted Artificial" },
  { value: "rejected_natural", label: "Rejected Natural" },
];

export default function ReviewQueuePage() {
  const [category, setCategory] = useState<ReviewStatus>("pending");
  const { data, isLoading, isError, refetch } = useDetections({ review_status: category, page_size: 100 });

  return (
    <AppShell title="Review">
      <div className="mb-4 flex gap-2 border-b border-abyss-600 pb-2">
        {CATEGORIES.map((cat) => (
          <button
            key={cat.value}
            onClick={() => setCategory(cat.value)}
            className={clsx(
              "rounded-t-md px-4 py-2 text-sm font-medium transition",
              category === cat.value ? "bg-cyan-accent/10 text-cyan-accent" : "text-slate-400 hover:text-slate-200"
            )}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <LoadingSkeleton rows={4} label="Loading review queue…" />
      ) : isError ? (
        <ErrorState message="Unable to load review queue." onRetry={() => refetch()} />
      ) : !data || data.items.length === 0 ? (
        <EmptyState title="No review items pending." description="Nothing in this category right now." />
      ) : (
        <div className="space-y-2">
          {data.items.map((d) => (
            <Link
              key={d.id}
              href={`/app/review/${d.id}`}
              className="flex items-center justify-between panel px-4 py-3 hover:border-cyan-accent/40"
            >
              <div>
                <p className="font-medium text-slate-100">{d.detection_ref}</p>
                <p className="text-xs capitalize text-slate-500">{d.detection_class.replace("_", " ")}</p>
              </div>
              <div className="flex items-center gap-4 text-sm">
                <MeterBar value={d.calibrated_confidence} label={formatConfidence(d.calibrated_confidence)} />
                <UncertaintyLabel level={d.uncertainty} />
                <PriorityBadge priority={d.priority} />
                <span className="text-xs text-slate-500">{formatDateTime(d.created_at)}</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </AppShell>
  );
}
