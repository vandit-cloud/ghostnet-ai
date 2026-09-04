"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";

import { EmptyState, LoadingSkeleton } from "@/components/States";
import type { Scene3DDetection } from "@/components/three/Scene3D";
import { computeBounds, projectLatLon } from "@/components/three/utils/geo3d";
import { useSurveyMap } from "@/features/map/hooks";
import { usePageVisible } from "@/hooks/usePageVisible";
import { useReducedMotion } from "@/hooks/useReducedMotion";
import type { JobStatus, SurveyStatus } from "@/types";

const Scene3D = dynamic(() => import("@/components/three/Scene3D").then((m) => m.Scene3D), {
  ssr: false,
  loading: () => <LoadingSkeleton rows={1} label="Loading 3D survey view…" />,
});

const REPLAY_STEP_MS = 450;

export function SurveyHero({
  surveyId,
  surveyStatus,
  activeJobStatus,
}: {
  surveyId: string;
  surveyStatus: SurveyStatus;
  activeJobStatus: JobStatus | null;
}) {
  const { data, isLoading } = useSurveyMap(surveyId);
  const reducedMotion = useReducedMotion();
  const pageVisible = usePageVisible();
  const paused = reducedMotion || !pageVisible;

  const [cameraMode, setCameraMode] = useState<"follow" | "free">("free");
  const [fitRequestId, setFitRequestId] = useState(0);
  const [selectedId, setSelectedId] = useState<string | undefined>(undefined);
  const [replayIndex, setReplayIndex] = useState<number | null>(null);
  const replayTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  const projected = useMemo(() => {
    if (!data) return null;
    const originPoint = data.track[0] ?? data.markers[0];
    if (!originPoint) return null;
    const originLat = originPoint.latitude;
    const originLon = originPoint.longitude;

    const track = data.track.map((p) => ({
      ...projectLatLon(originLat, originLon, p.latitude, p.longitude),
      range: p.range,
    }));
    const detections: Scene3DDetection[] = data.markers.map((m) => {
      const { x, z } = projectLatLon(originLat, originLon, m.latitude, m.longitude);
      return { id: m.detection_id, x, z, detectionClass: m.detection_class, priority: m.priority };
    });
    const bounds = computeBounds([...track, ...detections.map((d) => ({ x: d.x, z: d.z }))]);
    return { track, detections, bounds };
  }, [data]);

  const canReplay = surveyStatus === "COMPLETED" && (projected?.track.length ?? 0) >= 2;

  useEffect(() => {
    return () => {
      if (replayTimer.current) clearInterval(replayTimer.current);
    };
  }, []);

  function startReplay() {
    if (!projected || projected.track.length < 2) return;
    if (replayTimer.current) clearInterval(replayTimer.current);
    setReplayIndex(0);
    replayTimer.current = setInterval(() => {
      setReplayIndex((i) => {
        if (i === null) return null;
        const next = i + 1;
        if (next >= projected.track.length) {
          if (replayTimer.current) clearInterval(replayTimer.current);
          return null;
        }
        return next;
      });
    }, REPLAY_STEP_MS);
  }

  if (isLoading) {
    return (
      <div className="flex h-[520px] items-center justify-center rounded-lg border border-abyss-600 bg-abyss-900/60">
        <LoadingSkeleton rows={1} label="Loading survey view…" />
      </div>
    );
  }

  if (!projected || projected.track.length === 0) {
    return (
      <div className="flex h-[520px] items-center justify-center rounded-lg border border-abyss-600 bg-abyss-900/60">
        <EmptyState title="No track data for this survey." description="Upload geotagged sonar frames to see the 3D survey view." />
      </div>
    );
  }

  const displayTrack = replayIndex !== null ? projected.track.slice(0, replayIndex + 1) : projected.track;
  const vesselPoint = displayTrack[displayTrack.length - 1] ?? projected.track[projected.track.length - 1];
  const prevPoint = displayTrack.length > 1 ? displayTrack[displayTrack.length - 2] : vesselPoint;
  const headingDeg =
    vesselPoint === prevPoint ? 0 : (Math.atan2(vesselPoint.x - prevPoint.x, vesselPoint.z - prevPoint.z) * 180) / Math.PI;

  const sonarActive = activeJobStatus === "PROCESSING" || replayIndex !== null;

  return (
    <div className="relative h-[520px] overflow-hidden rounded-lg border border-abyss-600 bg-abyss-900/60">
      <Scene3D
        track={displayTrack}
        detections={projected.detections}
        vessel={{ x: vesselPoint.x, z: vesselPoint.z, headingDeg }}
        bounds={projected.bounds}
        sonarActive={sonarActive}
        selectedId={selectedId}
        onSelectDetection={setSelectedId}
        cameraMode={cameraMode}
        fitRequestId={fitRequestId}
        paused={paused}
      />

      <div className="pointer-events-none absolute inset-x-0 top-0 flex items-center justify-between p-3">
        <span className="pointer-events-auto rounded-md border border-abyss-600 bg-abyss-900/80 px-2.5 py-1 text-xs text-slate-400">
          {projected.track.length} track points · {projected.detections.length} detections
        </span>
      </div>

      <div className="pointer-events-none absolute inset-x-0 bottom-0 flex items-center gap-2 p-3">
        <button
          onClick={() => setFitRequestId((n) => n + 1)}
          className="pointer-events-auto rounded-md border border-abyss-600 bg-abyss-900/85 px-3 py-1.5 text-xs text-slate-200 hover:border-cyan-accent/50 hover:text-cyan-accent"
        >
          Fit Survey
        </button>
        <button
          onClick={() => setCameraMode((m) => (m === "follow" ? "free" : "follow"))}
          className={`pointer-events-auto rounded-md border px-3 py-1.5 text-xs ${
            cameraMode === "follow"
              ? "border-cyan-accent/50 bg-cyan-accent/10 text-cyan-accent"
              : "border-abyss-600 bg-abyss-900/85 text-slate-200 hover:border-cyan-accent/50 hover:text-cyan-accent"
          }`}
        >
          Follow Vessel
        </button>
        {canReplay && (
          <button
            onClick={startReplay}
            disabled={replayIndex !== null}
            className="pointer-events-auto rounded-md border border-abyss-600 bg-abyss-900/85 px-3 py-1.5 text-xs text-slate-200 hover:border-cyan-accent/50 hover:text-cyan-accent disabled:opacity-50"
          >
            {replayIndex !== null ? "Replaying…" : "Replay Survey"}
          </button>
        )}
      </div>
    </div>
  );
}
