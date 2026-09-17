"use client";

import { Canvas } from "@react-three/fiber";

import { OceanSurface } from "@/components/three/OceanSurface";
import { useReducedMotion } from "@/hooks/useReducedMotion";

/** Subtle ambient ocean behind the login card (spec: Page 01 - Login). Not
 * the full survey scene - just the ambient water plane, dimmed and static
 * when reduced motion is requested. */
export function LoginOceanBackground() {
  const reducedMotion = useReducedMotion();

  return (
    <Canvas
      className="!absolute inset-0"
      camera={{ position: [0, 40, 90], fov: 50, near: 1, far: 2000 }}
      dpr={[1, 1.5]}
      gl={{ antialias: true }}
    >
      <color attach="background" args={["#040a12"]} />
      <fog attach="fog" args={["#040a12", 150, 600]} />
      <ambientLight intensity={0.4} color="#0d2430" />
      <directionalLight position={[100, 150, 60]} intensity={0.55} color="#bfe9f5" />
      <OceanSurface paused={reducedMotion} size={1600} speed={0.55} />
      {/* Faster, dimmer near-surface layer - reads as light/caustics drifting
          over the deeper water below instead of one flat animated plane. */}
      <OceanSurface paused={reducedMotion} size={650} speed={1.4} opacity={0.28} y={9} />
    </Canvas>
  );
}
