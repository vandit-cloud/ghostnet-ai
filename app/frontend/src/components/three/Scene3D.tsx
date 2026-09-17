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
import { ModelSlot, VESSEL_MODEL_URL } from "@/components/three/hero/ModelSlot";
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

/** How far the camera sits from the survey once fit to it -- shared by
 * CameraRig (which places the camera there) and SceneContents (which has to
 * make sure the fog reaches at least that far, or a small survey renders as
 * a flat wall of fog colour the instant the camera fits to it). Floored at
 * 30 so a tightly-clustered survey doesn't collapse this toward zero. */
function fitDistanceFor(bounds: LocalBounds): number {
  const spanX = Math.max(30, bounds.maxX - bounds.minX);
  const spanZ = Math.max(30, bounds.maxZ - bounds.minZ);
  return Math.max(spanX, spanZ) * 1.1 + 50;
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
  const hasAutoFitted = useRef(false);
  const fittingUntil = useRef(0);

  // Auto-frame the survey once bounds exist, without waiting for the user to
  // click "Fit Survey" -- otherwise the scene sits at its fixed default camera
  // position, which only ever happens to frame one particular survey size. On
  // a real survey (often 1000+ world units across) that default view was just
  // fog with the route line barely visible: an out-of-focus wall, not a scene.
  //
  // Skipped when the default mode is already "follow": that mode renders the
  // vessel/detections at natural scale (see SceneContents), so a forced wide
  // establishing shot would show a nearly-empty ocean for a second before
  // zooming to the boat, instead of going straight to the hero-style shot.
  if (!hasAutoFitted.current && bounds) {
    hasAutoFitted.current = true;
    if (cameraMode !== "follow") {
      fittingUntil.current = performance.now() + 1200;
    }
  }

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
      const dist = fitDistanceFor(bounds);
      camera.position.lerp(new THREE.Vector3(cx + dist * 0.45, dist * 0.65, cz + dist * 0.85), 0.12);
      if (orbit) {
        orbit.target.lerp(new THREE.Vector3(cx, 0, cz), 0.12);
        orbit.update();
      }
    } else if (cameraMode === "follow" && vesselPosition) {
      // Follow mode renders the vessel at natural (1x) scale -- same as the
      // login/hero page -- specifically so this close offset (identical to
      // the hero's own chase distance) puts the camera at a realistic,
      // hero-matching distance from it, not scaled up alongside an
      // artificially-enlarged hull.
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

/** Calibrated vertical correction applied to the vessel (and detections) ONLY
 * in follow mode -- see the long comment where this is used for why it
 * exists instead of real water geometry under the hull.
 *
 * HeroWaterBackdrop (composited behind Scene3D's transparent canvas in
 * follow mode, see SurveyHero.tsx) is a fixed, independently-rendered shot:
 * its own camera height and horizon never move. CameraRig's follow camera is
 * ALSO a fixed offset from the vessel ((+35, 50, +65), see CameraRig below),
 * so -- because both cameras are constants, not survey-dependent -- the
 * vessel's projected screen position relative to that backdrop's horizon is
 * the SAME fixed discrepancy for every survey, not something that varies per
 * survey the way, say, the overview's extent-scaled framing does. That is
 * what makes a single hand-tuned constant a legitimate fix here rather than
 * a hack that will drift the moment a different survey is opened: it was
 * measured once (the vessel rendered ~15 world units too high, matching its
 * own real GLTF bounding box height -- see ai/ai-log for that measurement),
 * and that offset does not change per survey.
 *
 * A real local water plane at y=0 was tried first and rejected: it visually
 * buried the ENTIRE natural-scale vessel (confirmed even at a patch barely
 * bigger than the hull's own footprint), which the model's own bounding box
 * says it should not do from this camera angle. Rather than ship an
 * unexplained regression while chasing that, this shifts the vessel down (a
 * plain, well-understood transform on geometry already known to render
 * correctly) so it visually sits on the backdrop's existing waterline
 * instead of trying to draw a second one under it. */
const FOLLOW_WATERLINE_Y = 0;

function SceneContents(props: Scene3DProps) {
  const { track, detections, vessel, bounds, sonarActive, selectedId, onSelectDetection, cameraMode, fitRequestId, paused } = props;

  const trackPoints: [number, number, number][] = track.map((p) => [p.x, 0.4, p.z]);
  const followActive = cameraMode === "follow";
  // CameraRig's own target/aim -- deliberately NOT shifted by
  // FOLLOW_WATERLINE_Y. Shifting this too (tried first) moves where the
  // camera looks without moving the camera itself (CameraRig's follow
  // "desired" position hardcodes its Y at a fixed 50, independent of the
  // target), which steepens the down-tilt enough to push the vessel out of
  // the frame entirely instead of just lower within it. Keeping the camera's
  // aim exactly where it already was known to work, and shifting only the
  // rendered mesh position below, moves the vessel within an unchanged shot
  // instead of changing the shot itself.
  const vesselPosition: [number, number, number] | null = vessel ? [vessel.x, 0, vessel.z] : null;
  // Where the vessel/detections are actually DRAWN -- see the comment above.
  const vesselRenderPosition: [number, number, number] | null = vessel
    ? [vessel.x, followActive ? FOLLOW_WATERLINE_Y : 0, vessel.z]
    : null;

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

  // Follow mode is a close, hero-page-style shot of the vessel -- rendered
  // at the SAME natural (1x) scale the login/hero page uses, shifted onto
  // the backdrop's waterline by FOLLOW_WATERLINE_Y above -- rather than the
  // huge, artificially-enlarged hull `markerScale` produces for the
  // survey-wide overview. Distant detections genuinely wouldn't be visible
  // from a real close chase-cam shot, so they only render at natural scale
  // too; the overview (`markerScale`) is what makes them visible at survey
  // scale in "Fit Survey" mode.
  const vesselScale = followActive ? 1 : markerScale;
  const detectionScale = followActive ? 1 : markerScale;

  // The fog's far plane must reach at least as far as CameraRig will ever
  // place the camera when fitting to this survey, or the fit lands the
  // camera beyond its own fog and the whole scene renders as a flat wall of
  // fog colour -- no ocean, track or vessel visible. `extent * 2.2` alone
  // guaranteed that for a large survey but not a small, tightly-clustered
  // one, because CameraRig's fit distance has a fixed +50 unit floor that a
  // tiny extent's fog range doesn't. Taking the max of both keeps every
  // survey size framed.
  const cameraFitDistance = bounds ? fitDistanceFor(bounds) : extent;
  const fogFar = Math.max(extent * 2.2, cameraFitDistance * 1.6);

  return (
    <>
      {/* In follow mode, Scene3D renders with a transparent clear colour (see
          the Canvas below) so HeroWaterBackdrop -- the exact landing-page
          water shader, composited behind this canvas in SurveyHero.tsx --
          shows through instead. A background colour, fog, or the survey's
          own ocean plane here would just paint over it. Fit/overview mode
          keeps all three: the backdrop's fixed camera height doesn't make
          sense at overview scale, so that mode still needs its own.

          The vessel/detections in follow mode are shifted down by
          FOLLOW_WATERLINE_Y (see below) rather than grounded with real
          geometry -- see that constant's own comment for why. */}
      {!followActive && (
        <>
          <color attach="background" args={["#072639"]} />
          <fog attach="fog" args={["#072639", extent * 0.25, fogFar]} />
        </>
      )}
      <ambientLight intensity={0.45} color="#0F4B70" />
      <directionalLight position={[120, 180, 80]} intensity={0.65} color="#C4F8FF" />
      <pointLight position={[0, 60, 0]} intensity={0.3} color="#C4F8FF" distance={Math.max(400, extent)} decay={2} />

      {!followActive && (
        // Fixed at 2400 by default, which only ever covers one survey size:
        // for a large survey (real lines run 20+ km) the plane is a tiny
        // patch in the middle of the framed view, and everything past its
        // edge is bare background colour -- not fog, not water, nothing
        // rendered there at all. Sized off `extent` like the fog/far-plane/
        // OrbitControls limits above, with room to spare so it still reaches
        // past the horizon at a steep look-down angle.
        <OceanSurface
          paused={paused}
          size={Math.max(2400, extent * 4)}
          fogNear={extent * 0.25}
          fogFar={fogFar}
          fogColor="#072639"
        />
      )}
      <CoverageSwath points={track} />
      <SurveyRoute points={trackPoints} />

      {vesselRenderPosition && (
        <group
          position={vesselRenderPosition}
          rotation={[0, (vessel!.headingDeg * Math.PI) / 180, 0]}
          scale={vesselScale}
        >
          <ModelSlot url={VESSEL_MODEL_URL} fallback={<Vessel />} />
          <SonarSweep active={sonarActive} paused={paused} />
        </group>
      )}

      {detections.map((d) => (
        <DetectionMarker
          key={d.id}
          position={[d.x, followActive ? FOLLOW_WATERLINE_Y : 0, d.z]}
          detectionClass={d.detectionClass}
          priority={d.priority}
          selected={d.id === selectedId}
          paused={paused}
          scale={detectionScale}
          onSelect={() => onSelectDetection?.(d.id)}
        />
      ))}

      <CameraRig cameraMode={cameraMode} fitRequestId={fitRequestId} bounds={bounds} vesselPosition={vesselPosition} />
      {/* minDistance was scaled for the survey OVERVIEW (hundreds to
          thousands of units) so a user inspecting the whole track couldn't
          zoom to a meaningless distance. But the follow-mode camera sits
          only ~85 units from a natural-scale vessel -- well under that
          overview minDistance -- so OrbitControls' own constraint
          enforcement was forcing the camera back out to it every frame,
          undoing the close shot CameraRig had just placed it at. A small
          fixed floor works for both modes; there's no need to scale it up,
          and capping maxDistance for follow mode instead (an earlier
          attempt at this fix) actively fights "Fit Survey" clicked from
          follow mode -- CameraRig lerping the camera out to the fit
          distance (often 10,000+ units) while OrbitControls clamps it back
          under a few hundred, every frame, which froze the tab. */}
      <OrbitControls
        makeDefault
        enableDamping
        dampingFactor={0.08}
        maxPolarAngle={Math.PI / 2.1}
        minDistance={5}
        maxDistance={Math.max(2000, extent * 3)}
      />
    </>
  );
}

export function Scene3D(props: Scene3DProps) {
  // Fixed at 4000 units, this clipped the ENTIRE scene the moment the camera
  // auto-fit to a real survey bigger than that: NBP0505-scale lines run to
  // 20+ km (tens of thousands of world units, since projectLatLon works in
  // metres), the fit distance scales with it, and a camera sitting 29,000
  // units from geometry with a 4000-unit far plane renders literally nothing
  // -- not fog, not a dim scene, a hard clip. Every surface behind that plane
  // is simply not drawn, so the canvas shows only its background colour.
  // Scaling this with the survey (like the fog and OrbitControls maxDistance
  // already do below) is what actually fixes that, not a fog tweak.
  const camFar = props.bounds ? Math.max(4000, fitDistanceFor(props.bounds) * 3) : 4000;

  return (
    <Canvas
      camera={{ position: [80, 90, 140], fov: 42, near: 1, far: camFar }}
      dpr={[1, 1.5]}
      // Always continuous -- same as the login/hero page's OceanSurface
      // Canvas, which never sets `frameloop` at all. Switching to "demand"
      // whenever `paused` (reduced-motion OR page-visibility) went true made
      // the whole scene, including the camera's continuous lerp toward the
      // vessel, mostly stop rendering: R3F only advances a "demand" canvas on
      // an explicit invalidation, and `document.visibilityState` can read
      // "hidden" in ordinary situations (window snapping, virtual desktops,
      // an undocked DevTools) that don't mean the user actually stopped
      // looking at the tab. The camera then sat wherever it happened to be
      // -- often still the default spawn position, looking at nothing.
      // `paused` still stops the ocean shader's own time uniform and the
      // sonar sweep/marker animations (see OceanSurface, SonarSweep,
      // DetectionMarker), so reduced-motion is still honoured for genuinely
      // decorative motion -- it just no longer breaks navigation.
      frameloop="always"
      // alpha:true so follow mode (no <color>/<fog> in SceneContents above)
      // clears to transparent instead of opaque black, letting
      // HeroWaterBackdrop's canvas underneath show through. Harmless for the
      // overview, which still paints a fully opaque <color> every frame.
      gl={{ antialias: true, alpha: true }}
    >
      <SceneContents {...props} />
    </Canvas>
  );
}
