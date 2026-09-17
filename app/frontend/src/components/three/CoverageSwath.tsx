"use client";

import { useMemo } from "react";
import * as THREE from "three";

interface SwathPoint {
  x: number;
  z: number;
  range?: number | null;
}

/** Trailing ribbon showing the real sonar swath width behind the vessel,
 * built from each frame's actual `range` value (meters, spec-honest - never
 * a fixed/invented width). Points without a measured range are skipped, so
 * the ribbon only ever covers what was actually scanned. */
export function CoverageSwath({ points }: { points: SwathPoint[] }) {
  const geometry = useMemo(() => {
    const usable = points
      .filter((p) => typeof p.range === "number" && p.range > 0)
      .map((p) => ({ x: p.x, z: p.z, range: p.range as number }));
    if (usable.length < 2) return null;

    const positions: number[] = [];
    const indices: number[] = [];

    for (let i = 0; i < usable.length; i++) {
      const curr = usable[i];
      const prev = usable[i - 1] ?? curr;
      const next = usable[i + 1] ?? curr;
      const dx = next.x - prev.x;
      const dz = next.z - prev.z;
      const len = Math.hypot(dx, dz) || 1;
      const nx = -dz / len;
      const nz = dx / len;
      const half = curr.range;

      positions.push(curr.x + nx * half, 0.15, curr.z + nz * half);
      positions.push(curr.x - nx * half, 0.15, curr.z - nz * half);

      if (i > 0) {
        const base = (i - 1) * 2;
        indices.push(base, base + 1, base + 2);
        indices.push(base + 1, base + 3, base + 2);
      }
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    geo.setIndex(indices);
    geo.computeVertexNormals();
    return geo;
  }, [points]);

  if (!geometry) return null;

  return (
    <mesh geometry={geometry}>
      <meshBasicMaterial color="#C4F8FF" transparent opacity={0.07} side={THREE.DoubleSide} depthWrite={false} />
    </mesh>
  );
}
