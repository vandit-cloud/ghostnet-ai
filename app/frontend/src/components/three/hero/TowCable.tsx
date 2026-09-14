"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Line } from "@react-three/drei";
import * as THREE from "three";

const SEGMENTS = 28;

/** The tow cable, rebuilt every frame as a sagging curve between the A-frame
 * and the towfish nose.
 *
 * It cannot be baked into either model, and it cannot be the fixed cylinder
 * Vessel.tsx uses: a cable under its own weight hangs in a catenary, and the
 * sag has to shrink as the fish moves astern and the cable comes taut. A
 * straight line between two moving points reads as a rigid rod and kills the
 * illusion immediately.
 *
 * Uses drei's <Line> (Line2 under the hood) rather than a TubeGeometry because
 * a tube would mean rebuilding and re-uploading geometry 60 times a second for
 * something that is two pixels wide on screen. */
export function TowCable({ from, to, deploy }: { from: THREE.Vector3; to: THREE.Vector3; deploy: number }) {
  const ref = useRef<any>(null);
  const points = useMemo(
    () => Array.from({ length: SEGMENTS + 1 }, () => new THREE.Vector3()),
    []
  );

  useFrame(() => {
    const span = from.distanceTo(to);
    // Sag peaks mid-deployment: lots of loose cable in the water early, pulled
    // near-straight once the fish is flying at speed and depth.
    const sag = span * 0.16 * Math.sin(Math.PI * Math.min(1, deploy)) + span * 0.04;
    const mid = from.clone().lerp(to, 0.5);
    mid.y -= sag;

    const curve = new THREE.QuadraticBezierCurve3(from, mid, to);
    curve.getPoints(SEGMENTS).forEach((p, i) => points[i].copy(p));
    ref.current?.geometry?.setPositions(points.flatMap((p) => [p.x, p.y, p.z]));
  });

  return (
    <Line
      ref={ref}
      points={points}
      color="#7f9bb3"
      lineWidth={1.6}
      transparent
      opacity={0.85}
    />
  );
}
