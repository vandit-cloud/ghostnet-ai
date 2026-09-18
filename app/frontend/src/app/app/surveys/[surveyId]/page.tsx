"use client";

import clsx from "clsx";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { AppShell } from "@/components/AppShell";
import { SurveyStatusBadge } from "@/components/Badges";
import { FileValidationCard } from "@/components/FileValidationCard";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/States";
import { useToastStore } from "@/components/Toast";
import { UploadDropzone } from "@/components/UploadDropzone";
import { useDeleteFile, useSurveyFiles, useUploadFile } from "@/features/upload/hooks";
import { ApiError } from "@/api/client";
import { useDeleteSurvey, useSurvey } from "@/features/surveys/hooks";
import type { SurveyFile } from "@/types";
import { formatDateTime } from "@/utils/format";

export default function SurveyDetailPage() {
  const params = useParams<{ surveyId: string }>();
  const router = useRouter();
  const surveyId = params.surveyId;

  const { data: survey, isLoading, isError, refetch } = useSurvey(surveyId);
  const { data: files, isLoading: filesLoading } = useSurveyFiles(surveyId);
  const uploadFile = useUploadFile(surveyId);
  const deleteFile = useDeleteFile(surveyId);
  const deleteSurvey = useDeleteSurvey();
  const push = useToastStore((s) => s.push);

  const [confirmingDelete, setConfirmingDelete] = useState(false);
  // Which row is mid-delete, so only that card shows a spinner rather than all
  // of them sharing the mutation's single isPending flag.
  const [removingFileId, setRemovingFileId] = useState<string | null>(null);

  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [depth, setDepth] = useState("");
  const [heading, setHeading] = useState("");
  const [range, setRange] = useState("");

  async function handleFiles(selected: File[]) {
    const metadata: Record<string, number> = {};
    if (latitude) metadata.latitude = Number(latitude);
    if (longitude) metadata.longitude = Number(longitude);
    if (depth) metadata.depth = Number(depth);
    if (heading) metadata.heading = Number(heading);
    if (range) metadata.range = Number(range);

    for (const file of selected) {
      try {
        await uploadFile.mutateAsync({ file, metadata: Object.keys(metadata).length ? metadata : undefined });
      } catch {
        push(`Failed to upload ${file.name}.`, "error");
      }
    }
    push("Upload complete.", "success");
  }

  async function handleRemoveFile(fileId: string) {
    const name = files?.find((f) => f.id === fileId)?.filename ?? "File";
    setRemovingFileId(fileId);
    try {
      await deleteFile.mutateAsync(fileId);
      push(`${name} removed.`, "success");
    } catch (error) {
      // The backend refuses with 409 while a job is running, and its message
      // explains what to do about it. Surface that rather than a generic
      // failure, which would leave the operator retrying a click that cannot
      // work until the job finishes.
      const message =
        error instanceof ApiError ? error.message : `Could not remove ${name}.`;
      push(message, "error");
    } finally {
      setRemovingFileId(null);
    }
  }

  if (isLoading) {
    return (
      <AppShell title="Survey">
        <LoadingSkeleton rows={4} label="Loading survey…" />
      </AppShell>
    );
  }

  if (isError || !survey) {
    return (
      <AppShell title="Survey">
        <ErrorState message="Unable to load survey." onRetry={() => refetch()} />
      </AppShell>
    );
  }

  return (
    <AppShell title={survey.name}>
      <div className="space-y-6">
        <section className="flex flex-wrap items-center justify-between gap-4 panel p-4">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold text-slate-100">{survey.name}</h2>
              <SurveyStatusBadge status={survey.status} />
            </div>
            <p className="mt-1 text-sm text-slate-400">
              {survey.source ?? "No source"} · {survey.sonar_type ?? "Unknown sonar type"}
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => router.push(`/app/surveys/${surveyId}/process`)}
              className="rounded-md bg-cyan-accent px-4 py-2 text-sm font-medium text-abyss-950 hover:bg-cyan-accent/90"
            >
              Start / Continue Processing
            </button>
            <Link
              href={`/app/detections?survey_id=${surveyId}`}
              className="rounded-md border border-abyss-600 px-4 py-2 text-sm text-slate-200 hover:border-cyan-accent/50 hover:text-cyan-accent"
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
              onClick={() => setConfirmingDelete(true)}
              className="rounded-md border border-abyss-700 px-4 py-2 text-sm text-slate-400 hover:border-alert-critical/60 hover:text-alert-critical"
            >
              Delete Survey
            </button>
          </div>
        </section>

        {confirmingDelete && (
          <DeleteSurveyDialog
            survey={survey}
            pending={deleteSurvey.isPending}
            onCancel={() => setConfirmingDelete(false)}
            onConfirm={async () => {
              try {
                await deleteSurvey.mutateAsync(surveyId);
                push(`Deleted "${survey.name}".`, "success");
                // Replace, not push: the survey behind this entry is gone, so
                // Back must not land on a page that 404s.
                router.replace("/app/surveys");
              } catch {
                push("Unable to delete this survey.", "error");
                setConfirmingDelete(false);
              }
            }}
          />
        )}

        <section className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <SummaryStat label="Files" value={survey.file_count} />
          <SummaryStat label="Validated" value={survey.processed_count} />
          <SummaryStat label="Detections" value={survey.detection_count} />
          <SummaryStat label="Needs Review" value={survey.review_count ?? 0} />
        </section>

        <section className="panel p-4">
          <h3 className="mb-3 text-sm font-semibold text-slate-200">Upload SSS Data</h3>
          <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-5">
            <MetaInput label="Latitude" value={latitude} onChange={setLatitude} />
            <MetaInput label="Longitude" value={longitude} onChange={setLongitude} />
            <MetaInput label="Depth (m)" value={depth} onChange={setDepth} />
            <MetaInput label="Heading (°)" value={heading} onChange={setHeading} />
            <MetaInput label="Sonar Range (m)" value={range} onChange={setRange} />
          </div>
          <p className="mb-3 text-xs text-slate-500">
            Optional metadata applied to files uploaded below. Leave blank if unavailable — coordinates are never
            invented. Sonar range (per-side scan width) drives the map&apos;s coverage-corridor overlay.
          </p>
          <UploadDropzone onFilesSelected={handleFiles} accept=".xtf,.jsf,.tif,.tiff,.png,.jpg,.jpeg" />
        </section>

        <section className="panel p-4">
          <h3 className="mb-3 text-sm font-semibold text-slate-200">Files</h3>
          {filesLoading ? (
            <LoadingSkeleton rows={3} />
          ) : !files || files.length === 0 ? (
            <EmptyState title="No survey files uploaded." description="Drag files into the upload area above." />
          ) : (
            <>
              <ValidationStrip files={files} />
              <div className="space-y-2">
                {files.map((file) => (
                  <FileValidationCard
                    key={file.id}
                    file={file}
                    onRemove={handleRemoveFile}
                    removing={removingFileId === file.id}
                  />
                ))}
              </div>
            </>
          )}
        </section>
      </div>
    </AppShell>
  );
}

