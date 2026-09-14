"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

function beamShape(spread: number, length: number): THREE.Shape {
  const shape = new THREE.Shape();
  shape.moveTo(0, 0);
  shape.lineTo(-spread, -length);
  shape.lineTo(spread * 0.35, -length);
  shape.closePath();
  return shape;
}

/** The real bowtie shape of an actual towed side-scan sonar swath: two beams
 * fanning out to either side with a gap directly beneath the towfish.
 * Animation only runs while `active` (an actual PROCESSING job) - otherwise
 * renders static and dim, per the "calmer when paused" requirement. */
export function SonarSweep({ active, paused }: { active: boolean; paused: boolean }) {
  const leftMat = useRef<THREE.MeshBasicMaterial>(null);
  const rightMat = useRef<THREE.MeshBasicMaterial>(null);
  const shape = useMemo(() => beamShape(13, 20), []);

  useFrame((state) => {
    if (paused) return;
    const pulse = active ? 0.16 + Math.sin(state.clock.elapsedTime * 2.2) * 0.08 : 0.06;
    if (leftMat.current) leftMat.current.opacity = pulse;
    if (rightMat.current) rightMat.current.opacity = pulse;
  });

  return (
    <group rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.05, 6]}>
      <mesh position={[-1.5, 0, 0]}>
        <shapeGeometry args={[shape]} />
        <meshBasicMaterial ref={leftMat} color="#C4F8FF" transparent opacity={0.06} side={THREE.DoubleSide} depthWrite={false} />
      </mesh>
      <mesh position={[1.5, 0, 0]} scale={[-1, 1, 1]}>
        <shapeGeometry args={[shape]} />
        <meshBasicMaterial ref={rightMat} color="#C4F8FF" transparent opacity={0.06} side={THREE.DoubleSide} depthWrite={false} />
      </mesh>
    </group>
  );
}
