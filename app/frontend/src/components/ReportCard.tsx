import { useState, type MouseEvent } from "react";
import clsx from "clsx";

import { FormatIcon } from "@/components/FormatIcon";
import { useToastStore } from "@/components/Toast";
import { downloadReport } from "@/features/reports/hooks";
import type { Report } from "@/types";
import { formatDateTime } from "@/utils/format";

const STATUS_STYLES: Record<string, string> = {
  QUEUED: "text-slate-400",
  PROCESSING: "text-cyan-accent",
  COMPLETED: "text-emerald-300",
  FAILED: "text-alert-critical",
};

function DownloadIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M12 3v12m0 0-4.5-4.5M12 15l4.5-4.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M4.5 17v2a1.5 1.5 0 0 0 1.5 1.5h12a1.5 1.5 0 0 0 1.5-1.5v-2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function ReportCard({ report }: { report: Report }) {
  const push = useToastStore((s) => s.push);
  const [downloading, setDownloading] = useState(false);

  async function handleDownload(event: MouseEvent) {
    event.preventDefault();
    if (downloading) return;
    setDownloading(true);
    try {
      await downloadReport(report.id, `report-${report.id}.${report.format}`);
    } catch {
      push("Unable to download report.", "error");
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-4 panel px-5 py-4">
      <div className="min-w-0">
        <p className="text-[11px] uppercase tracking-[0.26em] text-slate-500">Report Artifact</p>
        <p className="mt-2 font-semibold capitalize text-slate-100">{report.type.replace("_", " ")}</p>
        <p className="mt-2 flex items-center gap-1.5 font-mono text-xs tabular-nums text-slate-500">
          <FormatIcon format={report.format} /> {report.format.toUpperCase()} | {formatDateTime(report.created_at)}
        </p>
      </div>
      <div className="flex items-center gap-3">
        <span className={clsx("flex items-center gap-1.5 text-sm font-medium uppercase tracking-[0.18em]", STATUS_STYLES[report.status])}>
          {report.status === "PROCESSING" ? <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-accent" /> : null}
          {report.status}
        </span>
        {report.status === "COMPLETED" && (
          <button
            type="button"
            onClick={handleDownload}
            disabled={downloading}
            title={`Download ${report.format.toUpperCase()}`}
            aria-label={`Download ${report.format.toUpperCase()}`}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-abyss-600/80 text-slate-400 transition hover:border-cyan-accent/50 hover:text-cyan-accent disabled:opacity-50"
          >
            <DownloadIcon />
          </button>
        )}
      </div>
    </div>
  );
}
