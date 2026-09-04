import Link from "next/link";
import clsx from "clsx";

import { FormatIcon } from "@/components/FormatIcon";
import type { Report } from "@/types";
import { formatDateTime } from "@/utils/format";

const STATUS_STYLES: Record<string, string> = {
  QUEUED: "text-slate-400",
  PROCESSING: "text-cyan-accent",
  COMPLETED: "text-emerald-300",
  FAILED: "text-alert-critical",
};

export function ReportCard({ report }: { report: Report }) {
  return (
    <Link
      href={`/app/reports/${report.id}`}
      className="flex flex-wrap items-center justify-between gap-4 panel px-5 py-4 transition hover:border-cyan-accent/40"
    >
      <div className="min-w-0">
        <p className="text-[11px] uppercase tracking-[0.26em] text-slate-500">Report Artifact</p>
        <p className="mt-2 font-semibold capitalize text-slate-100">{report.type.replace("_", " ")}</p>
        <p className="mt-2 flex items-center gap-1.5 font-mono text-xs tabular-nums text-slate-500">
          <FormatIcon format={report.format} /> {report.format.toUpperCase()} | {formatDateTime(report.created_at)}
        </p>
      </div>
      <span className={clsx("flex items-center gap-1.5 text-sm font-medium uppercase tracking-[0.18em]", STATUS_STYLES[report.status])}>
        {report.status === "PROCESSING" ? <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-accent" /> : null}
        {report.status}
      </span>
    </Link>
  );
}
