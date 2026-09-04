import clsx from "clsx";

import type { SurveyFile } from "@/types";
import { formatBytes } from "@/utils/format";

const STATUS_STYLES: Record<string, string> = {
  VALID: "text-emerald-300",
  INVALID: "text-alert-critical",
  PENDING: "text-slate-400",
};

export function FileValidationCard({ file }: { file: SurveyFile }) {
  return (
    <div className="panel flex items-center justify-between px-4 py-3">
      <div>
        <p className="text-sm font-medium text-slate-200">{file.filename}</p>
        <p className="font-mono text-xs text-slate-500">
          {file.format.toUpperCase()} · {formatBytes(file.size)}
        </p>
        {file.validation_message && <p className="mt-1 text-xs text-alert-critical">{file.validation_message}</p>}
      </div>
      <div className="text-right text-xs">
        <p className={clsx("font-medium", STATUS_STYLES[file.validation_status])}>File: {file.validation_status}</p>
        <p className={clsx("font-medium", STATUS_STYLES[file.metadata_status])}>Metadata: {file.metadata_status}</p>
      </div>
    </div>
  );
}
