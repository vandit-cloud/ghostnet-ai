"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";

import { HeroWaterBackdrop } from "@/components/three/HeroWaterBackdrop";
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

  // Defaults to "follow" so the panel opens on a close, cinematic shot of the
  // vessel on the water -- matching the login/hero page's presentation --
  // rather than the distant top-down survey overview "free" gives, which is
  // what "Fit Survey" is for.
  const [cameraMode, setCameraMode] = useState<"follow" | "free">("follow");
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
      <div className="flex h-[520px] items-center justify-center border border-abyss-600 bg-abyss-900/60">
        <LoadingSkeleton rows={1} label="Loading survey view…" />
      </div>
    );
  }

  if (!projected || projected.track.length === 0) {
    return (
      <div className="flex h-[520px] items-center justify-center border border-abyss-600 bg-abyss-900/60">
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
    <div className="relative h-[520px] overflow-hidden border border-abyss-600 bg-abyss-900/60">
      {/* The exact landing-page water shader (see WATER_PROMPT.md /
          HeroWaterBackdrop.tsx), composited BEHIND the real 3D vessel/data
          scene as a distant backdrop -- HeroWaterBackdrop is a fixed,
          non-interactive "ambient shot" raymarch (its own doc comment: "no
          scroll-driven dive... reads as a static ambient shot") with its own
          camera that never moves, while this panel needs a real navigable
          camera driven by survey data. Those two cameras are NOT coordinated,
          so the backdrop's horizon cannot be trusted as this vessel's actual
          waterline -- Scene3D grounds the vessel itself with its own small
          OceanSurface anchored to the vessel's real position (see Scene3D's
          comment on it); this backdrop is purely the distant sky/water it
          fades into. Only shown in follow mode: that's the close, natural-
          scale shot this backdrop's fixed camera height was tuned for;
          "Fit Survey"'s wide overview keeps its own extent-scaled ocean plane
          instead, since the backdrop's water wouldn't visually match at that
          vastly different camera distance. Scene3D renders with a transparent
          clear colour in follow mode so this shows through in the distance. */}
      {cameraMode === "follow" && <HeroWaterBackdrop />}
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
        <span className="pointer-events-auto border border-abyss-600/80 bg-abyss-900/85 px-3 py-1.5 font-mono text-[10.5px] uppercase tracking-[0.12em] text-slate-300">
          {projected.track.length} track points · {projected.detections.length} detections
        </span>
      </div>

      <div className="pointer-events-none absolute inset-x-0 bottom-0 flex flex-wrap items-center gap-2 p-3">
        <button
          onClick={() => setFitRequestId((n) => n + 1)}
          className="pointer-events-auto border border-abyss-600/80 bg-abyss-900/85 px-4 py-2 font-mono text-[10.5px] uppercase tracking-[0.18em] text-slate-200 transition hover:border-cyan-accent/50 hover:text-cyan-accent"
        >
          Fit Survey
        </button>
        <button
          onClick={() => setCameraMode((m) => (m === "follow" ? "free" : "follow"))}
          className={`pointer-events-auto border px-4 py-2 font-mono text-[10.5px] uppercase tracking-[0.18em] transition ${
            cameraMode === "follow"
              ? "border-imperial bg-imperial text-paper"
              : "border-abyss-600/80 bg-abyss-900/85 text-slate-200 hover:border-cyan-accent/50 hover:text-cyan-accent"
          }`}
        >
          Follow Vessel
        </button>
        {canReplay && (
          <button
            onClick={startReplay}
            disabled={replayIndex !== null}
            className="pointer-events-auto border border-abyss-600/80 bg-abyss-900/85 px-4 py-2 font-mono text-[10.5px] uppercase tracking-[0.18em] text-slate-200 transition hover:border-cyan-accent/50 hover:text-cyan-accent disabled:opacity-50"
          >
            {replayIndex !== null ? "Replaying…" : "Replay Survey"}
          </button>
        )}
      </div>
    </div>
  );
}
