"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

import { SURVEY_SPEED } from "@/components/three/hero/stages";

/** Suspended particulate drifting astern - "marine snow".
 *
 * This is the component that makes the vessel look like it is making way.
 *
 * The problem it solves: at an honest 2 m/s, nothing in the far field visibly
 * moves. A 400 m swath takes three minutes to pass. The instinct is to speed
 * the seabed up, but a fast-scrolling floor under a fixed boat is precisely
 * what reads as a treadmill - the eye knows those two things disagree.
 *
 * Real underwater footage solves it the same way this does: forward motion is
 * read from PARALLAX in the near field. Particles a few metres from the lens
 * sweep across the frame while the seabed a hundred metres down barely creeps,
 * and both are moving at the same speed. Getting that ratio right is the whole
 * trick, so the drift rate here is SURVEY_SPEED - the same constant the sonar
 * waterfall uses - and never a tuned-by-eye number.
 *
 * It also fills the empty water, which is the other half of why the scene reads
 * as a void: clear water has no depth cues at all.
 */

const COUNT = 700;

/** The volume the particles live in, centred on the tow path. Particles that
 * leave the aft face are recycled to the forward face, so the field is
 * effectively infinite for the cost of 700 points. */
const FIELD = { width: 190, height: 100, depth: 300 };

export function MarineSnow({
  center,
  opacity,
  paused,
}: {
  /** Centre of the particle volume, normally the midpoint of the tow path. */
  center: [number, number, number];
  /** Faded in as the camera goes under - there is no marine snow in the air. */
  opacity: number;
  paused: boolean;
}) {
  const points = useRef<THREE.Points>(null);
  const material = useRef<THREE.PointsMaterial>(null);

  const geometry = useMemo(() => {
    const positions = new Float32Array(COUNT * 3);
    const sizes = new Float32Array(COUNT);
    for (let i = 0; i < COUNT; i += 1) {
      positions[i * 3] = (Math.random() - 0.5) * FIELD.width;
      positions[i * 3 + 1] = (Math.random() - 0.5) * FIELD.height;
      positions[i * 3 + 2] = (Math.random() - 0.5) * FIELD.depth;
      sizes[i] = 0.05 + Math.random() * 0.22;
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    g.setAttribute("size", new THREE.BufferAttribute(sizes, 1));
    return g;
  }, []);

  /** A soft round dot. Default square points are the single clearest tell that
   * a scene is a WebGL demo rather than a camera. */
  const sprite = useMemo(() => {
    const size = 64;
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = size;
    const ctx = canvas.getContext("2d");
    if (ctx) {
      const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
      g.addColorStop(0, "rgba(255,255,255,1)");
      g.addColorStop(0.35, "rgba(210,240,255,0.55)");
      g.addColorStop(1, "rgba(160,210,235,0)");
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, size, size);
    }
    const tex = new THREE.CanvasTexture(canvas);
    tex.needsUpdate = true;
    return tex;
  }, []);

  useFrame((_, delta) => {
    if (material.current) {
      material.current.opacity = opacity * 0.55;
      material.current.visible = opacity > 0.01;
    }
    if (paused || !points.current || opacity <= 0.01) return;

    const attr = points.current.geometry.getAttribute("position") as THREE.BufferAttribute;
    const arr = attr.array as Float32Array;
    const half = FIELD.depth / 2;
    // Astern is +Z: the water is standing still and the rig is moving through
    // it, so relative to the vessel every particle travels aft at survey speed.
    const step = SURVEY_SPEED * delta;

    for (let i = 0; i < COUNT; i += 1) {
      const zi = i * 3 + 2;
      arr[zi] += step;
      if (arr[zi] > half) {
        arr[zi] -= FIELD.depth;
        // Re-randomise across-track on recycle so the field never develops
        // visible lanes the eye can latch onto.
        arr[i * 3] = (Math.random() - 0.5) * FIELD.width;
        arr[i * 3 + 1] = (Math.random() - 0.5) * FIELD.height;
      }
    }
    attr.needsUpdate = true;
  });

  return (
    <points ref={points} geometry={geometry} position={center}>
      <pointsMaterial
        ref={material}
        map={sprite}
        size={0.55}
        sizeAttenuation
        transparent
        opacity={0}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
        color="#a8dcef"
      />
    </points>
  );
}
