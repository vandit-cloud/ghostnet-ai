"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/api/client";
import type { ProcessingJob } from "@/types";

const ACTIVE_STATUSES: ProcessingJob["status"][] = ["QUEUED", "VALIDATING", "PROCESSING"];

export function useActiveJob(surveyId: string | undefined) {
  return useQuery({
    queryKey: ["active-job", surveyId],
    queryFn: () => apiFetch<ProcessingJob | null>(`/surveys/${surveyId}/jobs/active`),
    enabled: Boolean(surveyId),
  });
}

/** The survey's most recent job, whatever state it is in.
 *
 * The processing page reads this and nothing else. It used to read
 * `/jobs/active` for the id and `/jobs/{id}` for the detail, displaying
 * `job ?? activeJob` -- two endpoints refreshed on different triggers, so a
 * momentarily-missing `job` fell back to a staler `activeJob` and the bar
 * jumped (sampled 22 points apart mid-run). Worse, `/jobs/active` returns null
 * the moment a job leaves QUEUED|VALIDATING|PROCESSING, so on completion the
 * id was lost and the page claimed nothing had run. One endpoint, one truth.
 * See A1 and A3 in docs/KNOWN_ISSUES.md. */
export function useLatestJob(surveyId: string | undefined) {
  return useQuery({
    queryKey: ["latest-job", surveyId],
    queryFn: () => apiFetch<ProcessingJob | null>(`/surveys/${surveyId}/jobs/latest`),
    enabled: Boolean(surveyId),
    refetchInterval: (query) => {
      const data = query.state.data as ProcessingJob | null | undefined;
      return data && ACTIVE_STATUSES.includes(data.status) ? 1500 : false;
    },
    // A finished job is immutable, so never show a gap while refetching -- an
    // undefined frame here is exactly what used to make the display flicker.
    placeholderData: (previous) => previous,
  });
}

export function useJob(jobId: string | undefined) {
  return useQuery({
    queryKey: ["job", jobId],
    queryFn: () => apiFetch<ProcessingJob>(`/jobs/${jobId}`),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const data = query.state.data as ProcessingJob | undefined;
      return data && ACTIVE_STATUSES.includes(data.status) ? 1500 : false;
    },
  });
}

export function useStartProcessing(surveyId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    // force_restart is the caller's deliberate choice to discard the survey's
    // existing detections -- and the review decisions that cascade off them.
    // Never defaulted on; the UI asks first.
    mutationFn: (forceRestart: boolean) =>
      apiFetch<ProcessingJob>(`/surveys/${surveyId}/process`, {
        method: "POST",
        body: JSON.stringify({ force_restart: forceRestart }),
      }),
    onSuccess: (job) => {
      queryClient.setQueryData(["active-job", surveyId], job);
      queryClient.setQueryData(["latest-job", surveyId], job);
      queryClient.setQueryData(["job", job.id], job);
    },
  });
}

export function useCancelJob(surveyId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) => apiFetch<ProcessingJob>(`/jobs/${jobId}/cancel`, { method: "POST" }),
    onSuccess: (job) => {
      queryClient.setQueryData(["job", job.id], job);
      queryClient.invalidateQueries({ queryKey: ["active-job", surveyId] });
      queryClient.invalidateQueries({ queryKey: ["latest-job", surveyId] });
    },
  });
}
