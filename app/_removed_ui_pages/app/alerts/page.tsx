"use client";

import Link from "next/link";
import { useMemo } from "react";

import { AppShell } from "@/components/AppShell";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/States";
import { useDetections } from "@/features/detections/hooks";
import { useRecentJobs } from "@/features/system/hooks";
import { useSurveys } from "@/features/surveys/hooks";
import type { Detection, ProcessingJob } from "@/types";

type Severity = "critical" | "warning" | "info";

interface Alert {
  id: string;
  severity: Severity;
  title: string;
  description: string;
  href: string;
  timestamp: string;
}

const SEVERITY_STYLES: Record<Severity, string> = {
  critical: "border-alert-critical/40 bg-alert-critical/5",
  warning: "border-alert-high/40 bg-alert-high/5",
  info: "border-cyan-accent/30 bg-cyan-accent/5",
};

const SEVERITY_LABELS: Record<Severity, string> = {
  critical: "Critical",
  warning: "Warning",
  info: "Information",
};

function detectionAlerts(detections: Detection[] | undefined, severity: Severity): Alert[] {
  if (!detections) return [];
  return detections.map((d) => ({
    id: `detection-${d.id}`,
    severity,
    title: `${d.detection_class.replace("_", " ")} — ${d.detection_ref}`,
    description: `Confidence ${d.calibrated_confidence !== null ? `${Math.round(d.calibrated_confidence * 100)}%` : "unavailable"} · awaiting review`,
    href: `/app/detections/${d.id}`,
    timestamp: d.created_at,
  }));
}

function jobAlerts(jobs: ProcessingJob[] | undefined, surveys: { id: string; name: string }[] | undefined): Alert[] {
  if (!jobs) return [];
  return jobs
    .filter((j) => j.status === "FAILED" || j.status === "PARTIAL")
    .map((j) => ({
      id: `job-${j.id}`,
      severity: j.status === "FAILED" ? ("critical" as const) : ("warning" as const),
      title: `Processing ${j.status === "FAILED" ? "failed" : "partially completed"} — ${
        surveys?.find((s) => s.id === j.survey_id)?.name ?? j.survey_id.slice(0, 8)
      }`,
      description: j.error_summary ?? `${j.frames_failed} of ${j.frames_total} frames failed`,
      href: `/app/surveys/${j.survey_id}/process`,
      timestamp: j.completed_at ?? j.created_at,
    }));
}

export default function AlertsPage() {
  const { data: surveys } = useSurveys(1, 200);
  const critical = useDetections({ priority: "critical", review_status: "pending", page_size: 100 });
  const criticalUnknown = useDetections({ priority: "critical", review_status: "unknown", page_size: 100 });
  const high = useDetections({ priority: "high", review_status: "pending", page_size: 100 });
  const jobs = useRecentJobs({ limit: 50 });

  const isLoading = critical.isLoading || criticalUnknown.isLoading || high.isLoading || jobs.isLoading;
  const isError = critical.isError || criticalUnknown.isError || high.isError || jobs.isError;

  const alerts = useMemo(() => {
    const list: Alert[] = [
      ...detectionAlerts(critical.data?.items, "critical"),
      ...detectionAlerts(criticalUnknown.data?.items, "critical"),
      ...detectionAlerts(high.data?.items, "warning"),
      ...jobAlerts(jobs.data, surveys?.items),
    ];
    return list.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
  }, [critical.data, criticalUnknown.data, high.data, jobs.data, surveys]);

  const groups: Record<Severity, Alert[]> = {
    critical: alerts.filter((a) => a.severity === "critical"),
    warning: alerts.filter((a) => a.severity === "warning"),
    info: alerts.filter((a) => a.severity === "info"),
  };

  return (
    <AppShell title="Alerts">
      {isLoading ? (
        <LoadingSkeleton rows={5} label="Scanning for critical detections and processing issues…" />
      ) : isError ? (
        <ErrorState message="Unable to load alerts." onRetry={() => { critical.refetch(); high.refetch(); jobs.refetch(); }} />
      ) : alerts.length === 0 ? (
        <EmptyState title="No active alerts." description="Critical detections and processing failures will appear here as they occur." />
      ) : (
        <div className="space-y-8">
          {(["critical", "warning", "info"] as Severity[]).map((severity) =>
            groups[severity].length === 0 ? null : (
              <section key={severity}>
                <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
                  {SEVERITY_LABELS[severity]} ({groups[severity].length})
                </h2>
                <div className="space-y-2">
                  {groups[severity].map((alert) => (
                    <Link
                      key={alert.id}
                      href={alert.href}
                      className={`block rounded-lg border p-4 transition hover:brightness-125 ${SEVERITY_STYLES[alert.severity]}`}
                    >
                      <div className="flex items-center justify-between gap-4">
                        <p className="text-sm font-medium text-slate-100">{alert.title}</p>
                        <span className="shrink-0 text-xs text-slate-500">
                          {new Date(alert.timestamp).toLocaleString()}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-slate-400">{alert.description}</p>
                    </Link>
                  ))}
                </div>
              </section>
            )
          )}
        </div>
      )}
    </AppShell>
  );
}
