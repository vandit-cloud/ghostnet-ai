"use client";

import Link from "next/link";

import { AppShell } from "@/components/AppShell";
import { BarListChart, TrendSparkline } from "@/components/Chart";
import { JobStatusBadge, PriorityBadge, SurveyStatusBadge } from "@/components/Badges";
import { KpiCard } from "@/components/KpiCard";
import { Panel } from "@/components/Panel";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/States";
import { useDashboardSummary } from "@/features/dashboard/hooks";
import { SurveyHero } from "@/features/dashboard/SurveyHero";
import { formatConfidence, formatDateTime } from "@/utils/format";

function formatDetectionClass(value: string) {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export default function DashboardPage() {
  const { data, isLoading, isError, refetch } = useDashboardSummary();

  if (isLoading) {
    return (
      <AppShell title="Dashboard">
        <div className="space-y-6">
          <Panel className="p-6">
            <LoadingSkeleton rows={2} label="Loading mission dashboard..." />
          </Panel>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
            {Array.from({ length: 5 }).map((_, index) => (
              <Panel key={index} className="min-h-[148px] p-5">
                <LoadingSkeleton rows={2} />
              </Panel>
            ))}
          </div>
          <Panel className="p-6">
            <LoadingSkeleton rows={3} />
          </Panel>
        </div>
      </AppShell>
    );
  }

  if (isError) {
    return (
      <AppShell title="Dashboard">
        <Panel className="p-6">
          <ErrorState message="Unable to load dashboard." onRetry={() => refetch()} />
        </Panel>
      </AppShell>
    );
  }

  if (!data) {
    return (
      <AppShell title="Dashboard">
        <Panel className="p-6">
          <EmptyState title="Dashboard data is unavailable." description="Reconnect to the backend and refresh to restore mission telemetry." />
        </Panel>
      </AppShell>
    );
  }

  const topClass = [...data.class_distribution].sort((left, right) => right.count - left.count)[0] ?? null;
  const reviewRatio = data.candidates ? Math.round((data.needs_review / data.candidates) * 100) : 0;
  const confirmationRatio = data.candidates ? Math.round((data.confirmed_artificial / data.candidates) * 100) : 0;
  const recentDetection = data.recent_detections[0] ?? null;

  return (
    <AppShell title="Dashboard">
      <div className="space-y-6">
        <section className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(340px,0.95fr)]">
          <Panel className="p-6 sm:p-7">
            {data.current_survey ? (
              <>
                <div className="flex flex-wrap items-start justify-between gap-5">
                  <div className="max-w-3xl">
                    <p className="text-[11px] uppercase tracking-[0.32em] text-cyan-accent/85">Active Mission</p>
                    <h2 className="mt-3 font-display text-3xl font-semibold tracking-wide text-slate-50 sm:text-4xl">
                      <Link href={`/app/surveys/${data.current_survey.id}`} className="hover:text-cyan-accent">
                        {data.current_survey.name}
                      </Link>
                    </h2>
                    <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300">
                      GhostNet turns sonar ingestion, live geospatial tracking, and analyst review into one coordinated command surface for maritime anomaly detection.
                    </p>
                    <div className="mt-5 flex flex-wrap items-center gap-2">
                      <SurveyStatusBadge status={data.current_survey.status} />
                      {data.active_job ? <JobStatusBadge status={data.active_job.status} /> : null}
                      {data.active_job ? (
                        <span className="border border-cyan-accent/30 bg-cyan-accent/10 px-3 py-1 text-[11px] uppercase tracking-[0.24em] text-cyan-accent">
                          {data.active_job.stage}
                        </span>
                      ) : null}
                    </div>
                  </div>

                  <div className="grid min-w-[260px] grid-cols-2 gap-3">
                    <div className="rounded-2xl border border-abyss-600/70 bg-skytint/42 px-3 py-3">
                      <p className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Last Sync</p>
                      <p className="mt-2 text-sm text-slate-200">{formatDateTime(data.last_updated)}</p>
                    </div>
                    <div className="rounded-2xl border border-abyss-600/70 bg-skytint/42 px-3 py-3">
                      <p className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Review Load</p>
                      <p className="mt-2 text-sm text-slate-200">{reviewRatio}% queued</p>
                    </div>
                    <div className="rounded-2xl border border-abyss-600/70 bg-skytint/42 px-3 py-3">
                      <p className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Lead Signal</p>
                      <p className="mt-2 text-sm text-slate-200">{topClass ? formatDetectionClass(topClass.detection_class) : "Awaiting detections"}</p>
                    </div>
                    <div className="rounded-2xl border border-abyss-600/70 bg-skytint/42 px-3 py-3">
                      <p className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Confirm Rate</p>
                      <p className="mt-2 text-sm text-slate-200">{confirmationRatio}% analyst-verified</p>
                    </div>
                  </div>
                </div>

                <div className="mt-6 flex flex-wrap gap-3">
                  <Link
                    href="/app/map"
                    className="border border-imperial bg-imperial px-4 py-2 text-xs font-medium uppercase tracking-[0.24em] text-paper transition hover:bg-imperial-deep"
                  >
                    Open GIS Map
                  </Link>
                  <Link
                    href="/app/review"
                    className="border border-abyss-600/80 px-4 py-2 text-xs font-medium uppercase tracking-[0.24em] text-slate-200 transition hover:border-cyan-accent/35 hover:text-cyan-accent"
                  >
                    Review Queue
                  </Link>
                  <Link
                    href="/app/reports"
                    className="border border-abyss-600/80 px-4 py-2 text-xs font-medium uppercase tracking-[0.24em] text-slate-200 transition hover:border-cyan-accent/35 hover:text-cyan-accent"
                  >
                    Generate Reports
                  </Link>
                </div>
              </>
            ) : (
              <EmptyState title="No surveys yet." description="Create a survey to activate the mission dashboard and 3D monitoring view." />
            )}
          </Panel>

          <Panel className="p-6">
            <p className="text-[11px] uppercase tracking-[0.32em] text-cyan-accent/80">Mission Posture</p>
            <div className="mt-4 space-y-4">
              <div className="rounded-2xl border border-cyan-accent/15 bg-cyan-accent/5 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-slate-100">
                      {data.active_job ? "Pipeline is active" : "Pipeline is standing by"}
                    </p>
                    <p className="mt-1 text-sm text-slate-400">
                      {data.active_job
                        ? `${data.active_job.progress}% complete through ${data.active_job.stage.toLowerCase()}.`
                        : "Waiting for the next survey upload to enter the processing chain."}
                    </p>
                  </div>
                  {data.active_job ? <JobStatusBadge status={data.active_job.status} /> : null}
                </div>
                <div className="mt-4 h-2 bg-abyss-700/80">
                  <div
                    className="h-2 bg-imperial"
                    style={{ width: `${Math.max(data.active_job?.progress ?? 0, data.active_job ? 6 : 0)}%` }}
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-2xl border border-abyss-600/70 bg-skytint/42 p-4">
                  <p className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Confirmed</p>
                  <p className="mt-2 font-mono text-2xl text-emerald-300">{data.confirmed_artificial}</p>
                </div>
                <div className="rounded-2xl border border-abyss-600/70 bg-skytint/42 p-4">
                  <p className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Rejected</p>
                  <p className="mt-2 font-mono text-2xl text-slate-200">{data.rejected_natural}</p>
                </div>
              </div>

              <div className="rounded-2xl border border-abyss-600/70 bg-skytint/42 p-4">
                <p className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Operator Focus</p>
                <p className="mt-2 text-sm leading-6 text-slate-300">
                  Prioritize {data.high_priority} high-priority detections and clear the {data.needs_review} items waiting on analyst judgement.
                </p>
              </div>
            </div>
          </Panel>
        </section>

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          <KpiCard label="Frames Processed" value={data.frames_processed} hint="Total sonar frames ingested into the mission timeline." />
          <KpiCard label="Detections" value={data.candidates} hint="All candidate anomalies currently in the evidence graph." />
          <KpiCard label="High Priority" value={data.high_priority} tone="high" hint="Signals likely to need immediate operator review." />
          <KpiCard label="Pending Review" value={data.needs_review} tone="critical" hint="Items still waiting for human confirmation." />
          <KpiCard
            label="Processing Stage"
            value={data.active_job ? data.active_job.stage : "IDLE"}
            live={Boolean(data.active_job)}
            hint={data.active_job ? "Current pipeline checkpoint for the active survey." : "No active processing task is running right now."}
          />
        </section>

        <section className="grid gap-6 xl:grid-cols-[minmax(0,1.5fr)_minmax(340px,0.9fr)]">
          <div className="space-y-3">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="text-[11px] uppercase tracking-[0.32em] text-cyan-accent/80">Survey Theater</p>
                <h2 className="mt-2 font-display text-2xl font-semibold text-slate-100">3D Vessel Replay</h2>
              </div>
              <p className="max-w-xl text-sm text-slate-400">Follow the vessel path, inspect detections spatially, and switch between overview and close-up review modes.</p>
            </div>
            {data.current_survey ? (
              <SurveyHero
                surveyId={data.current_survey.id}
                surveyStatus={data.current_survey.status}
                activeJobStatus={data.active_job?.status ?? null}
              />
            ) : (
              <Panel className="flex h-[520px] items-center justify-center p-6">
                <EmptyState title="No active survey selected." description="Create or upload a survey to unlock the live 3D theater." />
              </Panel>
            )}
          </div>

          <div className="space-y-4">
            <Panel className="p-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.28em] text-cyan-accent/80">Signal Mix</p>
                  <h3 className="mt-2 text-lg font-semibold text-slate-100">Class Distribution</h3>
                </div>
                {topClass ? (
                  <span className="border border-abyss-600/80 px-3 py-1 text-xs text-slate-300">
                    Lead: {formatDetectionClass(topClass.detection_class)}
                  </span>
                ) : null}
              </div>
              <div className="mt-4">
                <BarListChart
                  data={data.class_distribution.map((c) => ({ label: formatDetectionClass(c.detection_class), value: c.count }))}
                  labelKey="label"
                  valueKey="value"
                />
              </div>
            </Panel>

            <Panel className="p-5">
              <p className="text-[11px] uppercase tracking-[0.28em] text-cyan-accent/80">Decision Pulse</p>
              <h3 className="mt-2 text-lg font-semibold text-slate-100">Detection Trend (14 days)</h3>
              <div className="mt-4 rounded-2xl border border-abyss-600/70 bg-skytint/42 px-3 py-4">
                <TrendSparkline data={data.detection_trend} />
              </div>
            </Panel>

            <Panel className="p-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.28em] text-cyan-accent/80">Latest Alert</p>
                  <h3 className="mt-2 text-lg font-semibold text-slate-100">Recent Detection</h3>
                </div>
                {recentDetection ? <PriorityBadge priority={recentDetection.priority} /> : null}
              </div>
              {recentDetection ? (
                <div className="mt-4 rounded-2xl border border-abyss-600/70 bg-skytint/42 p-4">
                  <Link href={`/app/detections/${recentDetection.id}`} className="text-lg font-semibold text-cyan-accent hover:underline">
                    {recentDetection.detection_ref}
                  </Link>
                  <p className="mt-2 text-sm text-slate-300">{formatDetectionClass(recentDetection.detection_class)}</p>
                  <p className="mt-1 text-sm text-slate-400">Confidence {formatConfidence(recentDetection.calibrated_confidence)}</p>
                  <p className="mt-3 text-xs uppercase tracking-[0.24em] text-slate-500">{formatDateTime(recentDetection.created_at)}</p>
                </div>
              ) : (
                <p className="mt-4 text-sm text-slate-500">No detections have been recorded yet.</p>
              )}
            </Panel>
          </div>
        </section>

        <Panel className="p-5 sm:p-6">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <p className="text-[11px] uppercase tracking-[0.32em] text-cyan-accent/80">Intel Feed</p>
              <h2 className="mt-2 text-xl font-semibold text-slate-100">Recent Detections</h2>
            </div>
            <Link
              href="/app/detections"
              className="border border-abyss-600/80 px-3 py-1.5 text-xs font-medium uppercase tracking-[0.22em] text-slate-300 transition hover:border-cyan-accent/35 hover:text-cyan-accent"
            >
              View All
            </Link>
          </div>
          {data.recent_detections.length === 0 ? (
            <EmptyState title="No detections found." description="Process a survey to populate the intelligence feed." />
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left text-[11px] uppercase tracking-[0.24em] text-slate-500">
                    <th className="pb-3 pr-4">Detection</th>
                    <th className="pb-3 pr-4">Class</th>
                    <th className="pb-3 pr-4">Confidence</th>
                    <th className="pb-3 pr-4">Priority</th>
                    <th className="pb-3">Time</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent_detections.map((d) => (
                    <tr key={d.id} className="border-t border-abyss-700/80 text-slate-300 transition hover:bg-skytint/42">
                      <td className="py-3 pr-4">
                        <Link href={`/app/detections/${d.id}`} className="font-medium text-cyan-accent hover:underline">
                          {d.detection_ref}
                        </Link>
                      </td>
                      <td className="py-3 pr-4">{formatDetectionClass(d.detection_class)}</td>
                      <td className="py-3 pr-4 font-mono">{formatConfidence(d.calibrated_confidence)}</td>
                      <td className="py-3 pr-4">
                        <PriorityBadge priority={d.priority} />
                      </td>
                      <td className="py-3 text-slate-500">{formatDateTime(d.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      </div>
    </AppShell>
  );
}