/** Confirmation for an action with no undo.
 *
 * Deleting a survey cascades away its files, frames, detections and the review
 * decisions made on them. A yes/no dialog is too easy to click through for
 * that, so the survey's name has to be typed -- the same gesture a repository
 * host asks for, and for the same reason: it forces the operator to read which
 * survey they are about to erase. */
function DeleteSurveyDialog({
  survey,
  pending,
  onCancel,
  onConfirm,
}: {
  survey: { name: string; detection_count: number; file_count: number };
  pending: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const [typed, setTyped] = useState("");
  const matches = typed.trim() === survey.name;

  return (
    <section className="panel border border-alert-critical/40 p-5">
      <h3 className="text-sm font-semibold text-alert-critical">Delete this survey?</h3>
      <p className="mt-2 text-sm text-slate-300">
        This permanently removes {survey.file_count} uploaded file
        {survey.file_count === 1 ? "" : "s"}, every decoded frame, {survey.detection_count} detection
        {survey.detection_count === 1 ? "" : "s"} and the review decisions recorded against them, plus any
        reports generated from this survey. It cannot be undone.
      </p>
      <label className="mt-4 block text-xs text-slate-500">
        Type <span className="font-mono text-slate-300">{survey.name}</span> to confirm
      </label>
      <input
        autoFocus
        value={typed}
        onChange={(e) => setTyped(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && matches && !pending) onConfirm();
          if (e.key === "Escape") onCancel();
        }}
        className="mt-1 w-full max-w-md rounded-md border border-abyss-600 bg-abyss-900 px-3 py-2 text-sm text-slate-100 outline-none focus:border-alert-critical"
      />
      <div className="mt-4 flex gap-2">
        <button
          onClick={onConfirm}
          disabled={!matches || pending}
          className="rounded-md bg-alert-critical px-4 py-2 text-sm font-medium text-abyss-950 disabled:opacity-40"
        >
          {pending ? "Deleting…" : "Delete permanently"}
        </button>
        <button
          onClick={onCancel}
          disabled={pending}
          className="rounded-md border border-abyss-600 px-4 py-2 text-sm text-slate-300 hover:text-slate-100"
        >
          Cancel
        </button>
      </div>
    </section>
  );
}

function SummaryStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="panel p-4 text-center">
      <p className="text-2xl font-semibold text-slate-100">{value}</p>
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
    </div>
  );
}

/* Shape first, colour second. These ticks were three same-sized dots separated
 * by hue alone, with the status only in a `title` attribute -- a mouse-only
 * tooltip, so keyboard and touch users had nothing, and anyone who cannot
 * separate the hues had nothing either. A filled square, a hollow square and a
 * dash now say it before the colour does. */
const TICK_SHAPE: Record<string, string> = {
  VALID: "bg-emerald-500",
  INVALID: "border-2 border-alert-critical bg-transparent",
  PENDING: "h-[3px] self-center bg-ink-4",
};

/** At-a-glance overall status before scanning the full per-file list below -
 * one tick per file, colored by its actual validation_status. */
function ValidationStrip({ files }: { files: SurveyFile[] }) {
  const validCount = files.filter((f) => f.validation_status === "VALID").length;
  return (
    <div className="mb-3 flex items-center gap-2">
      <div className="flex flex-wrap gap-1">
        {files.map((f) => (
          <span
            key={f.id}
            title={`${f.filename}: ${f.validation_status}`}
            aria-label={`${f.filename}: ${f.validation_status}`}
            className={clsx("h-2 w-2", TICK_SHAPE[f.validation_status] ?? TICK_SHAPE.PENDING)}
          />
        ))}
      </div>
      <span className="text-xs text-slate-500">
        {validCount} / {files.length} validated
      </span>
    </div>
  );
}

function MetaInput({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <label className="mb-1 block text-xs text-slate-500">{label}</label>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        type="number"
        step="any"
        className="w-full rounded-md border border-abyss-600 bg-abyss-800 px-2 py-1.5 text-sm text-slate-100 outline-none focus:border-cyan-accent focus:shadow-glow-cyan"
      />
    </div>
  );
}
