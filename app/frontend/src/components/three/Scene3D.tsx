/* Colours here are the Atlantic palette in its ON-BLUE form: the ground is
 * atlantic/deep water and the accent is sky, because sky is what the palette
 * defines as bright ink on blue. See src/utils/palette.ts.
 */
"use client";

import { useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import * as THREE from "three";

import { CoverageSwath } from "@/components/three/CoverageSwath";
import { DetectionMarker } from "@/components/three/DetectionMarker";
import { OceanSurface } from "@/components/three/OceanSurface";
import { SonarSweep } from "@/components/three/SonarSweep";
import { SurveyRoute } from "@/components/three/SurveyRoute";
import { Vessel } from "@/components/three/Vessel";
import type { LocalBounds } from "@/components/three/utils/geo3d";

export interface Scene3DDetection {
  id: string;
  x: number;
  z: number;
  detectionClass: string;
  priority: string;
}

export interface Scene3DProps {
  track: { x: number; z: number; range?: number | null }[];
  detections: Scene3DDetection[];
  vessel: { x: number; z: number; headingDeg: number } | null;
  bounds: LocalBounds | null;
  sonarActive: boolean;
  selectedId?: string;
  onSelectDetection?: (id: string) => void;
  cameraMode: "follow" | "free";
  fitRequestId: number;
  paused: boolean;
}

function CameraRig({
  cameraMode,
  fitRequestId,
  bounds,
  vesselPosition,
}: {
  cameraMode: "follow" | "free";
  fitRequestId: number;
  bounds: LocalBounds | null;
  vesselPosition: [number, number, number] | null;
}) {
  const { camera, controls } = useThree((state) => ({ camera: state.camera, controls: state.controls }));
  const lastFitId = useRef(fitRequestId);
  const fittingUntil = useRef(0);

  if (lastFitId.current !== fitRequestId) {
    lastFitId.current = fitRequestId;
    fittingUntil.current = performance.now() + 1200;
  }

  useFrame(() => {
    const orbit = controls as unknown as { target: THREE.Vector3; update: () => void } | null;
    const isFitting = performance.now() < fittingUntil.current && bounds;

    if (isFitting && bounds) {
      const cx = (bounds.minX + bounds.maxX) / 2;
      const cz = (bounds.minZ + bounds.maxZ) / 2;
      const spanX = Math.max(30, bounds.maxX - bounds.minX);
      const spanZ = Math.max(30, bounds.maxZ - bounds.minZ);
      const dist = Math.max(spanX, spanZ) * 1.1 + 50;
      camera.position.lerp(new THREE.Vector3(cx + dist * 0.45, dist * 0.65, cz + dist * 0.85), 0.12);
      if (orbit) {
        orbit.target.lerp(new THREE.Vector3(cx, 0, cz), 0.12);
        orbit.update();
      }
    } else if (cameraMode === "follow" && vesselPosition) {
      const target = new THREE.Vector3(...vesselPosition);
      const desired = new THREE.Vector3(vesselPosition[0] + 35, 50, vesselPosition[2] + 65);
      camera.position.lerp(desired, 0.05);
      if (orbit) {
        orbit.target.lerp(target, 0.08);
        orbit.update();
      }
    }
  });

  return null;
}

function SceneContents(props: Scene3DProps) {
  const { track, detections, vessel, bounds, sonarActive, selectedId, onSelectDetection, cameraMode, fitRequestId, paused } = props;

  const trackPoints: [number, number, number][] = track.map((p) => [p.x, 0.4, p.z]);
  const vesselPosition: [number, number, number] | null = vessel ? [vessel.x, 0, vessel.z] : null;

  // Everything below is sized RELATIVE TO THE SURVEY, and it has to be.
  //
  // projectLatLon returns METRES, so the scene is as big as the survey line:
  // NBP0505 line 01B spans about 1,680 m along-track by 607 m across. The
  // markers are authored at 1.3-2.6 world units and the fog was fixed at
  // 220/1150, so on a real survey every marker was roughly ONE PIXEL and the
  // far half of the track sat beyond the fog's far plane. The route line was
  // the only thing visible, because a line keeps a 1 px minimum width however
  // small it is in world space.
  //
  // A fixed world constant is only ever right for one survey size. These are
  // fractions of the extent instead, so a 200 m harbour scan and a 5 km
  // offshore line both frame correctly.
  // bounds is null until the survey has at least one placed point; 1000 is a
  // neutral stand-in that only ever applies to an empty scene.
  const extent = bounds
    ? Math.max(bounds.maxX - bounds.minX, bounds.maxZ - bounds.minZ, 1)
    : 1000;
  const markerScale = Math.max(1, extent / 60);

  return (
    <>
      <color attach="background" args={["#072639"]} />
      <fog attach="fog" args={["#072639", extent * 0.25, extent * 2.2]} />
      <ambientLight intensity={0.45} color="#0F4B70" />
      <directionalLight position={[120, 180, 80]} intensity={0.65} color="#C4F8FF" />
      <pointLight position={[0, 60, 0]} intensity={0.3} color="#C4F8FF" distance={Math.max(400, extent)} decay={2} />

      <OceanSurface paused={paused} />
      <CoverageSwath points={track} />
      <SurveyRoute points={trackPoints} />

      {vesselPosition && (
        <group
          position={vesselPosition}
          rotation={[0, (vessel!.headingDeg * Math.PI) / 180, 0]}
          scale={markerScale}
        >
          <Vessel />
          <SonarSweep active={sonarActive} paused={paused} />
        </group>
      )}

      {detections.map((d) => (
        <DetectionMarker
          key={d.id}
          position={[d.x, 0, d.z]}
          detectionClass={d.detectionClass}
          priority={d.priority}
          selected={d.id === selectedId}
          paused={paused}
          scale={markerScale}
          onSelect={() => onSelectDetection?.(d.id)}
        />
      ))}

      <CameraRig cameraMode={cameraMode} fitRequestId={fitRequestId} bounds={bounds} vesselPosition={vesselPosition} />
      <OrbitControls
        makeDefault
        enableDamping
        dampingFactor={0.08}
        maxPolarAngle={Math.PI / 2.1}
        minDistance={Math.max(5, extent / 60)}
        maxDistance={Math.max(2000, extent * 3)}
      />
    </>
  );
}

export function Scene3D(props: Scene3DProps) {
  return (
    <Canvas
      camera={{ position: [80, 90, 140], fov: 42, near: 1, far: 4000 }}
      dpr={[1, 1.5]}
      frameloop={props.paused ? "demand" : "always"}
      gl={{ antialias: true }}
    >
      <SceneContents {...props} />
    </Canvas>
  );
}
