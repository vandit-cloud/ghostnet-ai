"use client";

import { Canvas } from "@react-three/fiber";

import { OceanSurface } from "@/components/three/OceanSurface";
import { useReducedMotion } from "@/hooks/useReducedMotion";

/** Subtle non-interactive ambient ocean, reused as a backdrop wherever a page
 * needs the product's visual identity without the full interactive survey
 * scene (Login, New Survey form). `dim` lowers it further behind foreground
 * content that needs to stay readable. */
export function AmbientOceanBackground({ dim = false }: { dim?: boolean }) {
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
      <OceanSurface paused={reducedMotion} size={1600} speed={0.55} opacity={dim ? 0.4 : 1} />
      <OceanSurface paused={reducedMotion} size={650} speed={1.4} opacity={dim ? 0.12 : 0.28} y={9} />
    </Canvas>
  );
}
