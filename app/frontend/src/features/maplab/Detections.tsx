"use client";

/* =============================================================================
 * Detections in the plate lab.
 *
 * The marker itself lives in components/three/DetectionMarker.tsx and is
 * shared with the dashboard hero and the GIS map's 3D View. This file is only
 * the survey-space -> world mapping and the sample data: a second copy of the
 * marker here is how the lab and the product quietly drift apart, and the
 * whole point of prototyping it here was to ship the same thing.
 * ========================================================================== */

import { DetectionMarker } from "@/components/three/DetectionMarker";
import { SWATH_M, type SurveyPoint } from "./plate";

export interface LabDetection extends SurveyPoint {
  id: string;
  detectionClass: "ghost_net" | "debris" | "natural_object" | "unknown";
  priority: "critical" | "high" | "medium" | "low";
}

export function Detections({
  detections,
  selectedId,
  onSelect,
  paused,
}: {
  detections: LabDetection[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  paused: boolean;
}) {
  return (
    <group renderOrder={6}>
      {detections.map((d) => (
        <DetectionMarker
          key={d.id}
          position={[d.u * SWATH_M, 0, -d.v * SWATH_M]}
          detectionClass={d.detectionClass}
          priority={d.priority}
          selected={d.id === selectedId}
          paused={paused}
          onSelect={() => onSelect(d.id)}
        />
      ))}
    </group>
  );
}

/**
 * Stand-in detections, placed the way real ones fall: CLUSTERED, not scattered.
 * Ghost gear snags on the same seabed features repeatedly, so a survey finds
 * three contacts within 100 m and then nothing for a kilometre. Sprinkling
 * markers evenly produces a map that looks plausible and tests nothing -- in
 * particular it never puts two markers close enough to overlap, which is the
 * case the design has to survive.
 *
 * Coordinates are survey space (swath widths), so they sit on the legs.
 */
export const SAMPLE_DETECTIONS: LabDetection[] = [
  { id: "d1", u: -0.9, v: 1.9, detectionClass: "ghost_net", priority: "critical" },
  { id: "d2", u: -0.62, v: 2.05, detectionClass: "ghost_net", priority: "high" },
  { id: "d3", u: -0.75, v: 1.66, detectionClass: "debris", priority: "medium" },

  { id: "d4", u: 1.35, v: 2.62, detectionClass: "debris", priority: "high" },
  { id: "d5", u: 1.52, v: 2.5, detectionClass: "natural_object", priority: "low" },

  { id: "d6", u: 0.15, v: 3.45, detectionClass: "ghost_net", priority: "critical" },
  { id: "d7", u: 0.02, v: 3.62, detectionClass: "unknown", priority: "medium" },

  { id: "d8", u: -1.5, v: 4.3, detectionClass: "debris", priority: "low" },
  { id: "d9", u: 1.1, v: 5.1, detectionClass: "ghost_net", priority: "high" },
  { id: "d10", u: -0.4, v: 5.85, detectionClass: "natural_object", priority: "low" },
];
