"use client";

import clsx from "clsx";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { ApiError } from "@/api/client";
import { AppShell } from "@/components/AppShell";
import {
  formatDuration,
  PipelineStagePreview,
  ProcessingProgress,
  STAGE_DESCRIPTIONS,
} from "@/components/ProcessingProgress";
import { StatusIndicator } from "@/components/StatusIndicator";
import { LoadingSkeleton } from "@/components/States";
import { useToastStore } from "@/components/Toast";
import { useDetections } from "@/features/detections/hooks";
import { useCancelJob, useLatestJob, useStartProcessing, useSurveyJobs } from "@/features/processing/hooks";
import { useCreateReport } from "@/features/reports/hooks";
import { useFrameImage } from "@/features/sonar/hooks";
import { useSurvey } from "@/features/surveys/hooks";
import { useSurveyFiles } from "@/features/upload/hooks";
import { useSurveyRealtime } from "@/hooks/useRealtime";
import type { Detection, JobStage, ProcessingJob, SurveyFile } from "@/types";
import { formatConfidence, formatDateTime } from "@/utils/format";

const HeroWaterBackdrop = dynamic(
  () => import("@/components/three/HeroWaterBackdrop").then((m) => m.HeroWaterBackdrop),
  {
    ssr: false,
    // ssr:false means nothing at all renders here until the three.js chunk has
    // downloaded and the shader has compiled. Without a fallback that gap is
    // the PAGE BACKGROUND showing through -- a white flash on every cold load,
    // for as long as the chunk takes. Painting the shader's own deep-water
    // colour makes the wait read as the backdrop still loading rather than as
    // a broken page. Matches the pattern HeroSonar already used.
    loading: () => <div aria-hidden className="absolute inset-0 bg-[#072639]" />,
  }
);

// Same shape-first convention as the survey detail page's ValidationStrip:
// filled square = VALID, hollow red square = INVALID, dash = PENDING.
const VALIDATION_TICK: Record<string, string> = {
  VALID: "bg-emerald-500",
  INVALID: "border-2 border-alert-critical bg-transparent",
  PENDING: "h-[3px] self-center bg-ink-4",
};

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
  const { data: files } = useSurveyFiles(surveyId);
  const startProcessing = useStartProcessing(surveyId);
  const cancelJob = useCancelJob(surveyId);
  const push = useToastStore((s) => s.push);
  const connectionStatus = useSurveyRealtime(surveyId);

  const isRunning = Boolean(job && RUNNING_STATUSES.includes(job.status));
  const isFinished = Boolean(job && FINISHED_STATUSES.includes(job.status));
  const isStopped = Boolean(job && (job.status === "FAILED" || job.status === "CANCELLED"));

  const log = useStageLog(job);

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
      <div className="mb-1 flex items-center justify-between">
        <Link href={`/app/surveys/${surveyId}`} className="text-sm text-cyan-accent hover:underline">
          ← Back to survey
        </Link>
        <StatusIndicator status={connectionStatus} />
      </div>
      {survey && (
        <p className="mb-4 text-xs uppercase tracking-wide text-slate-500">
          {survey.source || "No source recorded"} · {survey.sonar_type || "Unknown sonar type"}
        </p>
      )}

      {jobLoading ? (
        <div className="panel p-6">
          <LoadingSkeleton rows={3} label="Restoring processing status…" />
        </div>
      ) : !job ? (
        <NotStarted
          surveyId={surveyId}
          fileCount={survey?.file_count ?? 0}
          source={survey?.source ?? null}
          sonarType={survey?.sonar_type ?? null}
          files={files}
          onStart={() => handleStart()}
          starting={startProcessing.isPending}
        />
      ) : (
        <div className="panel p-6">
          <ProcessingProgress job={job} />

          {log.length > 0 && (
            <div className="mt-4 max-h-32 overflow-y-auto border border-abyss-700 bg-abyss-900/40 p-3 font-mono text-[11px] text-slate-400">
              {log.map((entry, i) => (
                <div key={i} className="flex gap-2">
                  <span className="shrink-0 text-slate-600">{entry.time}</span>
                  <span>{entry.message}</span>
                </div>
              ))}
            </div>
          )}

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
        </div>
      )}
    </AppShell>
  );
}

/** Tracks stage transitions as they're observed from the polled/pushed job
 * object and turns them into a small live log -- there is no backend event
 * history to read, so this is a client-observed timeline, not a server-logged
 * one, and it resets whenever a new job (a fresh run) starts. */
function useStageLog(job: ProcessingJob | null | undefined) {
  const [log, setLog] = useState<{ time: string; message: string }[]>([]);
  const prevStageRef = useRef<JobStage | null>(null);
  const prevJobIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!job) return;
    if (prevJobIdRef.current !== job.id) {
      prevJobIdRef.current = job.id;
      prevStageRef.current = null;
      setLog([]);
    }
    if (prevStageRef.current !== job.stage) {
      prevStageRef.current = job.stage;
      setLog((entries) =>
        [
          { time: new Date().toLocaleTimeString(), message: `${job.stage} — ${STAGE_DESCRIPTIONS[job.stage]}` },
          ...entries,
        ].slice(0, 20)
      );
    }
  }, [job]);

  return log;
}

