"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { WS_BASE_URL } from "@/api/client";
import { useAuthStore } from "@/state/auth-store";
import type { RealtimeEvent } from "@/types";

export type ConnectionStatus = "connecting" | "connected" | "reconnecting" | "offline";

/** Subscribes to survey realtime events (spec section 41) and invalidates the
 * relevant React Query caches so the UI updates without a full reload. On
 * disconnect it reconnects and reconciles by refetching current state rather
 * than assuming missed events (spec section 42). */
export function useSurveyRealtime(surveyId: string | undefined) {
  const queryClient = useQueryClient();
  const token = useAuthStore((s) => s.token);
  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const retryRef = useRef(0);

  useEffect(() => {
    if (!surveyId || !token) return;

    let socket: WebSocket | null = null;
    let closedByEffect = false;
    let retryTimeout: ReturnType<typeof setTimeout>;

    function connect() {
      setStatus(retryRef.current === 0 ? "connecting" : "reconnecting");
      socket = new WebSocket(`${WS_BASE_URL}/ws/surveys/${surveyId}?token=${token}`);

      socket.onopen = () => {
        retryRef.current = 0;
        setStatus("connected");
        queryClient.invalidateQueries({ queryKey: ["active-job", surveyId] });
        queryClient.invalidateQueries({ queryKey: ["survey", surveyId] });
      };

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as RealtimeEvent;
          handleEvent(payload);
        } catch {
          // ignore malformed frames
        }
      };

      socket.onclose = () => {
        if (closedByEffect) return;
        setStatus("offline");
        retryRef.current += 1;
        const delay = Math.min(1000 * retryRef.current, 8000);
        retryTimeout = setTimeout(connect, delay);
      };
    }

    function handleEvent(payload: RealtimeEvent) {
      switch (payload.event) {
        case "job.updated":
          queryClient.invalidateQueries({ queryKey: ["active-job", surveyId] });
          if (payload.job_id) {
            queryClient.invalidateQueries({ queryKey: ["job", payload.job_id] });
          }
          queryClient.invalidateQueries({ queryKey: ["survey", surveyId] });
          break;
        case "frame.processed":
          if (payload.job_id) {
            queryClient.invalidateQueries({ queryKey: ["job", payload.job_id] });
          }
          break;
        case "detection.created":
        case "detection.updated":
          queryClient.invalidateQueries({ queryKey: ["detections"] });
          queryClient.invalidateQueries({ queryKey: ["survey-map", surveyId] });
          queryClient.invalidateQueries({ queryKey: ["survey", surveyId] });
          break;
        case "report.completed":
          queryClient.invalidateQueries({ queryKey: ["reports"] });
          if (payload.report_id) {
            queryClient.invalidateQueries({ queryKey: ["report", payload.report_id] });
          }
          break;
      }
    }

    connect();

    return () => {
      closedByEffect = true;
      clearTimeout(retryTimeout);
      socket?.close();
    };
  }, [surveyId, token, queryClient]);

  return status;
}
