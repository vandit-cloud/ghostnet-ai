"use client";

import { useRef } from "react";
import { useFrame, type ThreeEvent } from "@react-three/fiber";
import * as THREE from "three";
import { ALERT } from "@/utils/palette";

const PRIORITY_COLORS: Record<string, string> = {
  critical: ALERT.critical,
  high: ALERT.high,
  medium: ALERT.medium,
  low: ALERT.low,
};

function ShapeForClass({ detectionClass }: { detectionClass: string }) {
  switch (detectionClass) {
    case "ghost_net":
      return <coneGeometry args={[1.4, 2.6, 4]} />;
    case "debris":
      return <octahedronGeometry args={[1.5]} />;
    case "natural_object":
      return <sphereGeometry args={[1.3, 16, 16]} />;
    default:
      return <boxGeometry args={[2, 2, 2]} />;
  }
}

export function DetectionMarker({
  position,
  detectionClass,
  priority,
  selected = false,
  paused,
  scale = 1,
  onSelect,
}: {
  position: [number, number, number];
  detectionClass: string;
  priority: string;
  selected?: boolean;
  paused: boolean;
  /** Multiplier sized from the survey extent -- see Scene3D. The shapes are
   *  authored at 1.3-2.6 world units, which is about a pixel on a 1.7 km
   *  survey line, so without this they render invisibly small. */
  scale?: number;
  onSelect?: () => void;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const growthRef = useRef(0);
  const color = PRIORITY_COLORS[priority] ?? PRIORITY_COLORS.low;

  useFrame((state, delta) => {
    if (!paused) {
      growthRef.current = Math.min(1, growthRef.current + delta * 2.2);
    } else if (growthRef.current < 1) {
      growthRef.current = 1;
    }
    if (meshRef.current) {
      const pulse = selected && !paused ? 1 + Math.sin(state.clock.elapsedTime * 3) * 0.12 : 1;
      meshRef.current.scale.setScalar(growthRef.current * pulse);
    }
  });

  function handleClick(event: ThreeEvent<MouseEvent>) {
    event.stopPropagation();
    onSelect?.();
  }

  return (
    <group position={position} scale={scale}>
      <mesh ref={meshRef} position={[0, 3, 0]} onClick={handleClick}>
        <ShapeForClass detectionClass={detectionClass} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={selected ? 0.7 : 0.3} />
      </mesh>
    </group>
  );
}
