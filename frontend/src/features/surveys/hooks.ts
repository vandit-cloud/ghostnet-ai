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
