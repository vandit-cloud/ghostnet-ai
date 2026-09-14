"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { ApiError } from "@/api/client";
import { AppShell } from "@/components/AppShell";
import { ProcessingProgress } from "@/components/ProcessingProgress";
import { StatusIndicator } from "@/components/StatusIndicator";
import { LoadingSkeleton } from "@/components/States";
import { useToastStore } from "@/components/Toast";
import { useCancelJob, useLatestJob, useStartProcessing } from "@/features/processing/hooks";
import { useSurvey } from "@/features/surveys/hooks";
import { useSurveyRealtime } from "@/hooks/useRealtime";
import type { ProcessingJob } from "@/types";

const RUNNING_STATUSES: ProcessingJob["status"][] = ["QUEUED", "VALIDATING", "PROCESSING"];
const FINISHED_STATUSES: ProcessingJob["status"][] = ["COMPLETED", "PARTIAL"];

export default function ProcessingPage() {
  const params = useParams<{ surveyId: string }>();
  const surveyId = params.surveyId;

  const { data: survey } = useSurvey(surveyId);
  // One endpoint, one truth. Reading /jobs/active for the id and /jobs/{id}
  // for the detail is what made a finished job vanish and the bar jump --
  // A1 and A3 in docs/KNOWN_ISSUES.md.
  const { data: job, isLoading: jobLoading } = useLatestJob(surveyId);
  const startProcessing = useStartProcessing(surveyId);
  const cancelJob = useCancelJob(surveyId);
  const push = useToastStore((s) => s.push);
  const connectionStatus = useSurveyRealtime(surveyId);

  const isRunning = Boolean(job && RUNNING_STATUSES.includes(job.status));
  const isFinished = Boolean(job && FINISHED_STATUSES.includes(job.status));
  const isStopped = Boolean(job && (job.status === "FAILED" || job.status === "CANCELLED"));

  async function handleStart(forceRestart = false) {
    try {
      await startProcessing.mutateAsync(forceRestart);
    } catch (error) {
      // The 409 re-process guard carries an explanation worth reading -- it is
      // why a run that already succeeded looks un-runnable. Show the server's
      // own message instead of a generic failure.
      if (error instanceof ApiError) {
        push(error.message, "error");
      } else {
        push("Unable to start processing.", "error");
      }
    }
  }

  function handleReprocess() {
    const confirmed = window.confirm(
      "Re-processing discards this survey's existing detections and every review " +
        "decision made on them, then scores it again from scratch.\n\nContinue?"
    );
    if (confirmed) void handleStart(true);
  }

  return (
    <AppShell title={`Processing — ${survey?.name ?? ""}`}>
      <div className="mb-4 flex items-center justify-between">
        <Link href={`/app/surveys/${surveyId}`} className="text-sm text-cyan-accent hover:underline">
          ← Back to survey
        </Link>
        <StatusIndicator status={connectionStatus} />
      </div>

      <div className="panel p-6">
        {jobLoading ? (
          <LoadingSkeleton rows={3} label="Restoring processing status…" />
        ) : !job ? (
          <div className="flex flex-col items-center gap-4 py-10 text-center">
            <p className="text-slate-300">This survey has not been processed yet.</p>
            <button
              onClick={() => handleStart()}
              disabled={startProcessing.isPending || !survey || survey.file_count === 0}
              className="rounded-md bg-cyan-accent px-5 py-2 text-sm font-medium text-abyss-950 hover:bg-cyan-accent/90 disabled:opacity-50"
            >
              {startProcessing.isPending ? "Starting…" : "Start Processing"}
            </button>
            {survey && survey.file_count === 0 && (
              <p className="text-xs text-slate-500">Upload at least one file before starting processing.</p>
            )}
          </div>
        ) : (
          <>
            <ProcessingProgress job={job} />

            {isRunning && (
              <div className="mt-6 flex justify-end">
                <button
                  onClick={() => cancelJob.mutate(job.id)}
                  disabled={cancelJob.isPending}
                  className="rounded-md border border-alert-critical/50 px-4 py-1.5 text-sm text-alert-critical hover:bg-alert-critical/10"
                >
                  Cancel Processing
                </button>
              </div>
            )}

            {isFinished && <CompletionPanel job={job} surveyId={surveyId} onReprocess={handleReprocess} />}

            {isStopped && (
              <div className="mt-6 rounded-md border border-abyss-600 bg-abyss-800/40 p-5">
                <p className="text-sm text-slate-200">
                  {job.status === "CANCELLED" ? "This run was cancelled before it finished." : "This run failed."}{" "}
                  {job.frames_processed > 0 &&
                    `${job.frames_processed} of ${job.frames_total} frames were processed before it stopped.`}
                </p>
                {job.error_summary && <p className="mt-1 text-xs text-slate-500">{job.error_summary}</p>}
                <div className="mt-4 flex flex-wrap gap-2">
                  <button
                    onClick={() => handleStart()}
                    disabled={startProcessing.isPending}
                    className="rounded-md bg-cyan-accent px-4 py-2 text-sm font-medium text-abyss-950 hover:bg-cyan-accent/90 disabled:opacity-50"
                  >
                    {startProcessing.isPending ? "Starting…" : "Run Again"}
                  </button>
                  {job.detections_found > 0 && (
                    <button
                      onClick={handleReprocess}
                      className="rounded-md border border-abyss-600 px-4 py-2 text-sm text-slate-300 hover:border-cyan-accent/50 hover:text-cyan-accent"
                    >
                      Re-process from scratch
                    </button>
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </AppShell>
  );
}

/** What a finished run leaves behind, and where to go next.
 *
 * The page used to end at the progress bar: no counts, no navigation, nothing
 * naming the survey the results belong to. An operator who watched a run
 * succeed was left on a screen that said nothing about it -- A2 in
 * docs/KNOWN_ISSUES.md. Every link carries `survey_id` so the destination
 * opens scoped to this survey rather than to every survey in the database. */
function CompletionPanel({
  job,
  surveyId,
  onReprocess,
}: {
  job: ProcessingJob;
  surveyId: string;
  onReprocess: () => void;
}) {
  const partial = job.status === "PARTIAL";

  return (
    <div
      className={`mt-6 rounded-md border p-5 ${
        partial ? "border-alert-high/40 bg-alert-high/10" : "border-emerald-500/40 bg-emerald-400/5"
      }`}
    >
      <p className={`text-sm font-medium ${partial ? "text-alert-high" : "text-emerald-300"}`}>
        {partial ? "Processing finished with errors" : "Processing complete"}
      </p>
      <p className="mt-1 text-sm text-slate-300">
        {job.frames_processed} frame{job.frames_processed === 1 ? "" : "s"} processed
        {job.frames_failed > 0 ? `, ${job.frames_failed} failed` : ""} · {job.detections_found} detection
        {job.detections_found === 1 ? "" : "s"} found.
      </p>

      {job.detections_found === 0 && (
        <p className="mt-2 text-xs text-slate-500">
          No candidates cleared the detection threshold on this survey. That is a result, not a failure — the
          frames were scored and nothing in them met the bar.
        </p>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Link
          href={`/app/detections?survey_id=${surveyId}`}
          className="rounded-md bg-cyan-accent px-4 py-2 text-sm font-medium text-abyss-950 hover:bg-cyan-accent/90"
        >
          View Detections
        </Link>
        <Link
          href={`/app/map?survey_id=${surveyId}`}
          className="rounded-md border border-abyss-600 px-4 py-2 text-sm text-slate-200 hover:border-cyan-accent/50 hover:text-cyan-accent"
        >
          Open Map
        </Link>
        <Link
          href={`/app/reports?survey_id=${surveyId}`}
          className="rounded-md border border-abyss-600 px-4 py-2 text-sm text-slate-200 hover:border-cyan-accent/50 hover:text-cyan-accent"
        >
          Generate Report
        </Link>
        <button
          onClick={onReprocess}
          className="ml-auto rounded-md border border-abyss-700 px-4 py-2 text-sm text-slate-400 hover:border-alert-critical/50 hover:text-alert-critical"
        >
          Re-process
        </button>
      </div>
    </div>
  );
}
