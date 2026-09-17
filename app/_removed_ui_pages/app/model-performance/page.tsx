"use client";

import { useMemo } from "react";

import { AppShell } from "@/components/AppShell";
import { KpiCard } from "@/components/KpiCard";
import { EmptyState, LoadingSkeleton } from "@/components/States";
import { useDashboardSummary } from "@/features/dashboard/hooks";
import { useRecentJobs } from "@/features/system/hooks";
import { useSystemStatus } from "@/features/system/hooks";

export default function ModelPerformancePage() {
  const { data: summary, isLoading: summaryLoading } = useDashboardSummary();
  const { data: jobs, isLoading: jobsLoading } = useRecentJobs({ limit: 100 });
  const { data: status } = useSystemStatus();

  const perf = useMemo(() => {
    const completed = (jobs ?? []).filter((j) => j.status === "COMPLETED" && j.started_at && j.completed_at);
    if (completed.length === 0) return null;
    const latencies = completed.map(
      (j) => (new Date(j.completed_at!).getTime() - new Date(j.started_at!).getTime()) / 1000
    );
    const totalFrames = completed.reduce((a, j) => a + j.frames_processed, 0);
    const totalSeconds = latencies.reduce((a, b) => a + b, 0);
    return {
      throughput: totalSeconds > 0 ? totalFrames / totalSeconds : 0,
      avgLatencyPerFrame: totalFrames > 0 ? totalSeconds / totalFrames : 0,
      framesEvaluated: totalFrames,
    };
  }, [jobs]);

  const reviewAgreement = useMemo(() => {
    if (!summary) return null;
    const reviewed = summary.confirmed_artificial + summary.rejected_natural;
    if (reviewed === 0) return null;
    return { rate: summary.confirmed_artificial / reviewed, reviewed };
  }, [summary]);

  const aiEngine = status?.components.find((c) => c.name === "AI Engine");

  return (
    <AppShell title="Model Performance">
      <div className="mb-6 panel p-4">
        <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-slate-400">Model In Use</h2>
        <p className="text-sm text-slate-300">{aiEngine?.detail ?? "Loading…"}</p>
      </div>

      <section className="mb-8">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
          Classification Metrics (Precision / Recall / F1 / mAP)
        </h2>
        <EmptyState
          title="Not yet available."
          description="These metrics require an evaluation run against a labeled validation dataset. They will appear here once Member 1's model is integrated and evaluated — this build never fabricates accuracy figures."
        />
      </section>

      <section className="mb-8">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
          Measured Processing Performance
        </h2>
        {jobsLoading ? (
          <LoadingSkeleton rows={2} />
        ) : !perf ? (
          <p className="text-sm text-slate-500">No completed processing jobs yet — run a survey to measure throughput and latency.</p>
        ) : (
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
            <KpiCard label="Throughput" value={`${perf.throughput.toFixed(1)} fr/s`} />
            <KpiCard label="Avg. Latency / Frame" value={`${(perf.avgLatencyPerFrame * 1000).toFixed(0)} ms`} />
            <KpiCard label="Frames Evaluated" value={perf.framesEvaluated} />
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
          Reviewer Agreement Rate
        </h2>
        <p className="mb-3 max-w-2xl text-xs text-slate-500">
          Share of reviewed candidates a human confirmed as artificial. This is an operational signal from actual
          review decisions, not a formal precision/recall metric.
        </p>
        {summaryLoading ? (
          <LoadingSkeleton rows={1} />
        ) : !reviewAgreement ? (
          <p className="text-sm text-slate-500">No reviewed detections yet.</p>
        ) : (
          <KpiCard
            label={`Confirmed Artificial (of ${reviewAgreement.reviewed} reviewed)`}
            value={`${Math.round(reviewAgreement.rate * 100)}%`}
          />
        )}
      </section>
    </AppShell>
  );
}
