"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/api/client";
import type { JobStage, JobStatus, Priority, SurveyStatus } from "@/types";

export interface DashboardSummary {
  current_survey: { id: string; name: string; status: SurveyStatus; updated_at: string } | null;
  active_job: { id: string; survey_id: string; status: JobStatus; stage: JobStage; progress: number } | null;
  last_updated: string | null;
  frames_processed: number;
  candidates: number;
  confirmed_artificial: number;
  high_priority: number;
  needs_review: number;
  rejected_natural: number;
  class_distribution: { detection_class: string; count: number }[];
  detection_trend: { date: string; count: number }[];
  recent_detections: {
    id: string;
    detection_ref: string;
    detection_class: string;
    calibrated_confidence: number | null;
    priority: Priority;
    created_at: string;
  }[];
}

export function useDashboardSummary() {
  return useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: () => apiFetch<DashboardSummary>("/dashboard/summary"),
    refetchInterval: 15_000,
  });
}
