"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { SurveyStatusBadge } from "@/components/Badges";
import { Panel } from "@/components/Panel";
import { RouteSparkline } from "@/components/RouteSparkline";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/States";
import { useSurveys } from "@/features/surveys/hooks";
import { formatDateTime } from "@/utils/format";

function SonarTypeIcon({ sonarType }: { sonarType: string | null | undefined }) {
  const t = (sonarType ?? "").toLowerCase();
  if (t.includes("side")) {
    return (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="inline-block text-slate-500" aria-hidden>
        <path d="M12 3v18M4 8l8-5 8 5M4 16l8 5 8-5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  if (t.includes("multi")) {
    return (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="inline-block text-slate-500" aria-hidden>
        <path d="M4 20c2-6 4-9 8-9s6 3 8 9" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        <path d="M6 20c1.5-4 3-6 6-6s4.5 2 6 6" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" opacity="0.6" />
      </svg>
    );
  }
  if (!t) return null;
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="inline-block text-slate-500" aria-hidden>
      <circle cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="1.6" />
      <circle cx="12" cy="12" r="2.4" fill="currentColor" />
    </svg>
  );
}

export default function SurveysPage() {
  const [page, setPage] = useState(1);
  const { data, isLoading, isError, refetch } = useSurveys(page, 20);

  const stats = useMemo(() => {
    const items = data?.items ?? [];
    return {
      totalSurveys: data?.total ?? items.length,
      activeSurveys: items.filter((survey) => survey.status === "PROCESSING" || survey.status === "VALIDATING").length,
      completedSurveys: items.filter((survey) => survey.status === "COMPLETED").length,
      totalDetections: items.reduce((sum, survey) => sum + survey.detection_count, 0),
    };
  }, [data]);

  return (
    <AppShell title="Surveys">
      <div className="space-y-6">
        <section className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.95fr)]">
          <Panel className="p-6 sm:p-7">
            <p className="text-[11px] uppercase tracking-[0.32em] text-cyan-accent/85">Field Operations</p>
            <h2 className="mt-3 font-display text-3xl font-semibold tracking-wide text-slate-50 sm:text-4xl">
              Survey missions, sonar intake, and route intelligence in one place.
            </h2>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-300">
              Use this workspace to stage new missions, track processing progress, and move from raw uploads into mapped detections and analyst review.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link
                href="/app/surveys/new"
                className="border border-imperial bg-imperial px-4 py-2 text-xs font-medium uppercase tracking-[0.24em] text-paper transition hover:bg-imperial-deep"
              >
                New Survey
              </Link>
              <Link
                href="/app/map"
                className="border border-abyss-600/80 px-4 py-2 text-xs font-medium uppercase tracking-[0.24em] text-slate-200 transition hover:border-cyan-accent/35 hover:text-cyan-accent"
              >
                Open GIS Map
              </Link>
            </div>
          </Panel>

          <Panel className="p-6">
            <p className="text-[11px] uppercase tracking-[0.32em] text-cyan-accent/80">Mission Snapshot</p>
            <div className="mt-4 grid grid-cols-2 gap-3">
              <div className="rounded-2xl border border-abyss-600/70 bg-skytint/42 p-4">
                <p className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Total surveys</p>
                <p className="mt-2 font-mono text-3xl text-slate-100">{stats.totalSurveys}</p>
              </div>
              <div className="rounded-2xl border border-abyss-600/70 bg-skytint/42 p-4">
                <p className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Active</p>
                <p className="mt-2 font-mono text-3xl text-cyan-accent">{stats.activeSurveys}</p>
              </div>
              <div className="rounded-2xl border border-abyss-600/70 bg-skytint/42 p-4">
                <p className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Completed</p>
                <p className="mt-2 font-mono text-3xl text-emerald-300">{stats.completedSurveys}</p>
              </div>
              <div className="rounded-2xl border border-abyss-600/70 bg-skytint/42 p-4">
                <p className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Detections</p>
                <p className="mt-2 font-mono text-3xl text-slate-100">{stats.totalDetections}</p>
              </div>
            </div>
          </Panel>
        </section>

        {isLoading ? (
          <Panel className="p-6">
            <LoadingSkeleton rows={6} label="Loading surveys..." />
          </Panel>
        ) : isError ? (
          <ErrorState message="Unable to load surveys." onRetry={() => refetch()} />
        ) : data && data.items.length === 0 ? (
          <EmptyState title="No surveys found." description="Create a survey to begin uploading sonar data." />
        ) : (
          <Panel className="overflow-hidden !p-0">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-abyss-600/70 px-5 py-4">
              <div>
                <p className="text-[11px] uppercase tracking-[0.28em] text-cyan-accent/80">Mission Registry</p>
                <h3 className="mt-2 text-lg font-semibold text-slate-100">Survey inventory</h3>
              </div>
              <p className="text-sm text-slate-400">Page {page} of {Math.max(1, Math.ceil((data?.total ?? 0) / Math.max(data?.page_size ?? 1, 1)))}</p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-[11px] uppercase tracking-[0.24em] text-slate-500">
                  <tr>
                    <th className="px-5 py-4">Name</th>
                    <th className="px-5 py-4">Source</th>
                    <th className="px-5 py-4">Sonar Type</th>
                    <th className="px-5 py-4">Route</th>
                    <th className="px-5 py-4">Files</th>
                    <th className="px-5 py-4">Detections</th>
                    <th className="px-5 py-4">Status</th>
                    <th className="px-5 py-4">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {data?.items.map((survey) => (
                    <tr key={survey.id} className="border-t border-abyss-700/80 text-slate-300 transition hover:bg-skytint/42">
                      <td className="px-5 py-4">
                        <Link href={`/app/surveys/${survey.id}`} className="font-medium text-cyan-accent hover:underline">
                          {survey.name}
                        </Link>
                      </td>
                      <td className="px-5 py-4 text-slate-400">{survey.source ?? "-"}</td>
                      <td className="px-5 py-4 text-slate-400">
                        <span className="inline-flex items-center gap-1.5">
                          <SonarTypeIcon sonarType={survey.sonar_type} />
                          {survey.sonar_type ?? "-"}
                        </span>
                      </td>
                      <td className="px-5 py-4">
                        <RouteSparkline surveyId={survey.id} />
                      </td>
                      <td className="px-5 py-4 font-mono tabular-nums text-slate-200">{survey.file_count}</td>
                      <td className="px-5 py-4 font-mono tabular-nums text-slate-200">{survey.detection_count}</td>
                      <td className="px-5 py-4">
                        <SurveyStatusBadge status={survey.status} />
                      </td>
                      <td className="px-5 py-4 font-mono tabular-nums text-slate-500">{formatDateTime(survey.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        )}

        {data && data.total > data.page_size ? (
          <div className="flex items-center justify-center gap-3 text-sm text-slate-400">
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="border border-abyss-600/80 px-4 py-2 transition hover:border-cyan-accent/35 hover:text-cyan-accent disabled:opacity-40"
            >
              Previous
            </button>
            <span>Page {page}</span>
            <button
              disabled={page * data.page_size >= data.total}
              onClick={() => setPage((p) => p + 1)}
              className="border border-abyss-600/80 px-4 py-2 transition hover:border-cyan-accent/35 hover:text-cyan-accent disabled:opacity-40"
            >
              Next
            </button>
          </div>
        ) : null}
      </div>
    </AppShell>
  );
}
