"use client";

import { useMemo, useRef, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";

import { OceanSurface } from "@/components/three/OceanSurface";
import { SonarSweep } from "@/components/three/SonarSweep";
import { Vessel } from "@/components/three/Vessel";
import { ModelSlot, VESSEL_MODEL_URL } from "@/components/three/hero/ModelSlot";
import { MarineSnow } from "@/components/three/hero/MarineSnow";
import { SonarReturns } from "@/components/three/hero/SonarReturns";
import { TowCable } from "@/components/three/hero/TowCable";
import { Towfish } from "@/components/three/hero/Towfish";
import { SEABED_Y, STAGE_DEPLOY_END, STAGE_IDLE_END, TOW_POINT, sceneStateFor, span } from "@/components/three/hero/stages";

/** The vessel sits to the RIGHT of the viewport, so the camera looks at a point
 * to its port side and the left half of the canvas stays clear for copy.
 * In metres, like everything else - vessel.glb is 28 m long. */
const VESSEL_X = 30;

/** Sonar swath half-range. SonarSweep is authored at ~13 units of spread, so
 * this opens it to roughly 45 m per side - a believable short-range setting. */
const SWEEP_SCALE = 3.4;

interface CameraKey {
  at: number;
  position: [number, number, number];
  target: [number, number, number];
}

/** Camera choreography. Above the waterline for the idle, dropping under it as
 * the fish descends, then pulling back to reveal the painted swath. */
const CAMERA_PATH: CameraKey[] = [
  { at: 0.0, position: [-44, 22, 104], target: [6, 6, 0] },
  { at: STAGE_IDLE_END, position: [-26, 14, 78], target: [12, 3, 14] },
  { at: STAGE_DEPLOY_END, position: [-36, -12, 70], target: [8, -20, 38] },
  { at: 0.82, position: [-62, -34, 92], target: [0, -44, 54] },
  { at: 1.0, position: [-78, -24, 138], target: [0, -47, 60] },
];

function sampleCamera(p: number, outPos: THREE.Vector3, outTarget: THREE.Vector3) {
  let a = CAMERA_PATH[0];
  let b = CAMERA_PATH[CAMERA_PATH.length - 1];
  for (let i = 0; i < CAMERA_PATH.length - 1; i += 1) {
    if (p >= CAMERA_PATH[i].at && p <= CAMERA_PATH[i + 1].at) {
      a = CAMERA_PATH[i];
      b = CAMERA_PATH[i + 1];
      break;
    }
  }
  const t = span(p, a.at, b.at);
  outPos.set(...a.position).lerp(new THREE.Vector3(...b.position), t);
  outTarget.set(...a.target).lerp(new THREE.Vector3(...b.target), t);
}

function SceneContents({
  progress,
  paused,
}: {
  progress: React.MutableRefObject<number>;
  paused: boolean;
}) {
  const vesselRef = useRef<THREE.Group>(null);
  const fishPos = useMemo(() => new THREE.Vector3(), []);
  const towOrigin = useMemo(() => new THREE.Vector3(), []);
  const camPos = useMemo(() => new THREE.Vector3(), []);
  const camTarget = useMemo(() => new THREE.Vector3(), []);
  const state = useRef(sceneStateFor(0, 0));

  /** Children below take plain numbers (deploy, ping, paint, lock) as props, so
   * they only update when this component RE-RENDERS - and useFrame never causes
   * a render. Until now the scene animated only because the lab page happened
   * to re-render on the 1%-quantised `settled` value from useScrollProgress,
   * whose own comment states the 3D scene never reads it. It did, by accident:
   * memoize HeroScene or drop that caption and the sonar, the cable sag and the
   * target lock all pin silently to zero while the camera keeps moving.
   *
   * So the scene now drives its own renders off its own progress ref. Still
   * quantised - a render per 0.4% of scroll, ~250 over the whole hero - because
   * a render per frame would be the other, worse mistake. */
  const [, setTick] = useState(0);
  const rendered = useRef(-1);

  useFrame((ctx, delta) => {
    const p = progress.current;
    if (Math.abs(p - rendered.current) > 0.004) {
      rendered.current = p;
      setTick((t) => t + 1);
    }
    const elapsed = paused ? 0 : ctx.clock.elapsedTime;
    const next = sceneStateFor(p, elapsed);
    state.current = next;

    fishPos.set(next.fish.x + VESSEL_X, next.fish.y, next.fish.z);
    towOrigin.set(VESSEL_X + TOW_POINT.x, TOW_POINT.y, TOW_POINT.z);

    if (vesselRef.current && !paused) {
      // Gentle heave and roll on the swell. Pinned to the same clock as
      // OceanSurface's shader so the boat and the water agree.
      vesselRef.current.position.y = Math.sin(elapsed * 0.6) * 0.5;
      vesselRef.current.rotation.z = Math.sin(elapsed * 0.45) * 0.02;
      vesselRef.current.rotation.x = Math.sin(elapsed * 0.6 + 0.8) * 0.015;
    }

    // Damped follow, so a fast flick of the scroll wheel does not snap the
    // camera. The scene stays scrubbable but never jitters.
    sampleCamera(p, camPos, camTarget);
    const k = 1 - Math.pow(0.0015, delta);
    ctx.camera.position.lerp(camPos, k);
    ctx.camera.lookAt(camTarget);
  });

  const s = state.current;

  return (
    <>
      <color attach="background" args={["#040a12"]} />
      <fog attach="fog" args={["#040a12", 110, 520]} />
      <ambientLight intensity={0.5} color="#0d2430" />
      <directionalLight position={[40, 90, 40]} intensity={0.8} color="#bfe9f5" />
      <pointLight position={[VESSEL_X, 26, 16]} intensity={0.5} color="#22d3ee" distance={240} decay={2} />

      <OceanSurface paused={paused} size={1500} />
      <OceanSurface paused={paused} size={1500} speed={1.6} opacity={0.35} y={-1.6} />

      <group ref={vesselRef} position={[VESSEL_X, 0, 0]}>
        <ModelSlot url={VESSEL_MODEL_URL} fallback={<Vessel />} />
      </group>

      <TowCable from={towOrigin} to={fishPos} deploy={s.deploy} />
      <Towfish position={fishPos} deploy={s.deploy} paused={paused} />

      <group position={[fishPos.x, fishPos.y, fishPos.z]} scale={SWEEP_SCALE}>
        <SonarSweep active={s.ping > 0.25} paused={paused} />
      </group>

      {/* x MUST track the tow path. The shader puts its nadir gap down the
          centre of this plane, so leaving it at the world origin painted the
          imagery 30 m to port of the fish that was supposedly making it. */}
      <SonarReturns x={VESSEL_X} y={SEABED_Y} paint={s.paint} lock={s.lock} paused={paused} />

      {/* Sells the forward motion the far field is too distant to show, and
          gives the empty water the depth cues it had none of. */}
      <MarineSnow center={[VESSEL_X, -16, 36]} opacity={s.deploy} paused={paused} />

      <mesh position={[VESSEL_X, SEABED_Y - 1, 40]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[1200, 1200]} />
        <meshStandardMaterial color="#061019" roughness={1} />
      </mesh>
    </>
  );
}

export function HeroScene({
  progress,
  paused,
}: {
  progress: React.MutableRefObject<number>;
  paused: boolean;
}) {
  return (
    <Canvas
      camera={{ position: [-44, 22, 104], fov: 40, near: 0.5, far: 1600 }}
      dpr={[1, 1.5]}
      gl={{ antialias: true, powerPreference: "high-performance" }}
    >
      <SceneContents progress={progress} paused={paused} />
    </Canvas>
  );
}
