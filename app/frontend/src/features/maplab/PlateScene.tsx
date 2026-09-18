"use client";

/* =============================================================================
 * The plate, as a real 3D scene.
 *
 * Reuses the project's own pieces rather than re-drawing them:
 *   OceanSurface  - the water shader the 3D survey view and login page use
 *   ModelSlot     - vessel.glb, with Vessel.tsx as the documented fallback
 *   PlateOverlay  - the only part this feature owns
 *
 * The camera is placed from two measurements off the reference (see
 * PARAMS.camera) and then left alone. Orbit is available in the lab for
 * inspection, but the shipped pose is the fixed one -- the whole composition
 * is built around where the horizon lands.
 * ========================================================================== */

import { Canvas, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

import { ModelSlot, VESSEL_MODEL_URL } from "@/components/three/hero/ModelSlot";
import { OceanSurface } from "@/components/three/OceanSurface";
import { Vessel } from "@/components/three/Vessel";

import { DEFAULT_LAYERS, PARAMS, SWATH_M, type PlateLayers } from "./plate";

export { DEFAULT_LAYERS, type PlateLayers };
import { Detections, SAMPLE_DETECTIONS } from "./Detections";
import {
  CoverageSlabs,
  RouteLine,
  SurveyGrid,
  SwathEdges,
  TargetMarker,
  WaypointNodes,
  useSurveyRoute,
} from "./PlateOverlay";


/* ---------------------------------------------------------------------------
 * Camera
 * ------------------------------------------------------------------------ */

function CameraRig({ orbit }: { orbit: boolean }) {
  const camera = useThree((s) => s.camera);

  useEffect(() => {
    if (orbit) return;
    const C = PARAMS.camera;
    camera.position.set(0, C.height, C.astern);
    // Pitch, not lookAt-a-point: the composition is defined by where the
    // HORIZON sits in frame, and the horizon's position depends only on the
    // pitch angle. Aiming at a point on the water instead couples the framing
    // to that point's distance, so changing the survey layout would silently
    // move the horizon.
    const pitch = (C.pitchDeg * Math.PI) / 180;
    camera.rotation.set(pitch, 0, 0, "YXZ");
    camera.updateProjectionMatrix();
  }, [camera, orbit]);

  return null;
}

/* ---------------------------------------------------------------------------
 * Sky
 * ------------------------------------------------------------------------ */

/** A graded dome rather than a flat clear colour. The bottom stop is exactly
 *  the fog colour, so the sea's distance fade and the sky meet at the horizon
 *  with no seam to match by hand -- they are literally the same value there. */
function SkyDome() {
  const uniforms = useMemo(
    () => ({
      uHorizon: { value: new THREE.Color(PARAMS.scene.fogColor) },
      uZenith: { value: new THREE.Color("#2E7BC4") },
    }),
    []
  );

  return (
    <mesh renderOrder={-1}>
      <sphereGeometry args={[PARAMS.camera.far * 0.9, 24, 16]} />
      <shaderMaterial
        side={THREE.BackSide}
        depthWrite={false}
        uniforms={uniforms}
        vertexShader={`
          varying float vH;
          void main() {
            vH = normalize(position).y;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
          }
        `}
        fragmentShader={`
          uniform vec3 uHorizon;
          uniform vec3 uZenith;
          varying float vH;
          void main() {
            float t = smoothstep(0.0, 0.42, vH);
            gl_FragColor = vec4(mix(uHorizon, uZenith, t), 1.0);
          }
        `}
      />
    </mesh>
  );
}

/* ---------------------------------------------------------------------------
 * Wake
 * ------------------------------------------------------------------------ */

/** Foam astern. The 19.5° spread is the Kelvin half-angle -- the constant
 *  angle of a displacement hull's wake at any speed. It is physics, not a
 *  style choice, and widening it is the fastest way to make a vessel stop
 *  looking like it is on water. */
function Wake() {
  const geometry = useMemo(() => {
    const length = PARAMS.survey.sternTrail * SWATH_M;
    const spread = Math.tan((19.5 * Math.PI) / 180);
    const steps = 24;

    const positions: number[] = [];
    const colors: number[] = [];

    const strip = (
      centreAt: (t: number) => number,
      halfWidthAt: (t: number) => number,
      alphaAt: (t: number) => number
    ) => {
      for (let i = 1; i <= steps; i++) {
        const t0 = (i - 1) / steps;
        const t1 = i / steps;
        const z0 = t0 * length;
        const z1 = t1 * length;
        const c0 = centreAt(t0);
        const c1 = centreAt(t1);
        const w0 = halfWidthAt(t0);
        const w1 = halfWidthAt(t1);
        const a0 = alphaAt(t0);
        const a1 = alphaAt(t1);

        const quad = [
          [c0 - w0, z0, a0],
          [c0 + w0, z0, a0],
          [c1 + w1, z1, a1],
          [c0 - w0, z0, a0],
          [c1 + w1, z1, a1],
          [c1 - w1, z1, a1],
        ];
        for (const [x, z, a] of quad) {
          positions.push(x, 0.35, z);
          colors.push(1, 1, 1, a);
        }
      }
    };

    // Propeller wash: densest foam, straight astern.
    strip(
      () => 0,
      (t) => 5 + 22 * t,
      (t) => 0.85 * (1 - t) + 0.08
    );
    // The two Kelvin arms.
    for (const side of [-1, 1]) {
      strip(
        (t) => side * spread * t * length,
        (t) => 4 + 20 * t,
        (t) => 0.62 * (1 - t) + 0.06
      );
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    geo.setAttribute("color", new THREE.Float32BufferAttribute(colors, 4));
    return geo;
  }, []);

  // three has no finalizer: an unmounted mesh's geometry stays on the GPU.
  useEffect(() => () => geometry.dispose(), [geometry]);

  return (
    <mesh geometry={geometry} renderOrder={0}>
      <meshBasicMaterial
        vertexColors
        transparent
        depthWrite={false}
        side={THREE.DoubleSide}
        toneMapped={false}
      />
    </mesh>
  );
}


/* ---------------------------------------------------------------------------
 * Vessel
 * ------------------------------------------------------------------------ */

/**
 * The hull, placed against its own contract (public/models/README.md): bow
 * along Blender +Y -> glTF -Z, origin AT THE WATERLINE, authored at real
 * metres. So the correct placement is the origin, unrotated, and the scale is
 * whatever it takes to make the model its REAL length.
 *
 * That last part is not a fudge, it is the missing half of the contract. The
 * README fixes orientation and origin but says nothing about absolute size,
 * and every text-to-3D generator normalises its output to roughly 1-2 units
 * (HERO_VESSEL_MODEL_BRIEF.md documents exactly this, as step one of the
 * Blender fixup pass). A model that skipped that pass is not wrong in a way
 * the scene can detect from orientation alone -- it just renders a 2 m dinghy
 * where a 28 m survey vessel should be, and nothing else in the frame has a
 * known size to contradict it.
 *
 * So: measure the model, scale it to VESSEL_LENGTH_M, and say so in dev. The
 * vessel is the only object here with a real-world size, which makes it the
 * scale reference for the whole composition -- if it is wrong, the camera
 * distance derived from it in PARAMS.camera is wrong too.
 */
const VESSEL_LENGTH_M = 28;

function VesselRig() {
  const group = useRef<THREE.Group>(null);
  const [scale, setScale] = useState<number>(PARAMS.vessel.scale);

  useEffect(() => {
    const id = window.setTimeout(() => {
      if (!group.current) return;
      const box = new THREE.Box3().setFromObject(group.current);
      const size = new THREE.Vector3();
      box.getSize(size);
      // Length is the longest horizontal axis: a hull is longer than it is
      // wide or tall, whichever way the exporter happened to lay it out.
      const length = Math.max(size.x, size.z);
      if (!Number.isFinite(length) || length < 1e-4) return;

      const factor = VESSEL_LENGTH_M / length;
      if (process.env.NODE_ENV !== "production") {
        console.info(
          `[maplab] vessel.glb measures ${length.toFixed(2)} units -> scale ` +
            `${factor.toFixed(3)} for ${VESSEL_LENGTH_M} m. A model authored at ` +
            `real metres makes this a no-op; see HERO_VESSEL_MODEL_BRIEF.md.`
        );
      }
      if (Math.abs(factor - 1) < 0.02) return;
      setScale(factor);
    }, 350);
    return () => window.clearTimeout(id);
  }, []);

  return (
    <group
      position={[0, PARAMS.vessel.y, 0]}
      rotation={[0, (PARAMS.vessel.headingDeg * Math.PI) / 180, 0]}
      scale={scale}
    >
      <group ref={group}>
        <ModelSlot url={VESSEL_MODEL_URL} fallback={<Vessel />} />
      </group>
    </group>
  );
}

/* ---------------------------------------------------------------------------
 * Scene
 * ------------------------------------------------------------------------ */

function SceneContents({
  layers,
  paused,
  orbit,
  selectedId,
  onSelect,
}: {
  layers: PlateLayers;
  paused: boolean;
  orbit: boolean;
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const route = useSurveyRoute();
  const S = PARAMS.scene;

  return (
    <>
      <color attach="background" args={[S.fogColor]} />
      <fog attach="fog" args={[S.fogColor, S.fogNear, S.fogFar]} />
      <SkyDome />

      <ambientLight intensity={S.ambientIntensity} color="#C4F8FF" />
      <hemisphereLight
        intensity={S.hemiIntensity}
        color="#DCEBF5"
        groundColor={S.waterShallow}
      />
      <directionalLight
        position={[S.sunPosition[0], S.sunPosition[1], S.sunPosition[2]]}
        intensity={S.sunIntensity}
        color="#FFFFFF"
      />

      {layers.water && (
        <OceanSurface
          paused={paused}
          size={S.oceanSize}
          fogNear={S.fogNear}
          fogFar={S.fogFar}
          fogColor={S.fogColor}
          // The same shader, under a midday sun instead of the survey view's
          // dusk. Only the three water tones and the sun direction move; the
          // wave field, the Fresnel and the glint are untouched.
          deepColor={S.waterDeep}
          shallowColor={S.waterShallow}
          skyColor={S.waterSky}
          sunDirection={[...S.sunPosition] as [number, number, number]}
          waveHeight={S.waveHeight}
        />
      )}

      {layers.wake && <Wake />}
      {layers.swath && <CoverageSlabs route={route} />}
      {layers.grid && <SurveyGrid route={route} />}
      {layers.edges && <SwathEdges route={route} />}
      {layers.route && <RouteLine route={route} paused={paused} />}
      {layers.nodes && <WaypointNodes route={route} />}
      {layers.target && <TargetMarker route={route} paused={paused} />}
      {layers.detections && (
        <Detections
          detections={SAMPLE_DETECTIONS}
          selectedId={selectedId}
          onSelect={onSelect}
          paused={paused}
        />
      )}

      {/* The vessel's own contract (public/models/README.md) is bow along
          Blender +Y -> glTF -Z, origin AT THE WATERLINE, authored at real
          metres. So the correct placement is the origin, unrotated, unscaled:
          it sails away from the camera along the route, sitting in the water
          at its true 28 m. Any y-offset or scale factor here would be papering
          over a bad export instead of placing a good one. */}
      {layers.vessel && <VesselRig />}

      <CameraRig orbit={orbit} />
      {orbit && (
        <OrbitControls makeDefault enableDamping dampingFactor={0.08} target={[0, 0, -600]} />
      )}
    </>
  );
}

export function PlateScene({
  layers,
  paused,
  orbit,
  selectedId,
  onSelect,
  className,
}: {
  layers: PlateLayers;
  paused: boolean;
  orbit: boolean;
  selectedId: string | null;
  onSelect: (id: string) => void;
  className?: string;
}) {
  const C = PARAMS.camera;
  return (
    <div className={className}>
      <Canvas
        camera={{ position: [0, C.height, C.astern], fov: C.fov, near: C.near, far: C.far }}
        dpr={[1, 1.75]}
        // "demand" while paused: the page computes `paused` from reduced-motion
        // and the space-bar toggle, and without this the canvas still renders a
        // full frame every vsync at up to 1.75 DPR with nothing moving in it.
        frameloop={paused ? "demand" : "always"}
        gl={{ antialias: true }}
      >
        <SceneContents
          layers={layers}
          paused={paused}
          orbit={orbit}
          selectedId={selectedId}
          onSelect={onSelect}
        />
      </Canvas>
    </div>
  );
}

