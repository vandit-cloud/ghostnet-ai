"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/api/client";
import type { ProcessingJob, SystemStatus } from "@/types";

export function useSystemStatus() {
  return useQuery({
    queryKey: ["system-status"],
    queryFn: () => apiFetch<SystemStatus>("/system/status"),
    refetchInterval: 10_000,
  });
}

export interface SystemConfig {
  app_name: string;
  max_upload_size_mb: number;
  allowed_upload_extensions: string[];
}

export function useSystemConfig() {
  return useQuery({
    queryKey: ["system-config"],
    queryFn: () => apiFetch<SystemConfig>("/system/config"),
    staleTime: 5 * 60_000,
  });
}

export function useRecentJobs(opts: { activeOnly?: boolean; limit?: number } = {}) {
  const { activeOnly = false, limit = 50 } = opts;
  return useQuery({
    queryKey: ["jobs", { activeOnly, limit }],
    queryFn: () => apiFetch<ProcessingJob[]>(`/jobs?active_only=${activeOnly}&limit=${limit}`),
    refetchInterval: activeOnly ? 4_000 : 30_000,
  });
}
