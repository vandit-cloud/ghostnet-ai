"use client";

import { useSurveyMap } from "@/features/map/hooks";
import { ATLANTIC } from "@/utils/palette";

const WIDTH = 64;
const HEIGHT = 28;
const PAD = 3;

/** Tiny static route shape for a survey list row - reuses the same
 * `/maps/surveys/{id}/detections` track data as the GIS map, just a
 * per-row lat/lon fetch instead of a new endpoint. Renders nothing if the
 * survey has no geotagged track (never draws an invented shape). */
export function RouteSparkline({ surveyId }: { surveyId: string }) {
  const { data, isLoading } = useSurveyMap(surveyId);
  const track = data?.track ?? [];

  if (isLoading) {
    return <span className="inline-block h-[28px] w-[64px] animate-pulse rounded bg-abyss-700/50" />;
  }
  if (track.length < 2) {
    return <span className="text-xs text-ink-3">—</span>;
  }

  const lats = track.map((p) => p.latitude);
  const lons = track.map((p) => p.longitude);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const minLon = Math.min(...lons);
  const maxLon = Math.max(...lons);
  const spanLat = maxLat - minLat || 1e-6;
  const spanLon = maxLon - minLon || 1e-6;

  const points = track
    .map((p) => {
      const x = PAD + ((p.longitude - minLon) / spanLon) * (WIDTH - PAD * 2);
      const y = HEIGHT - PAD - ((p.latitude - minLat) / spanLat) * (HEIGHT - PAD * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <svg width={WIDTH} height={HEIGHT} viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="opacity-80">
      <polyline points={points} fill="none" stroke={ATLANTIC} strokeWidth={1.4} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
