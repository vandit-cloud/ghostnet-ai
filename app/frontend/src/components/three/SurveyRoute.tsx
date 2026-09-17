"use client";

import { Line } from "@react-three/drei";

/** Never drawn if a survey has no geotagged frames - no invented route. */
export function SurveyRoute({ points }: { points: [number, number, number][] }) {
  if (points.length < 2) return null;
  return (
    <Line
      points={points}
      color="#C4F8FF"
      lineWidth={1.6}
      dashed
      dashSize={2}
      gapSize={2.5}
      transparent
      opacity={0.75}
    />
  );
}
