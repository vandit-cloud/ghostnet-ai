"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/api/client";
import type { SurveyMap } from "@/types";

export interface MapFilters {
  detection_class?: string;
  priority?: string;
  review_status?: string;
}

export function useSurveyMap(surveyId: string | undefined, filters: MapFilters = {}) {
  const params = new URLSearchParams();
  if (filters.detection_class) params.set("detection_class", filters.detection_class);
  if (filters.priority) params.set("priority", filters.priority);
  if (filters.review_status) params.set("review_status", filters.review_status);

  return useQuery({
    queryKey: ["survey-map", surveyId, filters],
    queryFn: () => apiFetch<SurveyMap>(`/maps/surveys/${surveyId}/detections?${params.toString()}`),
    enabled: Boolean(surveyId),
  });
}
