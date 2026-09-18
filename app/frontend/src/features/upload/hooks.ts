"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/api/client";
import type { SurveyFile } from "@/types";

export function useSurveyFiles(surveyId: string | undefined) {
  return useQuery({
    queryKey: ["survey-files", surveyId],
    queryFn: () => apiFetch<SurveyFile[]>(`/surveys/${surveyId}/files`),
    enabled: Boolean(surveyId),
  });
}

export function useUploadFile(surveyId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ file, metadata }: { file: File; metadata?: Record<string, unknown> }) => {
      const form = new FormData();
      form.append("file", file);
      if (metadata) form.append("metadata", JSON.stringify(metadata));
      return apiFetch<SurveyFile>(`/surveys/${surveyId}/files`, { method: "POST", body: form });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["survey-files", surveyId] });
      queryClient.invalidateQueries({ queryKey: ["survey", surveyId] });
    },
  });
}

export function useDeleteFile(surveyId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (fileId: string) =>
      apiFetch<void>(`/surveys/${surveyId}/files/${fileId}`, { method: "DELETE" }),
    onSuccess: () => {
      // The same two as upload, plus detections: removing a processed file
      // cascades its detections away, so a stale list would keep showing rows
      // whose detail pages now 404.
      queryClient.invalidateQueries({ queryKey: ["survey-files", surveyId] });
      queryClient.invalidateQueries({ queryKey: ["survey", surveyId] });
      queryClient.invalidateQueries({ queryKey: ["detections"] });
    },
  });
}
