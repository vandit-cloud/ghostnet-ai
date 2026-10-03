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
      // A new file brings new frames. The processing page caches the frame
      // list for minutes on the assumption it never changes, which let it map
      // a fresh run onto the old frames and judge the last run still current.
      queryClient.invalidateQueries({ queryKey: ["survey-frames", surveyId] });
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
      /* And the map, which is a SEPARATE cache keyed ["survey-map", id,
       * filters] and fed by its own endpoint. The GIS Map page and the
       * dashboard survey panel both render from it, so without this a deleted
       * file's track points and detection markers stay on screen until those
       * components remount -- the one place a stale cache is not just a stale
       * list but a map asserting gear is at a position that no longer has any
       * evidence behind it. `useDeleteSurvey` already clears this key; the
       * per-file delete was written before the map moved onto it. */
      queryClient.invalidateQueries({ queryKey: ["survey-map", surveyId] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
      // Its frames go with it -- see useUploadFile.
      queryClient.invalidateQueries({ queryKey: ["survey-frames", surveyId] });
    },
  });
}
