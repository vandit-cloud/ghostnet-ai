"use client";

import { BarListChart, TrendSparkline } from "@/components/Chart";
import { AppShell } from "@/components/AppShell";
import { KpiCard } from "@/components/KpiCard";
import { Panel } from "@/components/Panel";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/States";
import { useAnalyticsSummary } from "@/features/analytics/hooks";
import { formatConfidence } from "@/utils/format";

function formatDetectionClass(value: string) {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export default function AnalyticsPage() {
  const { data, isLoading, isError, refetch } = useAnalyticsSummary();

  if (isLoading) {
    return (
      <AppShell title="Analytics">
        <Panel className="p-6">
          <LoadingSkeleton rows={6} label="Loading platform analytics..." />
        </Panel>
      </AppShell>
    );
  }

  if (isError) {
    return (
      <AppShell title="Analytics">
        <ErrorState message="Unable to load analytics." onRetry={() => refetch()} />
      </AppShell>
    );
  }

  if (!data || data.total_detections === 0) {
    return (
      <AppShell title="Analytics">
        <EmptyState
          title="No analytics yet."
          description="Process at least one survey to populate platform-wide trends."
        />
      </AppShell>
    );
  }

  const funnel = data.review_funnel;
  const funnelTotal = funnel.pending + funnel.unknown + funnel.accepted_artificial + funnel.rejected_natural;

  return (
    <AppShell title="Analytics">
      <div className="space-y-6">
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <KpiCard label="Surveys" value={data.total_surveys} hint="Every survey ever created on this platform." />
          <KpiCard label="Detections" value={data.total_detections} hint="Across every survey, not just the current one." />
          <KpiCard label="Reports Generated" value={data.total_reports} hint="Total CSV/JSON exports produced to date." />
          <KpiCard
            label="Avg. Confidence"
            value={data.average_calibrated_confidence !== null ? formatConfidence(data.average_calibrated_confidence) : "—"}
            hint="Mean calibrated confidence across all detections."
          />
        </section>

        <section className="grid gap-6 xl:grid-cols-2">
          <Panel className="p-5">
            <p className="text-[11px] uppercase tracking-[0.28em] text-cyan-accent/80">Signal Mix</p>
            <h3 className="mt-2 text-lg font-semibold text-slate-100">Class Distribution (all surveys)</h3>
            <div className="mt-4">
              <BarListChart
                data={data.class_distribution.map((c) => ({ label: formatDetectionClass(c.detection_class), value: c.count }))}
                labelKey="label"
                valueKey="value"
              />
            </div>
          </Panel>

          <Panel className="p-5">
            <p className="text-[11px] uppercase tracking-[0.28em] text-cyan-accent/80">Triage</p>
            <h3 className="mt-2 text-lg font-semibold text-slate-100">Priority Distribution</h3>
            <div className="mt-4">
              <BarListChart
                data={data.priority_distribution.map((p) => ({ label: p.priority, value: p.count }))}
                labelKey="label"
                valueKey="value"
              />
            </div>
          </Panel>
        </section>

        <section className="grid gap-6 xl:grid-cols-2">
          <Panel className="p-5">
            <p className="text-[11px] uppercase tracking-[0.28em] text-cyan-accent/80">Decision Pulse</p>
            <h3 className="mt-2 text-lg font-semibold text-slate-100">Detection Trend (14 days)</h3>
            <div className="mt-4 rounded-2xl border border-abyss-600/70 bg-skytint/42 px-3 py-4">
              <TrendSparkline data={data.detection_trend} />
            </div>
          </Panel>

          <Panel className="p-5">
            <p className="text-[11px] uppercase tracking-[0.28em] text-cyan-accent/80">Human-in-the-Loop</p>
            <h3 className="mt-2 text-lg font-semibold text-slate-100">Review Funnel</h3>
            <div className="mt-4 grid grid-cols-2 gap-3">
              <div className="rounded-2xl border border-abyss-600/70 bg-skytint/42 p-4">
                <p className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Pending</p>
                <p className="mt-2 font-mono text-2xl text-slate-100">{funnel.pending}</p>
              </div>
              <div className="rounded-2xl border border-abyss-600/70 bg-skytint/42 p-4">
                <p className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Unknown</p>
                <p className="mt-2 font-mono text-2xl text-slate-100">{funnel.unknown}</p>
              </div>
              <div className="rounded-2xl border border-abyss-600/70 bg-skytint/42 p-4">
                <p className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Accepted — Artificial</p>
                <p className="mt-2 font-mono text-2xl text-emerald-300">{funnel.accepted_artificial}</p>
              </div>
              <div className="rounded-2xl border border-abyss-600/70 bg-skytint/42 p-4">
                <p className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Rejected — Natural</p>
                <p className="mt-2 font-mono text-2xl text-slate-300">{funnel.rejected_natural}</p>
              </div>
            </div>
            {funnelTotal === 0 ? <p className="mt-3 text-sm text-slate-500">No reviewed detections yet.</p> : null}
          </Panel>
        </section>
      </div>
    </AppShell>
  );
}
