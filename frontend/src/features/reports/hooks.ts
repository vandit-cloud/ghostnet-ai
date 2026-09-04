"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetchBlob, apiFetch } from "@/api/client";
import type { Report, ReportFormat, ReportType } from "@/types";

export function useReports(surveyId?: string) {
  return useQuery({
    queryKey: ["reports", surveyId],
    queryFn: () => apiFetch<Report[]>(`/reports${surveyId ? `?survey_id=${surveyId}` : ""}`),
  });
}

export function useReport(reportId: string | undefined) {
  return useQuery({
    queryKey: ["report", reportId],
    queryFn: () => apiFetch<Report>(`/reports/${reportId}`),
    enabled: Boolean(reportId),
    refetchInterval: (query) => {
      const data = query.state.data as Report | undefined;
      return data && (data.status === "QUEUED" || data.status === "PROCESSING") ? 1500 : false;
    },
  });
}

export function useCreateReport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      survey_id: string;
      type: ReportType;
      format: ReportFormat;
      filters?: Record<string, unknown>;
      detection_id?: string;
    }) => apiFetch<Report>("/reports", { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reports"] });
    },
  });
}

export async function downloadReport(reportId: string, filename: string) {
  const blob = await apiFetchBlob(`/reports/${reportId}/download`);
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
