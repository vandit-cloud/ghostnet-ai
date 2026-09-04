"use client";

import Link from "next/link";

import { AppShell } from "@/components/AppShell";
import { JobStatusBadge } from "@/components/Badges";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/States";
import { useRecentJobs } from "@/features/system/hooks";
import { useSurveys } from "@/features/surveys/hooks";
import type { ProcessingJob } from "@/types";

function surveyName(surveys: { id: string; name: string }[] | undefined, surveyId: string): string {
  return surveys?.find((s) => s.id === surveyId)?.name ?? surveyId.slice(0, 8);
}

function JobRow({ job, surveys }: { job: ProcessingJob; surveys: { id: string; name: string }[] | undefined }) {
  return (
    <Link
      href={`/app/surveys/${job.survey_id}/process`}
      className="flex items-center justify-between gap-4 panel p-4 transition hover:border-cyan-accent/40"
    >
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-slate-100">{surveyName(surveys, job.survey_id)}</p>
        <p className="mt-0.5 text-xs uppercase tracking-wide text-slate-500">{job.stage}</p>
      </div>
      <div className="flex shrink-0 items-center gap-4">
        <div className="w-32">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-abyss-700">
            <div className="h-1.5 rounded-full bg-cyan-accent transition-all" style={{ width: `${job.progress}%` }} />
          </div>
          <p className="mt-1 text-right text-xs tabular-nums text-slate-500">{job.progress}%</p>
        </div>
        <JobStatusBadge status={job.status} />
      </div>
    </Link>
  );
}

export default function LiveProcessingPage() {
  const { data: surveys } = useSurveys(1, 200);
  const { data: active, isLoading: activeLoading, isError: activeError, refetch: refetchActive } = useRecentJobs({
    activeOnly: true,
  });
  const { data: recent, isLoading: recentLoading } = useRecentJobs({ limit: 15 });

  const recentFinished = recent?.filter((j) => !active?.some((a) => a.id === j.id)) ?? [];

  return (
    <AppShell title="Live Processing">
      <section className="mb-8">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">Active Now</h2>
        {activeLoading ? (
          <LoadingSkeleton rows={2} label="Checking for active processing jobs…" />
        ) : activeError ? (
          <ErrorState message="Unable to load active jobs." onRetry={() => refetchActive()} />
        ) : !active || active.length === 0 ? (
          <EmptyState
            title="No survey is currently processing."
            description="Start processing from a survey's detail page to see live pipeline stages here."
            action={
              <Link href="/app/surveys" className="mt-2 text-sm text-cyan-accent hover:underline">
                Go to Surveys
              </Link>
            }
          />
        ) : (
          <div className="space-y-3">
            {active.map((job) => (
              <JobRow key={job.id} job={job} surveys={surveys?.items} />
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">Recent Jobs</h2>
        {recentLoading ? (
          <LoadingSkeleton rows={3} />
        ) : recentFinished.length === 0 ? (
          <p className="text-sm text-slate-500">No completed processing jobs yet.</p>
        ) : (
          <div className="space-y-3">
            {recentFinished.map((job) => (
              <JobRow key={job.id} job={job} surveys={surveys?.items} />
            ))}
          </div>
        )}
      </section>
    </AppShell>
  );
}
