"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/api/client";
import type { Detection, DetectionReview, Page, ReviewStatus } from "@/types";

export interface DetectionFilters {
  survey_id?: string;
  detection_class?: string;
  min_confidence?: number;
  priority?: string;
  review_status?: string;
  page?: number;
  page_size?: number;
}

function buildQuery(filters: DetectionFilters): string {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== "" && value !== null) {
      params.set(key, String(value));
    }
  });
  return params.toString();
}

export function useDetections(filters: DetectionFilters) {
  const query = buildQuery({ page: 1, page_size: 50, ...filters });
  return useQuery({
    queryKey: ["detections", filters],
    queryFn: () => apiFetch<Page<Detection>>(`/detections?${query}`),
  });
}

export function useDetection(detectionId: string | undefined) {
  return useQuery({
    queryKey: ["detection", detectionId],
    queryFn: () => apiFetch<Detection>(`/detections/${detectionId}`),
    enabled: Boolean(detectionId),
  });
}

export function useDetectionReviews(detectionId: string | undefined) {
  return useQuery({
    queryKey: ["detection-reviews", detectionId],
    queryFn: () => apiFetch<DetectionReview[]>(`/detections/${detectionId}/reviews`),
    enabled: Boolean(detectionId),
  });
}

export function useReviewDetection(detectionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    // No `reviewer`: the backend records the authenticated user from the token.
    mutationFn: (payload: { decision: ReviewStatus; note?: string }) =>
      apiFetch<DetectionReview>(`/detections/${detectionId}/review`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["detection", detectionId] });
      queryClient.invalidateQueries({ queryKey: ["detection-reviews", detectionId] });
      queryClient.invalidateQueries({ queryKey: ["detections"] });
    },
  });
}
