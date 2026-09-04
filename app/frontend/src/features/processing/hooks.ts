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
    mutationFn: () => apiFetch<ProcessingJob>(`/surveys/${surveyId}/process`, { method: "POST", body: "{}" }),
    onSuccess: (job) => {
      queryClient.setQueryData(["active-job", surveyId], job);
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
    },
  });
}
