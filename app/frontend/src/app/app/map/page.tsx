"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import clsx from "clsx";

import { AppShell } from "@/components/AppShell";
import { PriorityBadge, ReviewStatusBadge, UncertaintyLabel } from "@/components/Badges";
import { FilterSelect } from "@/components/FilterBar";
import { MapLegend } from "@/components/MapLegend";
import { SonarViewer } from "@/components/SonarViewer";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/States";
import { useDetection } from "@/features/detections/hooks";
import { useSurveyMap } from "@/features/map/hooks";
import { useSurveys } from "@/features/surveys/hooks";
import { bearingDeg } from "@/utils/geo";
import { formatConfidence } from "@/utils/format";

const MapView = dynamic(() => import("@/components/MapView").then((mod) => mod.MapView), {
  ssr: false,
  loading: () => <LoadingSkeleton rows={1} label="Loading map…" />,
});

const CLASS_OPTIONS = [
  { value: "ghost_net", label: "Ghost Net" },
  { value: "debris", label: "Debris" },
  { value: "natural_object", label: "Natural Object" },
  { value: "unknown", label: "Unknown" },
];

const PRIORITY_OPTIONS = [
  { value: "critical", label: "Critical" },
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
];

const REVIEW_OPTIONS = [
  { value: "pending", label: "Pending" },
  { value: "unknown", label: "Unknown" },
  { value: "accepted_artificial", label: "Accepted — Artificial" },
  { value: "rejected_natural", label: "Rejected — Natural" },
];

export default function MapPage() {
  return (
    <Suspense fallback={<AppShell title="GIS Map"><LoadingSkeleton rows={4} label="Loading map…" /></AppShell>}>
      <MapPageContent />
    </Suspense>
  );
}

function MapPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { data: surveys } = useSurveys(1, 100);

  const surveyId = searchParams.get("survey_id") ?? surveys?.items[0]?.id;
  const detectionClass = searchParams.get("detection_class") ?? undefined;
  const priority = searchParams.get("priority") ?? undefined;
  const reviewStatus = searchParams.get("review_status") ?? undefined;
  const focusId = searchParams.get("focus") ?? undefined;

  const [selectedId, setSelectedId] = useState<string | undefined>(focusId);

  function updateParam(key: string, value: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (value) params.set(key, value);
    else params.delete(key);
    router.push(`/app/map?${params.toString()}`);
  }

  const { data, isLoading, isError, refetch } = useSurveyMap(surveyId, {
    detection_class: detectionClass,
    priority,
    review_status: reviewStatus,
  });
  const { data: selectedDetection } = useDetection(selectedId);

  // --- Time playback (Section 4.1.A / 4.2.A): replays the survey path and
  // reveals detections in chronological order instead of showing everything
  // at once. null = live/full view; a number = "as of" this track index.
  const [playbackIndex, setPlaybackIndex] = useState<number | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);

  const trackLength = data?.track.length ?? 0;
  const canPlayback = trackLength >= 2;

  // Real creation order - never an invented timeline, just the same
  // detections sorted by the timestamp the backend already recorded.
  const chronologicalMarkers = useMemo(() => {
    if (!data) return [];
    return [...data.markers].sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
  }, [data]);

  useEffect(() => {
    if (!isPlaying) return;
    const timer = setInterval(() => {
      setPlaybackIndex((i) => {
        const next = (i ?? -1) + 1;
        if (next >= trackLength) {
          setIsPlaying(false);
          return trackLength - 1;
        }
        return next;
      });
    }, 600 / playbackSpeed);
    return () => clearInterval(timer);
  }, [isPlaying, playbackSpeed, trackLength]);

  function togglePlay() {
    if (!canPlayback) return;
    if (playbackIndex === null || playbackIndex >= trackLength - 1) setPlaybackIndex(0);
    setIsPlaying((p) => !p);
  }
  function stopPlayback() {
    setIsPlaying(false);
    setPlaybackIndex(null);
  }
  function scrubTo(index: number) {
    setIsPlaying(false);
    setPlaybackIndex(index);
  }

  const displayedTrack = useMemo(() => {
    if (!data) return [];
    return playbackIndex === null ? data.track : data.track.slice(0, playbackIndex + 1);
  }, [data, playbackIndex]);

  const displayedMarkers = useMemo(() => {
    if (!data) return [];
    if (playbackIndex === null) return data.markers;
    const revealCount = Math.max(
      0,
      Math.round(((playbackIndex + 1) / Math.max(trackLength, 1)) * chronologicalMarkers.length)
    );
    const visibleIds = new Set(chronologicalMarkers.slice(0, revealCount).map((m) => m.detection_id));
    return data.markers.filter((m) => visibleIds.has(m.detection_id));
  }, [data, playbackIndex, chronologicalMarkers, trackLength]);

  const vesselDuringPlayback = useMemo(() => {
    if (playbackIndex === null || displayedTrack.length === 0) return null;
    const last = displayedTrack[displayedTrack.length - 1];
    const prev = displayedTrack.length > 1 ? displayedTrack[displayedTrack.length - 2] : last;
    const headingDeg = last === prev ? 0 : bearingDeg(prev.latitude, prev.longitude, last.latitude, last.longitude);
    return { latitude: last.latitude, longitude: last.longitude, headingDeg };
  }, [playbackIndex, displayedTrack]);

  return (
    <AppShell title="GIS Map">
      <div className="mb-4 flex flex-wrap items-end gap-4 panel p-4">
        <div>
          <label className="mb-1 block text-xs text-slate-500">Survey</label>
          <select
            value={surveyId ?? ""}
            onChange={(e) => updateParam("survey_id", e.target.value)}
            className="rounded-md border border-abyss-600 bg-abyss-800 px-2 py-1.5 text-sm text-slate-200 outline-none focus:border-cyan-accent focus:shadow-glow-cyan"
          >
            {surveys?.items.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </div>
        <FilterSelect label="Class" value={detectionClass ?? ""} options={CLASS_OPTIONS} onChange={(v) => updateParam("detection_class", v)} />
        <FilterSelect label="Priority" value={priority ?? ""} options={PRIORITY_OPTIONS} onChange={(v) => updateParam("priority", v)} />
        <FilterSelect label="Review Status" value={reviewStatus ?? ""} options={REVIEW_OPTIONS} onChange={(v) => updateParam("review_status", v)} />
        <div className="ml-auto flex items-center gap-3">
          {data && (
            <span className="text-xs text-slate-500">
              {data.markers.length} detection{data.markers.length === 1 ? "" : "s"}
              {data.track.length > 1 ? ` · ${data.track.length} track points` : ""}
            </span>
          )}
        </div>
      </div>

      {data && canPlayback && (
        <div className="mb-4 flex flex-wrap items-center gap-3 panel p-3 text-xs">
          <button
            type="button"
            onClick={togglePlay}
            className="rounded-md border border-abyss-600 px-3 py-1.5 font-medium text-slate-200 hover:border-cyan-accent/50 hover:text-cyan-accent"
          >
            {isPlaying ? "⏸ Pause" : "▶ Replay"}
          </button>
          <input
            type="range"
            min={0}
            max={trackLength - 1}
            value={playbackIndex ?? trackLength - 1}
            onChange={(e) => scrubTo(Number(e.target.value))}
            className="h-1.5 max-w-xs flex-1 accent-cyan-500"
          />
          <span className="w-24 text-slate-500">
            {playbackIndex === null ? "Live" : `Point ${playbackIndex + 1} / ${trackLength}`}
          </span>
          <div className="flex overflow-hidden rounded-md border border-abyss-600">
            {[1, 2, 4].map((speed) => (
              <button
                key={speed}
                type="button"
                onClick={() => setPlaybackSpeed(speed)}
                className={clsx(
                  "px-2 py-1",
                  playbackSpeed === speed ? "bg-cyan-accent/10 text-cyan-accent" : "text-slate-400 hover:text-slate-200"
                )}
              >
                {speed}x
              </button>
            ))}
          </div>
          {playbackIndex !== null && (
            <button type="button" onClick={stopPlayback} className="text-slate-400 hover:text-cyan-accent">
              Back to live
            </button>
          )}
        </div>
      )}

      {!surveyId ? (
        <EmptyState title="No surveys available." description="Create a survey to view detections on the map." />
      ) : isLoading ? (
        <LoadingSkeleton rows={4} label="Loading map…" />
      ) : isError ? (
        <ErrorState message="Unable to load map data." onRetry={() => refetch()} />
      ) : !data || (data.markers.length === 0 && data.track.length === 0) ? (
        <EmptyState title="No detections found." description="No geotagged detections match the current filters." />
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_320px]">
          <div className="relative h-[620px] overflow-hidden rounded-lg border border-abyss-600">
            <MapView
              markers={displayedMarkers}
              bounds={data.bounds}
              track={displayedTrack}
              selectedId={selectedId}
              onSelect={setSelectedId}
              vesselPosition={vesselDuringPlayback}
            />
            <div className="pointer-events-none absolute bottom-3 left-3 z-[1000]">
              <div className="pointer-events-auto">
                <MapLegend />
              </div>
            </div>
          </div>

          <div className="flex h-[620px] flex-col overflow-hidden panel">
            {selectedDetection && (
              <div className="shrink-0 border-b border-abyss-600 p-3">
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-sm font-semibold text-slate-100">{selectedDetection.detection_ref}</p>
                  <Link
                    href={`/app/detections/${selectedDetection.id}`}
                    className="text-xs text-cyan-accent hover:underline"
                  >
                    Full Investigation →
                  </Link>
                </div>
                <SonarViewer frameId={selectedDetection.frame_id} bbox={selectedDetection.bbox} />
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-400">
                  <span>{formatConfidence(selectedDetection.calibrated_confidence)}</span>
                  <UncertaintyLabel level={selectedDetection.uncertainty} />
                  <PriorityBadge priority={selectedDetection.priority} />
                  <ReviewStatusBadge status={selectedDetection.review_status} />
                </div>
              </div>
            )}
            <div className="flex-1 overflow-y-auto">
            {data.markers.length === 0 ? (
              <div className="p-4 text-sm text-slate-500">No geotagged detections in this filter.</div>
            ) : (
              <ul className="divide-y divide-abyss-700">
                {data.markers.map((m) => (
                  <li key={m.detection_id}>
                    <button
                      onClick={() => setSelectedId(m.detection_id)}
                      className={clsx(
                        "block w-full px-4 py-3 text-left transition",
                        selectedId === m.detection_id ? "bg-cyan-accent/10" : "hover:bg-abyss-700/40"
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-slate-100">{m.detection_ref}</span>
                        <PriorityBadge priority={m.priority} />
                      </div>
                      <p className="mt-0.5 text-xs capitalize text-slate-400">{m.detection_class.replace("_", " ")}</p>
                      <div className="mt-1 flex items-center justify-between">
                        <span className="text-xs text-slate-500">{formatConfidence(m.calibrated_confidence)}</span>
                        <ReviewStatusBadge status={m.review_status} />
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            </div>
          </div>
        </div>
      )}

      {data && data.markers.length > 0 && (
        <p className="mt-3 text-xs text-slate-500">
          <Link href={`/app/detections?survey_id=${surveyId}`} className="text-cyan-accent hover:underline">
            View as list
          </Link>
        </p>
      )}
    </AppShell>
  );
}
