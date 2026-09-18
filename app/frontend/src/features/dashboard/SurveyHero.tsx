"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";

import { MapLegend } from "@/components/MapLegend";
import { EmptyState, LoadingSkeleton } from "@/components/States";
import { useSurveyMap } from "@/features/map/hooks";
import { bearingDeg } from "@/utils/geo";
import {
  MAP_SLOT_BOTTOM_LEFT,
  MAP_SLOT_BOTTOM_RIGHT,
  MAP_SLOT_TOP_LEFT,
} from "@/utils/mapSlots";
import type { JobStatus, SurveyStatus } from "@/types";

/** Leaflet touches `window` at import time, so the map can never be part of the
 *  server bundle -- same dynamic import the GIS Map page uses. */
const MapView = dynamic(() => import("@/components/MapView").then((m) => m.MapView), {
  ssr: false,
  loading: () => <LoadingSkeleton rows={1} label="Loading map…" />,
});

const REPLAY_STEP_MS = 450;

export function SurveyHero({
  surveyId,
  surveyStatus,
}: {
  surveyId: string;
  surveyStatus: SurveyStatus;
  /** Still accepted so the dashboard's call site is untouched. It drove the
   *  sonar sweep in the old 3D scene and has no 2D equivalent; the processing
   *  state is already surfaced by the dashboard's own status cards. */
  activeJobStatus?: JobStatus | null;
}) {
  const { data, isLoading } = useSurveyMap(surveyId);

  const [selectedId, setSelectedId] = useState<string | undefined>(undefined);
  const [replayIndex, setReplayIndex] = useState<number | null>(null);
  const replayTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  /* Memoised because `?? []` builds a NEW array every render, which would give
   * `displayedTrack` below a changing dependency each time and defeat its own
   * memo -- and, through it, `vesselDuringReplay`. */
  const track = useMemo(() => data?.track ?? [], [data]);
  const markers = useMemo(() => data?.markers ?? [], [data]);
  const canReplay = surveyStatus === "COMPLETED" && track.length >= 2;

  useEffect(() => {
    return () => {
      if (replayTimer.current) clearInterval(replayTimer.current);
    };
  }, []);

  // A survey switch while a replay is running would otherwise keep stepping an
  // index into a track that no longer exists.
  useEffect(() => {
    if (replayTimer.current) clearInterval(replayTimer.current);
    setReplayIndex(null);
  }, [surveyId]);

  const displayedTrack = useMemo(
    () => (replayIndex !== null ? track.slice(0, replayIndex + 1) : track),
    [track, replayIndex]
  );

  /** Only during replay: the live vessel marker. Outside replay the whole
   *  track is drawn and there is no "current" position to show. */
  const vesselDuringReplay = useMemo(() => {
    if (replayIndex === null || displayedTrack.length === 0) return null;
    const last = displayedTrack[displayedTrack.length - 1];
    const prev = displayedTrack.length > 1 ? displayedTrack[displayedTrack.length - 2] : last;
    const headingDeg =
      last === prev ? 0 : bearingDeg(prev.latitude, prev.longitude, last.latitude, last.longitude);
    return { latitude: last.latitude, longitude: last.longitude, headingDeg };
  }, [replayIndex, displayedTrack]);

  function startReplay() {
    if (track.length < 2) return;
    if (replayTimer.current) clearInterval(replayTimer.current);
    setReplayIndex(0);
    replayTimer.current = setInterval(() => {
      setReplayIndex((i) => {
        if (i === null) return null;
        const next = i + 1;
        if (next >= track.length) {
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

  if (!data || (markers.length === 0 && track.length === 0)) {
    return (
      <div className="flex h-[520px] items-center justify-center border border-abyss-600 bg-abyss-900/60">
        <EmptyState
          title="Nothing to map for this survey."
          description="Upload geotagged sonar frames to see the vessel track and detections."
        />
      </div>
    );
  }

  return (
    <div className="relative h-[520px] overflow-hidden border border-abyss-600 bg-abyss-900/60">
      <MapView
        markers={markers}
        bounds={data.bounds}
        track={displayedTrack}
        selectedId={selectedId}
        onSelect={setSelectedId}
        vesselPosition={vesselDuringReplay}
      />

      {/* Positions come from utils/mapSlots -- see that file for which corner
          belongs to Leaflet, which to MapView, and which is ours. This panel
          used to put the counter at top-3 and the legend at bottom-3, directly
          over MapView's cursor read-out and Leaflet's scale bar. */}
      <div className={`pointer-events-none ${MAP_SLOT_TOP_LEFT}`}>
        <span className="pointer-events-auto border border-abyss-600/80 bg-abyss-900/85 px-3 py-1.5 font-mono text-[10.5px] uppercase tracking-[0.12em] text-slate-300">
          {track.length} track points · {markers.length} detections
        </span>
      </div>

      <div className={`pointer-events-none ${MAP_SLOT_BOTTOM_LEFT}`}>
        <div className="pointer-events-auto">
          <MapLegend />
        </div>
      </div>

      {canReplay && (
        <div className={`pointer-events-none ${MAP_SLOT_BOTTOM_RIGHT}`}>
          <button
            onClick={startReplay}
            disabled={replayIndex !== null}
            className="pointer-events-auto border border-abyss-600/80 bg-abyss-900/85 px-4 py-2 font-mono text-[10.5px] uppercase tracking-[0.18em] text-slate-200 transition hover:border-cyan-accent/50 hover:text-cyan-accent disabled:opacity-50"
          >
            {replayIndex !== null ? "Replaying…" : "Replay Survey"}
          </button>
        </div>
      )}
    </div>
  );
}
