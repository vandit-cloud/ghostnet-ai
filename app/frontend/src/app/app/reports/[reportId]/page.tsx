"use client";

import { useParams } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { FormatIcon } from "@/components/FormatIcon";
import { ErrorState, LoadingSkeleton } from "@/components/States";
import { useToastStore } from "@/components/Toast";
import { downloadReport, useReport } from "@/features/reports/hooks";
import { formatDateTime } from "@/utils/format";

const STATUS_LABEL: Record<string, string> = {
  QUEUED: "Queued",
  PROCESSING: "Generating report…",
  COMPLETED: "Ready to download",
  FAILED: "Report generation failed",
};

export default function ReportDetailPage() {
  const params = useParams<{ reportId: string }>();
  const { data: report, isLoading, isError, refetch } = useReport(params.reportId);
  const push = useToastStore((s) => s.push);

  if (isLoading) {
    return (
      <AppShell title="Report">
        <LoadingSkeleton rows={3} label="Loading report…" />
      </AppShell>
    );
  }

  if (isError || !report) {
    return (
      <AppShell title="Report">
        <ErrorState message="Unable to load report." onRetry={() => refetch()} />
      </AppShell>
    );
  }

  async function handleDownload() {
    try {
      await downloadReport(report!.id, `report-${report!.id}.${report!.format}`);
    } catch {
      push("Unable to download report.", "error");
    }
  }

  return (
    <AppShell title="Report">
      <div className="max-w-lg space-y-4 panel p-6">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Type</p>
          <p className="capitalize text-slate-100">{report.type.replace("_", " ")}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Format</p>
          <p className="flex items-center gap-1.5 text-slate-100">
            <FormatIcon format={report.format} /> {report.format.toUpperCase()}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Status</p>
          <p className="flex items-center gap-1.5 text-slate-100">
            {report.status === "PROCESSING" && (
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-accent" />
            )}
            {STATUS_LABEL[report.status] ?? report.status}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Generated</p>
          <p className="text-slate-100">{formatDateTime(report.created_at)}</p>
        </div>
        {report.error_summary && <p className="text-sm text-alert-critical">{report.error_summary}</p>}

        <button
          onClick={handleDownload}
          disabled={report.status !== "COMPLETED"}
          className="w-full rounded-md bg-cyan-accent py-2 text-sm font-medium text-abyss-950 hover:bg-cyan-accent/90 disabled:opacity-50"
        >
          Download {report.format.toUpperCase()}
        </button>
      </div>
    </AppShell>
  );
}
