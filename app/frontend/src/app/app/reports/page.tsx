"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { Panel } from "@/components/Panel";
import { ReportCard } from "@/components/ReportCard";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/States";
import { useToastStore } from "@/components/Toast";
import { useCreateReport, useReports } from "@/features/reports/hooks";
import { useSurveys } from "@/features/surveys/hooks";
import type { ReportFormat, ReportType } from "@/types";

export default function ReportsPage() {
  return (
    <Suspense fallback={<AppShell title="Reports"><Panel className="p-6"><LoadingSkeleton rows={4} label="Loading reports..." /></Panel></AppShell>}>
      <ReportsPageContent />
    </Suspense>
  );
}

function ReportsPageContent() {
  const searchParams = useSearchParams();
  const initialSurveyId = searchParams.get("survey_id") ?? undefined;
  const detectionId = searchParams.get("detection_id") ?? undefined;

  const { data: surveys } = useSurveys(1, 100);
  const [surveyId, setSurveyId] = useState(initialSurveyId ?? "");
  const selectedSurvey = surveys?.items.find((s) => s.id === surveyId) ?? null;
  const [type, setType] = useState<ReportType>(detectionId ? "selected_detection" : "full_survey");
  const [format, setFormat] = useState<ReportFormat>("csv");

  const { data: reports, isLoading, isError, refetch } = useReports(surveyId || undefined);
  const createReport = useCreateReport();
  const push = useToastStore((s) => s.push);

  async function handleGenerate() {
    if (!surveyId) {
      push("Select a survey first.", "error");
      return;
    }
    try {
      await createReport.mutateAsync({
        survey_id: surveyId,
        type,
        format,
        detection_id: type === "selected_detection" ? detectionId : undefined,
      });
      push("Report generation started.", "success");
    } catch {
      push("Unable to generate report.", "error");
    }
  }

  return (
    <AppShell title="Reports">
      <div className="space-y-6">
        <section className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.95fr)]">
          <Panel className="p-6 sm:p-7">
            <p className="text-[11px] uppercase tracking-[0.32em] text-cyan-accent/85">Evidence Export</p>
            <h2 className="mt-3 font-display text-3xl font-semibold tracking-wide text-slate-50 sm:text-4xl">
              Build shareable report artifacts for surveys, filtered queues, and single detections.
            </h2>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-300">
              Turn live operational data into CSV or JSON deliverables for review teams, compliance workflows, and downstream analysis.
            </p>
          </Panel>

          <Panel className="p-6">
            <p className="text-[11px] uppercase tracking-[0.32em] text-cyan-accent/80">Output Snapshot</p>
            <div className="mt-4 grid grid-cols-2 gap-3">
              <div className="rounded-2xl border border-abyss-600/70 bg-skytint/42 p-4">
                <p className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Reports</p>
                <p className="mt-2 font-mono text-3xl text-slate-100">{reports?.length ?? 0}</p>
              </div>
              <div className="rounded-2xl border border-abyss-600/70 bg-skytint/42 p-4">
                <p className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Active survey</p>
                <p className="mt-2 truncate text-sm text-slate-200" title={selectedSurvey?.name}>
                  {selectedSurvey ? selectedSurvey.name : "Not set"}
                </p>
              </div>
              <div className="rounded-2xl border border-abyss-600/70 bg-skytint/42 p-4">
                <p className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Format</p>
                <p className="mt-2 font-mono text-2xl text-cyan-accent">{format.toUpperCase()}</p>
              </div>
              <div className="rounded-2xl border border-abyss-600/70 bg-skytint/42 p-4">
                <p className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Scope</p>
                <p className="mt-2 text-sm capitalize text-slate-200">{type.replace("_", " ")}</p>
              </div>
            </div>
          </Panel>
        </section>

        <Panel className="p-5">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
            <div>
              <label className="mb-2 block text-[11px] uppercase tracking-[0.26em] text-slate-500">Survey</label>
              <select
                value={surveyId}
                onChange={(e) => setSurveyId(e.target.value)}
                className="w-full rounded-2xl border border-abyss-600/80 bg-skytint/42 px-3 py-2.5 text-sm text-slate-200 outline-none focus:border-cyan-accent focus:shadow-glow-cyan"
              >
                <option value="">Select survey</option>
                {surveys?.items.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-2 block text-[11px] uppercase tracking-[0.26em] text-slate-500">Report Type</label>
              <select
                value={type}
                onChange={(e) => setType(e.target.value as ReportType)}
                className="w-full rounded-2xl border border-abyss-600/80 bg-skytint/42 px-3 py-2.5 text-sm text-slate-200 outline-none focus:border-cyan-accent focus:shadow-glow-cyan"
              >
                <option value="selected_detection" disabled={!detectionId}>
                  Selected Detection
                </option>
                <option value="filtered_detections">Filtered Detections</option>
                <option value="full_survey">Full Survey</option>
              </select>
            </div>
            <div>
              <label className="mb-2 block text-[11px] uppercase tracking-[0.26em] text-slate-500">Format</label>
              <select
                value={format}
                onChange={(e) => setFormat(e.target.value as ReportFormat)}
                className="w-full rounded-2xl border border-abyss-600/80 bg-skytint/42 px-3 py-2.5 text-sm text-slate-200 outline-none focus:border-cyan-accent focus:shadow-glow-cyan"
              >
                <option value="csv">CSV</option>
                <option value="json">JSON</option>
              </select>
            </div>
            <div className="flex items-end">
              <button
                onClick={handleGenerate}
                disabled={createReport.isPending}
                className="w-full border border-imperial bg-imperial px-4 py-2.5 text-sm font-medium uppercase tracking-[0.2em] text-paper transition hover:bg-imperial-deep disabled:opacity-50"
              >
                {createReport.isPending ? "Starting..." : "Generate Report"}
              </button>
            </div>
          </div>
        </Panel>

        {isLoading ? (
          <Panel className="p-6">
            <LoadingSkeleton rows={4} label="Loading reports..." />
          </Panel>
        ) : isError ? (
          <ErrorState message="Unable to load reports." onRetry={() => refetch()} />
        ) : !reports || reports.length === 0 ? (
          <EmptyState title="No reports generated yet." description="Generate a report using the form above." />
        ) : (
          <div className="space-y-3">
            {reports.map((r) => (
              <ReportCard key={r.id} report={r} />
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
