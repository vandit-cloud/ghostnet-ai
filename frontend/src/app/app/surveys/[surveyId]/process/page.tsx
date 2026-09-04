"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ProcessingProgress } from "@/components/ProcessingProgress";
import { StatusIndicator } from "@/components/StatusIndicator";
import { ErrorState, LoadingSkeleton } from "@/components/States";
import { useToastStore } from "@/components/Toast";
import { useActiveJob, useCancelJob, useJob, useStartProcessing } from "@/features/processing/hooks";
import { useSurvey } from "@/features/surveys/hooks";
import { useSurveyRealtime } from "@/hooks/useRealtime";

export default function ProcessingPage() {
  const params = useParams<{ surveyId: string }>();
  const surveyId = params.surveyId;

  const { data: survey } = useSurvey(surveyId);
  const { data: activeJob, isLoading: activeJobLoading, refetch } = useActiveJob(surveyId);
  const { data: job } = useJob(activeJob?.id);
  const startProcessing = useStartProcessing(surveyId);
  const cancelJob = useCancelJob(surveyId);
  const push = useToastStore((s) => s.push);
  const connectionStatus = useSurveyRealtime(surveyId);

  const displayedJob = job ?? activeJob;

  async function handleStart() {
    try {
      await startProcessing.mutateAsync();
    } catch {
      push("Unable to start processing.", "error");
    }
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
        {activeJobLoading ? (
          <LoadingSkeleton rows={3} label="Restoring processing status…" />
        ) : !displayedJob ? (
          <div className="flex flex-col items-center gap-4 py-10 text-center">
            <p className="text-slate-300">No processing job is running for this survey.</p>
            <button
              onClick={handleStart}
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
            <ProcessingProgress job={displayedJob} />
            {["QUEUED", "VALIDATING", "PROCESSING"].includes(displayedJob.status) && (
              <div className="mt-6 flex justify-end">
                <button
                  onClick={() => cancelJob.mutate(displayedJob.id)}
                  disabled={cancelJob.isPending}
                  className="rounded-md border border-alert-critical/50 px-4 py-1.5 text-sm text-alert-critical hover:bg-alert-critical/10"
                >
                  Cancel Processing
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </AppShell>
  );
}
