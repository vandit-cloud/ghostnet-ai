"use client";

import { useState } from "react";
import clsx from "clsx";

import type { SurveyFile } from "@/types";
import { formatBytes } from "@/utils/format";

const STATUS_STYLES: Record<string, string> = {
  VALID: "text-emerald-300",
  INVALID: "text-alert-critical",
  PENDING: "text-slate-400",
};

/**
 * One uploaded file, with an X to take it back off the survey.
 *
 * The remove control is two-step rather than immediate. A single click on an X
 * sitting beside a filename is far too easy to land by accident, and this is
 * not an undoable action -- the file's frames and detections cascade away with
 * it. The second step also earns the room to say so, which a bare X cannot.
 *
 * It is NOT a modal, though. The survey-level delete uses one (with a typed
 * name) because it destroys everything; removing a mis-dragged file before it
 * has been processed is the ordinary case here and does not deserve the same
 * ceremony. The confirm expands in place, in the row it belongs to, so it is
 * obvious WHICH file is about to go -- the thing a centred dialog listing a
 * filename actually makes harder.
 */
export function FileValidationCard({
  file,
  onRemove,
  removing = false,
}: {
  file: SurveyFile;
  onRemove?: (fileId: string) => void;
  removing?: boolean;
}) {
  const [confirming, setConfirming] = useState(false);

  return (
    <div className="panel px-4 py-3">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-slate-200">{file.filename}</p>
          <p className="font-mono text-xs text-slate-500">
            {file.format.toUpperCase()} · {formatBytes(file.size)}
          </p>
          {file.validation_message && (
            <p className="mt-1 text-xs text-alert-critical">{file.validation_message}</p>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-3">
          <div className="text-right text-xs">
            <p className={clsx("font-medium", STATUS_STYLES[file.validation_status])}>
              File: {file.validation_status}
            </p>
            <p className={clsx("font-medium", STATUS_STYLES[file.metadata_status])}>
              Metadata: {file.metadata_status}
            </p>
          </div>

          {onRemove && !confirming && (
            <button
              type="button"
              onClick={() => setConfirming(true)}
              disabled={removing}
              aria-label={`Remove ${file.filename} from this survey`}
              title="Remove this file from the survey"
              className="flex h-7 w-7 items-center justify-center rounded-md border border-abyss-600 text-slate-400 transition hover:border-alert-critical hover:text-alert-critical disabled:opacity-50"
            >
              {removing ? (
                <svg className="h-3.5 w-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
                  <path className="opacity-80" d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
                </svg>
              ) : (
                <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path
                    d="M6 6l12 12M18 6L6 18"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                  />
                </svg>
              )}
            </button>
          )}
        </div>
      </div>

      {confirming && (
        <div className="mt-3 border-t border-abyss-700 pt-3">
          <p className="text-xs text-slate-400">
            Remove <span className="font-medium text-slate-300">{file.filename}</span> from
            this survey? Every frame and detection produced from this file is removed with
            it. Other files in the survey are not affected.
          </p>
          <div className="mt-2 flex items-center gap-2">
            <button
              type="button"
              onClick={() => {
                setConfirming(false);
                onRemove?.(file.id);
              }}
              disabled={removing}
              className="rounded-md border border-alert-critical px-3 py-1.5 text-xs font-medium text-alert-critical transition hover:bg-alert-critical/10 disabled:opacity-50"
            >
              {removing ? "Removing…" : "Remove file"}
            </button>
            <button
              type="button"
              onClick={() => setConfirming(false)}
              disabled={removing}
              className="rounded-md border border-abyss-600 px-3 py-1.5 text-xs text-slate-300 transition hover:border-cyan-accent/50 hover:text-cyan-accent disabled:opacity-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
