"use client";

import { useMemo } from "react";

import { AppShell } from "@/components/AppShell";
import { BarListChart, TrendSparkline } from "@/components/Chart";
import { KpiCard } from "@/components/KpiCard";
import { ErrorState, LoadingSkeleton } from "@/components/States";
import { useDashboardSummary } from "@/features/dashboard/hooks";
import { useRecentJobs } from "@/features/system/hooks";
import { useSurveys } from "@/features/surveys/hooks";

const CLASS_LABELS: Record<string, string> = {
  ghost_net: "Ghost Net",
  debris: "Debris",
  natural_object: "Natural Object",
  unknown: "Unknown",
};

export default function AnalyticsPage() {
  const { data: summary, isLoading: summaryLoading, isError: summaryError, refetch } = useDashboardSummary();
  const { data: surveys, isLoading: surveysLoading } = useSurveys(1, 200);
  const { data: jobs, isLoading: jobsLoading } = useRecentJobs({ limit: 100 });

  const classData = useMemo(
    () =>
      (summary?.class_distribution ?? []).map((c) => ({
        detection_class: CLASS_LABELS[c.detection_class] ?? c.detection_class,
        count: c.count,
      })),
    [summary]
  );

  const priorityData = useMemo(
    () =>
      summary
        ? [
            { label: "Critical / High", count: summary.high_priority },
            { label: "Needs Review", count: summary.needs_review },
            { label: "Confirmed Artificial", count: summary.confirmed_artificial },
            { label: "Rejected Natural", count: summary.rejected_natural },
          ]
        : [],
    [summary]
  );

  const processingPerf = useMemo(() => {
    const completed = (jobs ?? []).filter((j) => j.status === "COMPLETED" && j.started_at && j.completed_at);
    if (completed.length === 0) return null;
    const latencies = completed.map(
      (j) => (new Date(j.completed_at!).getTime() - new Date(j.started_at!).getTime()) / 1000
    );
    const avgLatency = latencies.reduce((a, b) => a + b, 0) / latencies.length;
    const totalFrames = completed.reduce((a, j) => a + j.frames_processed, 0);
    const totalSeconds = latencies.reduce((a, b) => a + b, 0);
    const throughput = totalSeconds > 0 ? totalFrames / totalSeconds : 0;
    return { avgLatency, throughput, jobCount: completed.length };
  }, [jobs]);

  const inProgressSurveys = useMemo(
    () => (surveys?.items ?? []).filter((s) => s.status === "PROCESSING" || s.status === "PARTIAL"),
    [surveys]
  );

  if (summaryLoading) {
    return (
      <AppShell title="Analytics">
        <LoadingSkeleton rows={6} label="Loading analytics…" />
      </AppShell>
    );
  }

  if (summaryError || !summary) {
    return (
      <AppShell title="Analytics">
        <ErrorState message="Unable to load analytics data." onRetry={() => refetch()} />
      </AppShell>
    );
  }

  return (
    <AppShell title="Analytics">
      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <KpiCard label="Candidates" value={summary.candidates} />
        <KpiCard label="Confirmed Artificial" value={summary.confirmed_artificial} tone="positive" />
        <KpiCard label="High Priority" value={summary.high_priority} tone="high" />
        <KpiCard label="Needs Review" value={summary.needs_review} tone="critical" />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="panel p-4">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">Detections Over Time</h2>
          <TrendSparkline data={summary.detection_trend} />
        </div>

        <div className="panel p-4">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">Class Distribution</h2>
          <BarListChart data={classData} labelKey="detection_class" valueKey="count" />
        </div>

        <div className="panel p-4">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">Priority Breakdown</h2>
          <BarListChart data={priorityData} labelKey="label" valueKey="count" />
        </div>

        <div className="panel p-4">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">Processing Performance</h2>
          {jobsLoading ? (
            <LoadingSkeleton rows={2} />
          ) : !processingPerf ? (
            <p className="text-sm text-slate-500">No completed processing jobs yet.</p>
          ) : (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">Avg. Latency</p>
                <p className="mt-1 text-xl font-semibold tabular-nums text-slate-100">
                  {processingPerf.avgLatency.toFixed(1)}s
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">Throughput</p>
                <p className="mt-1 text-xl font-semibold tabular-nums text-slate-100">
                  {processingPerf.throughput.toFixed(1)} fr/s
                </p>
              </div>
              <p className="col-span-2 text-xs text-slate-500">
                Measured across {processingPerf.jobCount} completed job(s).
              </p>
            </div>
          )}
        </div>

        <div className="panel p-4 lg:col-span-2">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">Survey Progress</h2>
          {surveysLoading ? (
            <LoadingSkeleton rows={2} />
          ) : inProgressSurveys.length === 0 ? (
            <p className="text-sm text-slate-500">No surveys are currently processing.</p>
          ) : (
            <BarListChart
              data={inProgressSurveys.map((s) => ({
                name: s.name,
                pct: s.file_count > 0 ? Math.round((s.processed_count / s.file_count) * 100) : 0,
              }))}
              labelKey="name"
              valueKey="pct"
            />
          )}
        </div>
      </div>
    </AppShell>
  );
}
