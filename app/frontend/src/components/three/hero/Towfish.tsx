"use client";

import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

import { ModelSlot, TOWFISH_MODEL_URL } from "@/components/three/hero/ModelSlot";
import { TOWFISH_DISPLAY_SCALE, descentPitch } from "@/components/three/hero/stages";

/** Primitive stand-in for the towfish, used until towfish.glb lands.
 *
 * Shaped like the real hardware rather than a generic box: a torpedo body with
 * tail fins and a flat transducer array down each flank. The flanks matter -
 * they are the physical reason the swath is a bowtie with a gap directly
 * underneath, which is what SonarSweep draws. Nose along -z, matching the
 * vessel's convention. */
function TowfishPrimitive() {
  return (
    <group>
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <capsuleGeometry args={[0.42, 1.9, 6, 12]} />
        <meshStandardMaterial color="#f2b544" roughness={0.45} metalness={0.35} />
      </mesh>
      {[-1, 1].map((side) => (
        <mesh key={side} position={[side * 0.44, 0, 0.1]}>
          <boxGeometry args={[0.08, 0.34, 1.5]} />
          <meshStandardMaterial color="#16293b" roughness={0.3} metalness={0.6} />
        </mesh>
      ))}
      <mesh position={[0, 0, 1.45]}>
        <boxGeometry args={[1.25, 0.06, 0.62]} />
        <meshStandardMaterial color="#16293b" roughness={0.4} />
      </mesh>
      <mesh position={[0, 0, 1.45]} rotation={[0, 0, Math.PI / 2]}>
        <boxGeometry args={[1.0, 0.06, 0.62]} />
        <meshStandardMaterial color="#16293b" roughness={0.4} />
      </mesh>
      <mesh position={[0, 0.18, -1.28]}>
        <sphereGeometry args={[0.09, 8, 8]} />
        <meshStandardMaterial color="#22d3ee" emissive="#22d3ee" emissiveIntensity={1.4} />
      </mesh>
    </group>
  );
}

/** The towfish as an INDEPENDENT body - deliberately not a child of the vessel.
 *
 * In Vessel.tsx the towfish is welded to the hull at a fixed z, which is right
 * for a map marker and impossible for a deployment: it has to descend, trail
 * further astern as it goes, and fly its own attitude on the cable. */
export function Towfish({
  position,
  deploy,
  paused,
}: {
  position: THREE.Vector3;
  deploy: number;
  paused: boolean;
}) {
  const group = useRef<THREE.Group>(null);

  useFrame((state) => {
    if (!group.current) return;
    group.current.position.copy(position);

    // Attitude is a function of deploy, NOT of the clock, so it survives a
    // pause and scrubs backwards with the scroll like everything else.
    const pitch = descentPitch(deploy);
    if (paused) {
      group.current.rotation.set(pitch, 0, 0);
      return;
    }

    const t = state.clock.elapsedTime;
    // Nose-down through the descent, plus the gentle heave of a body flying on
    // a cable once it is down. The flying motion scales with deploy so a stowed
    // fish sitting in the A-frame is perfectly still.
    group.current.rotation.x = pitch + Math.sin(t * 0.9) * 0.04 * deploy;
    group.current.rotation.y = Math.sin(t * 0.55) * 0.05 * deploy;
    group.current.rotation.z = Math.sin(t * 0.8 + 1.3) * 0.03 * deploy;
  });

  return (
    <group ref={group}>
      <group scale={TOWFISH_DISPLAY_SCALE}>
        <ModelSlot url={TOWFISH_MODEL_URL} fallback={<TowfishPrimitive />} />
      </group>
    </group>
  );
}
