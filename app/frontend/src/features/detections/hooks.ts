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

export function useDetections(filters: DetectionFilters, options: { enabled?: boolean } = {}) {
  const query = buildQuery({ page: 1, page_size: 50, ...filters });
  return useQuery({
    queryKey: ["detections", filters],
    queryFn: () => apiFetch<Page<Detection>>(`/detections?${query}`),
    enabled: options.enabled ?? true,
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
    onSuccess: (_review, { decision }) => {
      // Write the decision into every cached detection list first. The review
      // page navigates back to the queue straight after saving, and the queue's
      // list is inactive at that moment, so invalidation alone only marks it
      // stale: the queue rendered its old list, reviewed item included, and
      // then dropped the item when the refetch landed. A list filtered to a
      // different status loses the item; any other list shows the new status.
      for (const [key, page] of queryClient.getQueriesData<Page<Detection>>({ queryKey: ["detections"] })) {
        if (!page) continue;
        const filters = (key[1] ?? {}) as DetectionFilters;
        const hit = page.items.some((d) => d.id === detectionId);
        if (!hit) continue;
        const drop = Boolean(filters.review_status) && filters.review_status !== decision;
        queryClient.setQueryData<Page<Detection>>(key, {
          ...page,
          items: drop
            ? page.items.filter((d) => d.id !== detectionId)
            : page.items.map((d) => (d.id === detectionId ? { ...d, review_status: decision } : d)),
          total: drop ? Math.max(0, page.total - 1) : page.total,
        });
      }
      // Then refresh everything that counts reviews: the dashboard tiles, the
      // survey header, the map's marker colours and the analytics page all
      // showed pre-review numbers until a hard reload. Returned so that
      // mutateAsync resolves only once the active ones have refetched.
      return Promise.all([
        queryClient.invalidateQueries({ queryKey: ["detection", detectionId] }),
        queryClient.invalidateQueries({ queryKey: ["detection-reviews", detectionId] }),
        queryClient.invalidateQueries({ queryKey: ["detections"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] }),
        queryClient.invalidateQueries({ queryKey: ["survey"] }),
        queryClient.invalidateQueries({ queryKey: ["surveys"] }),
        queryClient.invalidateQueries({ queryKey: ["survey-map"] }),
        queryClient.invalidateQueries({ queryKey: ["analytics-summary"] }),
      ]);
    },
  });
}
