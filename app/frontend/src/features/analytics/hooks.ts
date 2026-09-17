"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/api/client";
import type { AnalyticsSummary } from "@/types";

export function useAnalyticsSummary() {
  return useQuery({
    queryKey: ["analytics-summary"],
    queryFn: () => apiFetch<AnalyticsSummary>("/analytics/summary"),
    refetchInterval: 30_000,
  });
}
