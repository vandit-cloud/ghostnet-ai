"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/api/client";
import type { Page, Survey } from "@/types";

export function useSurveys(page = 1, pageSize = 20) {
  return useQuery({
    queryKey: ["surveys", page, pageSize],
    queryFn: () => apiFetch<Page<Survey>>(`/surveys?page=${page}&page_size=${pageSize}`),
  });
}

export function useSurvey(surveyId: string | undefined) {
  return useQuery({
    queryKey: ["survey", surveyId],
    queryFn: () => apiFetch<Survey>(`/surveys/${surveyId}`),
    enabled: Boolean(surveyId),
  });
}

export function useCreateSurvey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { name: string; source?: string; sonar_type?: string }) =>
      apiFetch<Survey>("/surveys", { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["surveys"] });
    },
  });
}

export function useUpdateSurvey(surveyId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<Pick<Survey, "name" | "source" | "sonar_type" | "status">>) =>
      apiFetch<Survey>(`/surveys/${surveyId}`, { method: "PATCH", body: JSON.stringify(payload) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["survey", surveyId] });
      queryClient.invalidateQueries({ queryKey: ["surveys"] });
    },
  });
}

/** Erase a survey and everything derived from it.
 *
 * A hard delete: the backend leans on the ondelete=CASCADE already declared on
 * every child table, so files, frames, detections, jobs, reports and the review
 * decisions hanging off those detections all go. There was no DELETE route in
 * the API at all before this (A4 in docs/KNOWN_ISSUES.md), so a mistaken upload
 * was permanent through the UI and cleanup meant raw SQL. The caller is
 * responsible for confirming first -- there is no undo. */
export function useDeleteSurvey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (surveyId: string) => apiFetch<void>(`/surveys/${surveyId}`, { method: "DELETE" }),
    onSuccess: (_data, surveyId) => {
      // Drop this survey's own caches rather than leave them to go stale --
      // every one of them now points at rows that no longer exist.
      queryClient.removeQueries({ queryKey: ["survey", surveyId] });
      queryClient.removeQueries({ queryKey: ["latest-job", surveyId] });
      queryClient.removeQueries({ queryKey: ["active-job", surveyId] });
      queryClient.removeQueries({ queryKey: ["survey-map", surveyId] });
      queryClient.invalidateQueries({ queryKey: ["surveys"] });
      queryClient.invalidateQueries({ queryKey: ["detections"] });
      queryClient.invalidateQueries({ queryKey: ["reports"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
    },
  });
}