/** The pre-launch screen: what's about to be processed, a preview of the
 * pipeline it will walk through, and the one button that starts it. This used
 * to be a single button on an otherwise blank panel with no context at all. */
function NotStarted({
  surveyId,
  fileCount,
  source,
  sonarType,
  files,
  onStart,
  starting,
}: {
  surveyId: string;
  fileCount: number;
  source: string | null;
  sonarType: string | null;
  files: SurveyFile[] | undefined;
  onStart: () => void;
  starting: boolean;
}) {
  return (
    <div className="space-y-6">
      <div className="relative min-h-[300px] overflow-hidden border border-abyss-600">
        <div className="absolute inset-0">
          <HeroWaterBackdrop />
        </div>
        <div className="absolute inset-0 bg-gradient-to-t from-atlantic-deep via-atlantic/55 to-atlantic/10" />
        <div className="relative z-10 flex flex-col items-center gap-4 px-6 py-12 text-center">
          <p className="text-[11px] uppercase tracking-[0.28em] text-skytint/85">Ready To Launch</p>
          <p className="max-w-lg text-sm leading-6 text-paper/85">
            This survey has not been processed yet. A run decodes every uploaded file into frames, scores each one
            against the trained model, and geotags whatever clears the detection threshold.
          </p>
          <button
            onClick={onStart}
            disabled={starting || fileCount === 0}
            className="rounded-md bg-cyan-accent px-5 py-2 text-sm font-medium text-abyss-950 hover:bg-cyan-accent/90 disabled:opacity-50"
          >
            {starting ? "Starting…" : "Start Processing"}
          </button>
          {fileCount === 0 && (
            <p className="text-xs text-paper/70">
              No files uploaded yet.{" "}
              <Link href={`/app/surveys/${surveyId}`} className="text-skytint hover:underline">
                Go upload sonar files
              </Link>{" "}
              before starting.
            </p>
          )}
        </div>
      </div>

      {fileCount > 0 && (
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="panel p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">Mission</p>
            <p className="mt-1 text-sm text-slate-200">{source || "No source recorded"}</p>
            <p className="text-sm text-slate-400">{sonarType || "Unknown sonar type"}</p>
          </div>
          <div className="panel p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">
              {fileCount} file{fileCount === 1 ? "" : "s"} queued
            </p>
            <ul className="mt-1 space-y-1.5 text-sm text-slate-300">
              {(files ?? []).slice(0, 5).map((f) => (
                <li key={f.id} className="flex items-center gap-2">
                  <span
                    title={f.validation_status}
                    aria-label={f.validation_status}
                    className={clsx("h-2 w-2 shrink-0", VALIDATION_TICK[f.validation_status] ?? VALIDATION_TICK.PENDING)}
                  />
                  <span className="truncate">{f.filename}</span>
                </li>
              ))}
            </ul>
            {files && files.length > 5 && (
              <p className="mt-1 text-xs text-slate-500">+{files.length - 5} more</p>
            )}
          </div>
        </div>
      )}

      <div className="panel p-4">
        <p className="mb-3 text-xs uppercase tracking-wide text-slate-500">Pipeline preview</p>
        <PipelineStagePreview />
      </div>
    </div>
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
  const durationSeconds =
    job.started_at && job.completed_at
      ? (new Date(job.completed_at).getTime() - new Date(job.started_at).getTime()) / 1000
      : null;

  const router = useRouter();
  const push = useToastStore((s) => s.push);
  const createReport = useCreateReport();

  async function handleGenerateReport() {
    try {
      await createReport.mutateAsync({ survey_id: surveyId, type: "full_survey", format: "csv" });
      push("Report generated.", "success");
      router.push(`/app/reports?survey_id=${surveyId}`);
    } catch {
      push("Unable to generate report.", "error");
    }
  }

  return (
    <div
      className={`mt-6 rounded-md border p-5 ${
        partial ? "border-alert-high/40 bg-alert-high/10" : "border-emerald-500/40 bg-emerald-400/5"
      }`}
    >
      <p className={`text-sm font-medium ${partial ? "text-alert-high" : "text-emerald-300"}`}>
        {partial ? "Processing finished with errors" : "Processing complete"}
        {durationSeconds !== null && (
          <span className="ml-2 font-mono text-xs font-normal text-slate-500">in {formatDuration(durationSeconds)}</span>
        )}
      </p>
      <p className="mt-1 text-sm text-slate-300">
        {job.frames_processed} frame{job.frames_processed === 1 ? "" : "s"} processed
        {job.frames_failed > 0 ? `, ${job.frames_failed} failed` : ""} · {job.detections_found} detection
        {job.detections_found === 1 ? "" : "s"} found.
      </p>

      <RunComparison job={job} surveyId={surveyId} />

      {job.detections_found === 0 ? (
        <p className="mt-2 text-xs text-slate-500">
          No candidates cleared the detection threshold on this survey. That is a result, not a failure — the
          frames were scored and nothing in them met the bar. If that&apos;s unexpected, double-check the uploaded
          files on the{" "}
          <Link href={`/app/surveys/${surveyId}`} className="text-cyan-accent hover:underline">
            survey page
          </Link>{" "}
          before re-processing.
        </p>
      ) : (
        <DetectionPreviewStrip surveyId={surveyId} />
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
        <button
          onClick={handleGenerateReport}
          disabled={createReport.isPending}
          className="rounded-md border border-abyss-600 px-4 py-2 text-sm text-slate-200 hover:border-cyan-accent/50 hover:text-cyan-accent disabled:opacity-50"
        >
          {createReport.isPending ? "Generating…" : "Generate Report"}
        </button>
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

/** How this run compares with the one it replaced.
 *
 * Only rendered for a survey that has actually been run more than once --
 * a first run has nothing to be measured against, and showing "+N vs. nothing"
 * would invent a baseline that does not exist.
 *
 * The previous run is the most recent job that ISN'T this one and that
 * actually finished: a cancelled or failed run stopped partway through, so its
 * counts describe how far it got rather than what the survey contains, and
 * comparing against those would report a delta that is really just the
 * interruption. */
function RunComparison({ job, surveyId }: { job: ProcessingJob; surveyId: string }) {
  const { data: jobs } = useSurveyJobs(surveyId);

  const previous = (jobs ?? []).find(
    (j) => j.id !== job.id && (j.status === "COMPLETED" || j.status === "PARTIAL")
  );
  if (!previous) return null;

  const deltas = [
    { label: "Detections", now: job.detections_found, before: previous.detections_found },
    { label: "Frames processed", now: job.frames_processed, before: previous.frames_processed },
    { label: "Frames failed", now: job.frames_failed, before: previous.frames_failed, lowerIsBetter: true },
  ];

  return (
    <div className="mt-3 border border-abyss-600/70 bg-abyss-900/30 p-3">
      <p className="text-xs uppercase tracking-wide text-slate-500">
        vs. previous run
        <span className="ml-2 font-mono normal-case tracking-normal text-slate-600">
          {formatDateTime(previous.completed_at ?? previous.created_at)}
        </span>
      </p>
      <div className="mt-2 flex flex-wrap gap-x-6 gap-y-2">
        {deltas.map((d) => (
          <DeltaStat key={d.label} {...d} />
        ))}
      </div>
    </div>
  );
}

function DeltaStat({
  label,
  now,
  before,
  lowerIsBetter = false,
}: {
  label: string;
  now: number;
  before: number;
  lowerIsBetter?: boolean;
}) {
  const diff = now - before;
  // Neutral when unchanged: a green "0" reads as a result rather than as the
  // absence of one.
  const tone =
    diff === 0
      ? "text-slate-500"
      : diff > 0 === lowerIsBetter
        ? "text-alert-high"
        : "text-emerald-300";

  return (
    <div>
      <p className="text-[11px] uppercase tracking-wide text-slate-500">{label}</p>
      <p className="font-mono text-sm text-slate-200">
        {now}
        <span className={clsx("ml-1.5 text-xs", tone)}>
          {diff === 0 ? "no change" : `${diff > 0 ? "+" : ""}${diff}`}
        </span>
        <span className="ml-1.5 text-xs text-slate-600">was {before}</span>
      </p>
    </div>
  );
}

/** A quick look at what got flagged, right on the page that just finished
 * scoring it -- instead of only a count and a link elsewhere. */
function DetectionPreviewStrip({ surveyId }: { surveyId: string }) {
  const { data } = useDetections({ survey_id: surveyId, page_size: 4 });
  const items = data?.items ?? [];
  if (items.length === 0) return null;

  return (
    <div className="mt-3">
      <p className="mb-2 text-xs uppercase tracking-wide text-slate-500">Top detections</p>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {items.map((d) => (
          <DetectionThumb key={d.id} detection={d} />
        ))}
      </div>
    </div>
  );
}

function DetectionThumb({ detection }: { detection: Detection }) {
  const { url } = useFrameImage(detection.frame_id);

  return (
    <Link
      href={`/app/detections/${detection.id}`}
      className="group relative block aspect-square overflow-hidden border border-abyss-600 bg-abyss-900"
    >
      {url ? (
        // Object-URL blob preview, not a static asset -- next/image can't
        // optimize a blob: URL, and there's nothing to optimize for a 4-tile
        // strip anyway.
        // eslint-disable-next-line @next/next/no-img-element
        <img src={url} alt="" className="h-full w-full object-cover transition group-hover:scale-105" />
      ) : (
        <div className="h-full w-full animate-pulse bg-abyss-800" />
      )}
      <span className="absolute inset-x-0 bottom-0 truncate bg-abyss-950/80 px-1.5 py-1 text-[10px] text-slate-200">
        {detection.detection_class} · {formatConfidence(detection.calibrated_confidence)}
      </span>
    </Link>
  );
}
