"use client";

/* =============================================================================
 * Detection markers for the 3D views (dashboard hero and GIS map > 3D View).
 *
 * THE PROBLEM. projectLatLon works in metres, so the scene is as big as the
 * survey: a real line runs 1.7 km to 20 km. A marker authored at a believable
 * real size -- a 3 m net bundle -- is about a pixel at the near end of that and
 * far under one at the far end. It is not small, it is INVISIBLE, and no
 * colour choice fixes a sub-pixel mark.
 *
 * WHAT THIS REPLACES. The previous version took a `scale` multiplier derived
 * from the survey extent (extent / 60). That works for a top-down overview
 * where everything is roughly equidistant, and it breaks under a perspective
 * camera: ONE constant world scale makes near markers enormous while the far
 * ones are still specks, because the problem is the 1/distance falloff, not
 * the size. It also meant the same detection was drawn at wildly different
 * sizes in follow mode and overview mode, on the same survey.
 *
 * WHAT IT DOES INSTEAD. Three parts, each owning a different range band:
 *
 *   BEACON - a vertical shaft of light, held at constant SCREEN height. The
 *            one element that works at any distance, because it is the only
 *            part that leaves the water plane: at range everything flat
 *            compresses toward the horizon and stops being separable, while a
 *            vertical mark keeps its full height. This is what you actually
 *            see from 1.5 km.
 *   PIP    - the class shape, held at constant SCREEN size, so it stays
 *            identifiable at every range instead of at one.
 *   RING   - a flat ring at TRUE WORLD size, so it shrinks honestly with
 *            distance. This is the part that says where the thing really is
 *            and how big it really is; without it the screen-locked pip is a
 *            floating UI sticker with no believable position on the water.
 *
 * The ring is the honest one, the beacon is the findable one, the pip is the
 * identifiable one. Drop any one and a range band stops working. The same
 * split covers camera ANGLE too: from directly overhead the beacons
 * foreshorten to nothing and the rings carry it.
 * ========================================================================== */

import { useEffect, useMemo, useRef } from "react";
import { useFrame, type ThreeEvent } from "@react-three/fiber";
import * as THREE from "three";
import { ALERT, PAPER } from "@/utils/palette";

const PRIORITY_COLORS: Record<string, string> = {
  critical: ALERT.critical,
  high: ALERT.high,
  medium: ALERT.medium,
  low: ALERT.low,
};

/** The `*Px` values are SCREEN pixels, held constant across range; the `*M`
 *  values are world-metre floors, so a marker the camera is right on top of
 *  stops growing and behaves like an object again. Two units in one block is
 *  unusual and deliberate -- it is exactly the tension this file resolves. */
const MARKER = {
  beaconWidthPx: 3.5,
  beaconMinWidthM: 2.5,
  /** ~6% of a 1000 px viewport: findable at any distance without dominating. */
  beaconHeightPx: 64,
  beaconMinHeightM: 26,
  pipPx: 7,
  pipMinM: 2.2,
  /** True world size. Deliberately NOT scaled by survey extent: on a 20 km
   *  survey framed whole, this is sub-pixel and simply disappears, which is
   *  correct -- the beacon and pip are carrying visibility at that range, and
   *  a ring inflated to stay visible would be lying about the contact's size. */
  ringRadiusM: 24,
} as const;

/** World units per screen pixel at `dist`. The whole constant-screen-size
 *  trick is this one line. */
function worldPerPixel(dist: number, fovDeg: number, viewportH: number): number {
  return (2 * dist * Math.tan((fovDeg * Math.PI) / 360)) / Math.max(viewportH, 1);
}

function ShapeForClass({ detectionClass }: { detectionClass: string }) {
  // Shape carries the CLASS, colour carries the PRIORITY. Shape first: it
  // survives colour-blindness, and it survives the marker being a few pixels
  // of a single hue.
  switch (detectionClass) {
    case "ghost_net":
      return <coneGeometry args={[1, 1.9, 4]} />;
    case "debris":
      return <octahedronGeometry args={[1]} />;
    case "natural_object":
      return <sphereGeometry args={[0.9, 12, 12]} />;
    default:
      return <boxGeometry args={[1.4, 1.4, 1.4]} />;
  }
}

/** Unit quad, x in [-0.5, 0.5] and y in [0, 1], bright at the base and
 *  transparent at the top. Scaled per frame; see the yaw-only note below. */
function makeBeaconGeometry(): THREE.BufferGeometry {
  const geo = new THREE.BufferGeometry();
  const positions = [
    -0.5, 0, 0, 0.5, 0, 0, 0.5, 1, 0,
    -0.5, 0, 0, 0.5, 1, 0, -0.5, 1, 0,
  ];
  const alphas = [1, 1, 0, 1, 0, 0];
  const colors: number[] = [];
  for (const a of alphas) colors.push(1, 1, 1, a);
  geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geo.setAttribute("color", new THREE.Float32BufferAttribute(colors, 4));
  return geo;
}

