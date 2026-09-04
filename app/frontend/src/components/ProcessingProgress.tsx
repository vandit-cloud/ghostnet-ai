import clsx from "clsx";

import { JobStatusBadge } from "@/components/Badges";
import type { JobStage, ProcessingJob } from "@/types";

const STAGES: JobStage[] = [
  "VALIDATING",
  "DECODING",
  "PREPROCESSING",
  "DETECTION",
  "VERIFICATION",
  "CALIBRATION",
  "GEOTAGGING",
  "SAVING",
];

export function ProcessingProgress({ job }: { job: ProcessingJob }) {
  const currentIndex = STAGES.indexOf(job.stage);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <JobStatusBadge status={job.status} />
        <span className="text-sm text-slate-400">
          {job.frames_total > 0 ? `${job.progress}%` : "Calculating…"}
        </span>
      </div>

      <div className="h-2 w-full overflow-hidden rounded-full bg-abyss-700">
        <div
          className="h-2 rounded-full bg-cyan-accent transition-all duration-300"
          style={{ width: `${job.progress}%` }}
        />
      </div>

      {/* Connected stepper: a traveling pulse at the current stage instead of
          a static badge grid - "completed stages remain visually calm" (only
          the current node pulses), matching the pipeline's own story. */}
      <ol className="flex items-start gap-0 overflow-x-auto pb-1 text-xs">
        {STAGES.map((stage, i) => {
          const state = i < currentIndex ? "done" : i === currentIndex ? "current" : "pending";
          return (
            <li key={stage} className="relative flex min-w-[76px] flex-1 flex-col items-center gap-2 px-1">
              {i > 0 && (
                <span
                  className={clsx(
                    "absolute right-1/2 top-[9px] h-0.5 w-full",
                    i <= currentIndex ? "bg-cyan-accent/70" : "bg-abyss-700"
                  )}
                />
              )}
              <span className="relative z-10 flex h-[18px] w-[18px] items-center justify-center">
                {state === "current" && (
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-cyan-accent/60" />
                )}
                <span
                  className={clsx(
                    "relative h-2.5 w-2.5 rounded-full border-2",
                    state === "done" && "border-emerald-400 bg-emerald-400",
                    state === "current" && "border-cyan-accent bg-cyan-accent",
                    state === "pending" && "border-abyss-600 bg-abyss-800"
                  )}
                />
              </span>
              <span
                className={clsx(
                  "text-center text-[10px] font-medium uppercase tracking-wide",
                  state === "done" && "text-emerald-300",
                  state === "current" && "text-cyan-accent",
                  state === "pending" && "text-slate-500"
                )}
              >
                {stage}
              </span>
            </li>
          );
        })}
      </ol>

      <FrameBreakdownBar job={job} />

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat label="Frames Processed" value={job.frames_processed} />
        <Stat label="Frames Failed" value={job.frames_failed} tone={job.frames_failed > 0 ? "critical" : undefined} />
        <Stat label="Detections" value={job.detections_found} />
        <Stat label="Frames Total" value={job.frames_total} />
      </div>

      {job.error_summary && (
        <p className="rounded-md border border-alert-critical/40 bg-alert-critical/5 px-4 py-2 text-sm text-alert-critical">
          {job.error_summary}
        </p>
      )}
    </div>
  );
}

/** One glance at processed/failed/remaining instead of reading four separate
 * tiles - derived from the same counts the tiles below already show. */
function FrameBreakdownBar({ job }: { job: ProcessingJob }) {
  const total = Math.max(job.frames_total, 1);
  const processedPct = Math.min(100, (job.frames_processed / total) * 100);
  const failedPct = Math.min(100 - processedPct, (job.frames_failed / total) * 100);
  const remaining = Math.max(job.frames_total - job.frames_processed - job.frames_failed, 0);

  return (
    <div>
      <div className="flex h-2 w-full overflow-hidden rounded-full bg-abyss-700">
        <div className="h-full bg-cyan-accent transition-all duration-300" style={{ width: `${processedPct}%` }} />
        <div className="h-full bg-alert-critical transition-all duration-300" style={{ width: `${failedPct}%` }} />
      </div>
      <div className="mt-1.5 flex gap-4 text-[11px] text-slate-500">
        <span className="flex items-center gap-1">
          <span className="h-1.5 w-1.5 rounded-full bg-cyan-accent" /> {job.frames_processed} processed
        </span>
        <span className="flex items-center gap-1">
          <span className="h-1.5 w-1.5 rounded-full bg-alert-critical" /> {job.frames_failed} failed
        </span>
        <span className="flex items-center gap-1">
          <span className="h-1.5 w-1.5 rounded-full bg-abyss-600" /> {remaining} remaining
        </span>
      </div>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone?: "critical" }) {
  return (
    <div className="panel p-3 text-center">
      <p className={clsx("text-xl font-semibold", tone === "critical" ? "text-alert-critical" : "text-slate-100")}>
        {value}
      </p>
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
    </div>
  );
}
