"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useMemo } from "react";

import { AppShell } from "@/components/AppShell";
import { DetectionTable } from "@/components/DetectionTable";
import { FilterSelect } from "@/components/FilterBar";
import { Panel } from "@/components/Panel";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/States";
import { useDetections } from "@/features/detections/hooks";
import { useSurveys } from "@/features/surveys/hooks";

const CLASS_OPTIONS = [
  { value: "ghost_net", label: "Ghost Net" },
  { value: "debris", label: "Debris" },
  { value: "natural_object", label: "Natural Object" },
  { value: "unknown", label: "Unknown" },
];

const PRIORITY_OPTIONS = [
  { value: "critical", label: "Critical" },
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
];

const REVIEW_OPTIONS = [
  { value: "pending", label: "Pending" },
  { value: "unknown", label: "Unknown" },
  { value: "accepted_artificial", label: "Accepted - Artificial" },
  { value: "rejected_natural", label: "Rejected - Natural" },
];

export default function DetectionsPage() {
  return (
    <Suspense fallback={<AppShell title="Detection Results"><Panel className="p-6"><LoadingSkeleton rows={6} label="Loading detections..." /></Panel></AppShell>}>
      <DetectionsPageContent />
    </Suspense>
  );
}

function DetectionsPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const survey_id = searchParams.get("survey_id") ?? undefined;
  const detection_class = searchParams.get("detection_class") ?? undefined;
  const priority = searchParams.get("priority") ?? undefined;
  const review_status = searchParams.get("review_status") ?? undefined;

  function updateParam(key: string, value: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (value) {
      params.set(key, value);
    } else {
      params.delete(key);
    }
    router.push(`/app/detections?${params.toString()}`);
  }

  // Landing here from the sidebar means no survey scope at all, so the table
  // shows every survey's rows at once. A survey filter (and the Survey column
  // in DetectionTable) is what makes that list readable -- B2 in
  // docs/KNOWN_ISSUES.md.
  const { data: surveys } = useSurveys(1, 200);
  const surveyOptions = useMemo(
    () => (surveys?.items ?? []).map((s) => ({ value: s.id, label: s.name })),
    [surveys]
  );

  const { data, isLoading, isError, refetch } = useDetections({
    survey_id,
    detection_class,
    priority,
    review_status,
  });

  const summary = useMemo(() => {
    const items = data?.items ?? [];
    return {
      critical: items.filter((item) => item.priority === "critical").length,
      pending: items.filter((item) => item.review_status === "pending").length,
      accepted: items.filter((item) => item.review_status === "accepted_artificial").length,
    };
  }, [data]);

  return (
    <AppShell title="Detection Results">
      <div className="space-y-6">
        <section className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.95fr)]">
          <Panel className="p-6 sm:p-7">
            <p className="text-[11px] uppercase tracking-[0.32em] text-cyan-accent/85">Detection Review</p>
            <h2 className="mt-3 font-display text-3xl font-semibold tracking-wide text-slate-50 sm:text-4xl">
              Filter, rank, and investigate maritime anomalies with less noise.
            </h2>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-300">
              This queue is optimized for analyst triage. Use the filters to narrow the evidence set, then sort detections by confidence, time, or escalation level.
            </p>
          </Panel>

          <Panel className="p-6">
            <p className="text-[11px] uppercase tracking-[0.32em] text-cyan-accent/80">Queue Snapshot</p>
            <div className="mt-4 grid grid-cols-2 gap-3">
              <div className="rounded-2xl border border-abyss-600/70 bg-skytint/42 p-4">
                <p className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Visible</p>
                <p className="mt-2 font-mono text-3xl text-slate-100">{data?.items.length ?? 0}</p>
              </div>
              <div className="rounded-2xl border border-abyss-600/70 bg-skytint/42 p-4">
                <p className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Critical</p>
                <p className="mt-2 font-mono text-3xl text-alert-critical">{summary.critical}</p>
              </div>
              <div className="rounded-2xl border border-abyss-600/70 bg-skytint/42 p-4">
                <p className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Pending</p>
                <p className="mt-2 font-mono text-3xl text-cyan-accent">{summary.pending}</p>
              </div>
              <div className="rounded-2xl border border-abyss-600/70 bg-skytint/42 p-4">
                <p className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Accepted</p>
                <p className="mt-2 font-mono text-3xl text-emerald-300">{summary.accepted}</p>
              </div>
            </div>
          </Panel>
        </section>

        <Panel className="p-5">
          <div className="flex flex-wrap items-end gap-4">
            <FilterSelect label="Survey" value={survey_id ?? ""} options={surveyOptions} onChange={(v) => updateParam("survey_id", v)} />
            <FilterSelect label="Class" value={detection_class ?? ""} options={CLASS_OPTIONS} onChange={(v) => updateParam("detection_class", v)} />
            <FilterSelect label="Priority" value={priority ?? ""} options={PRIORITY_OPTIONS} onChange={(v) => updateParam("priority", v)} />
            <FilterSelect label="Review Status" value={review_status ?? ""} options={REVIEW_OPTIONS} onChange={(v) => updateParam("review_status", v)} />
            <div className="ml-auto text-sm text-slate-400">
              {data
                ? `Showing ${data.items.length} of ${data.total} detections` +
                  (survey_id ? "" : " across all surveys")
                : "Set filters to refine the queue"}
            </div>
          </div>
        </Panel>

        {isLoading ? (
          <Panel className="p-6">
            <LoadingSkeleton rows={6} label="Loading detections..." />
          </Panel>
        ) : isError ? (
          <ErrorState message="Unable to load detections." onRetry={() => refetch()} />
        ) : !data || data.items.length === 0 ? (
          <EmptyState title="No detections found." description="Adjust your filters or process a survey." />
        ) : (
          <DetectionTable detections={data.items} showSurvey={!survey_id} />
        )}
      </div>
    </AppShell>
  );
}