export function DetectionMarker({
  position,
  detectionClass,
  priority,
  selected = false,
  paused,
  onSelect,
}: {
  position: [number, number, number];
  detectionClass: string;
  priority: string;
  selected?: boolean;
  paused: boolean;
  onSelect?: () => void;
}) {
  const color = PRIORITY_COLORS[priority] ?? PRIORITY_COLORS.low;
  const critical = priority === "critical";

  const beaconRef = useRef<THREE.Mesh>(null);
  const pipRef = useRef<THREE.Group>(null);
  const ringRef = useRef<THREE.Mesh>(null);
  const growthRef = useRef(0);
  const clockRef = useRef(0);

  const beaconGeometry = useMemo(makeBeaconGeometry, []);
  /* A BufferGeometry is a GPU allocation, and React unmounting the component
   * does not free it -- three has no finalizer. With one geometry per marker
   * and markers re-mounting on every filter change, this leaks a buffer per
   * marker per remount until the context is lost. */
  useEffect(() => () => beaconGeometry.dispose(), [beaconGeometry]);
  const world = useMemo(
    () => new THREE.Vector3(position[0], position[1], position[2]),
    [position]
  );

  useFrame(({ camera, size }, delta) => {
    // Grow-in, preserved from the previous marker: a detection arriving during
    // processing animates in rather than popping.
    if (!paused) {
      growthRef.current = Math.min(1, growthRef.current + delta * 2.2);
      clockRef.current += delta;
    } else if (growthRef.current < 1) {
      growthRef.current = 1;
    }

    // Read the lens off the actual camera rather than assuming one: Scene3D
    // uses fov 42, the lab uses its own, and an orbiting user can be anywhere.
    const fov = camera instanceof THREE.PerspectiveCamera ? camera.fov : 42;
    const dist = camera.position.distanceTo(world);
    const wpp = worldPerPixel(dist, fov, size.height);
    const grow = growthRef.current;

    // Only CRITICAL breathes. If every marker pulses, the pulse stops meaning
    // "look here" and becomes texture.
    const pulse = critical && !paused ? 1 + 0.16 * Math.sin(clockRef.current * 3.2) : 1;

    const beaconH = Math.max(MARKER.beaconMinHeightM, MARKER.beaconHeightPx * wpp) * pulse * grow;

    if (beaconRef.current) {
      beaconRef.current.scale.set(
        Math.max(MARKER.beaconMinWidthM, MARKER.beaconWidthPx * wpp) * grow,
        beaconH,
        1
      );
      // YAW-ONLY billboard, deliberately. A fully camera-facing quad tips over
      // as the camera pitches down and the beacon stops being vertical, which
      // is the single property it exists for.
      beaconRef.current.rotation.y = Math.atan2(
        camera.position.x - world.x,
        camera.position.z - world.z
      );
    }

    if (pipRef.current) {
      const s = Math.max(MARKER.pipMinM, MARKER.pipPx * wpp) * (selected ? 1.4 : 1) * pulse * grow;
      pipRef.current.scale.setScalar(s);
      pipRef.current.position.y = beaconH + s * 1.2;
      // The pip is the one part that faces the camera fully -- it is a symbol,
      // not an object in the world.
      pipRef.current.quaternion.copy(camera.quaternion);
    }

    if (ringRef.current) {
      ringRef.current.scale.setScalar((selected ? 1.35 : 1) * grow);
    }
  });

  function handleClick(event: ThreeEvent<MouseEvent>) {
    event.stopPropagation();
    onSelect?.();
  }

  /* `fog={false}` on every part, and it is a decision rather than an
   * oversight: a marker is UI, not scenery. Scene3D's fog is sized to the
   * survey extent, so a fogged marker at the far end of a long line fades into
   * the background exactly where being findable matters most -- which is the
   * problem this component exists to solve. Additive blending and fog also
   * interact badly, the fog colour being added rather than mixed. */
  return (
    <group position={position}>
      {/* RING -- true world size, shrinks honestly with distance. */}
      <mesh ref={ringRef} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.4, 0]}>
        <ringGeometry args={[MARKER.ringRadiusM * 0.72, MARKER.ringRadiusM, 28]} />
        <meshBasicMaterial
          color={color}
          transparent
          opacity={0.85}
          depthWrite={false}
          side={THREE.DoubleSide}
          toneMapped={false}
          fog={false}
        />
      </mesh>

      {/* BEACON -- the long-range cue.
          NORMAL blending, not additive. Additive only ever brightens, so on the
          overview's daylight sea it does almost nothing and the shaft washes
          out to nothing; the priority colour painted straight on reads against
          both a dark sea and a pale one. */}
      <mesh ref={beaconRef} geometry={beaconGeometry} position={[0, 0.2, 0]}>
        <meshBasicMaterial
          color={color}
          vertexColors
          transparent
          opacity={selected ? 1 : 0.9}
          depthWrite={false}
          side={THREE.DoubleSide}
          toneMapped={false}
          fog={false}
        />
      </mesh>

      {/* PIP -- constant screen size, sitting on top of the beacon, which is
          where the eye arrives after following the shaft up. */}
      {/* PIP -- a map-pin head, built back to front: a colour rim, a PAPER
          face, then the class symbol.
          The face is what makes this work. A bare coloured symbol has to
          out-contrast whatever is behind it, and the two backgrounds here are
          opposites -- near-black water in the old dusk overview, mid-blue in
          the daylight one -- so no single symbol colour wins both. Sitting the
          symbol on its own light disc means it only ever has to out-contrast
          the disc, which never changes. The `low` priority colour (#3D6C8A) is
          the proof: on blue water it is invisible, on paper it is crisp. */}
      <group ref={pipRef}>
        <mesh position={[0, 0, -0.02]} onClick={handleClick}>
          <circleGeometry args={[1.85, 24]} />
          <meshBasicMaterial color={color} toneMapped={false} fog={false} />
        </mesh>
        <mesh position={[0, 0, -0.01]}>
          <circleGeometry args={[1.5, 24]} />
          <meshBasicMaterial color={PAPER} toneMapped={false} fog={false} />
        </mesh>
        <mesh position={[0, 0, 0.35]}>
          <ShapeForClass detectionClass={detectionClass} />
          <meshBasicMaterial color={color} toneMapped={false} fog={false} />
        </mesh>
      </group>
    </group>
  );
}
