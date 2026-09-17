"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

import { SURVEY_SPEED } from "@/components/three/hero/stages";

const vertexShader = `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

/** The acoustic half of the scene.
 *
 * Side-scan imagery is NOT a top-down photograph - it is a time series. Each
 * ping returns one line of pixels and the image builds row by row as the fish
 * advances, which is why real mosaics have that streaky along-track texture.
 * The other giveaway is the shadow: sound travels outward from the nadir, so a
 * proud object is lit on the side facing the track and throws an ACOUSTIC
 * SHADOW directly away from it. Get the shadow direction right and anyone who
 * has read real sonar will believe the scene; a symmetrical glow reads as
 * generic sci-fi.
 *
 * uNadir is the across-track position of the track line, so shadows are cast
 * away from it on both sides - mirrored, not parallel. */
const fragmentShader = `
  uniform float uScroll;
  uniform float uPaint;
  uniform float uLock;
  varying vec2 vUv;

  float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
  }

  float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x),
               mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x), f.y);
  }

  // Speckle: heavy along-track streaking, fine across-track. Real SSS texture.
  float seafloor(vec2 uv) {
    float n = noise(vec2(uv.x * 26.0, uv.y * 5.0)) * 0.6;
    n += noise(vec2(uv.x * 70.0, uv.y * 12.0)) * 0.3;
    return n;
  }

  // A target plus the shadow it throws away from the track line.
  float target(vec2 uv, vec2 at, float size) {
    float body = 1.0 - smoothstep(0.0, size, distance(uv, at));
    float side = sign(at.x - 0.5);
    vec2 sh = uv - vec2(at.x + side * size * 2.2, at.y);
    sh.x /= 3.0;
    float shadow = 1.0 - smoothstep(0.0, size, length(sh));
    return body - shadow * 0.85;
  }

  void main() {
    // The waterfall scrolls: the image is older the further astern you look.
    // uScroll is in UV units and advances at the real survey speed, so the
    // seabed texture and the marine snow drift past at the same rate.
    vec2 uv = vec2(vUv.x, vUv.y + uScroll);
    float nadir = 1.0 - smoothstep(0.0, 0.06, abs(vUv.x - 0.5));

    float v = seafloor(uv) * 0.5;
    v += target(vUv, vec2(0.30, 0.42), 0.045) * uLock;
    v += target(vUv, vec2(0.72, 0.63), 0.032) * uLock * 0.8;
    v = max(v, 0.0);

    // Ensonified band widens as the survey develops; nothing outside it yet.
    float reach = smoothstep(0.0, 0.55, uPaint);
    float band = smoothstep(0.5 + reach * 0.5, 0.5, abs(vUv.x - 0.5));
    float alpha = v * band * uPaint * (1.0 - nadir * 0.8);

    vec3 cold = vec3(0.03, 0.16, 0.22);
    vec3 hot  = vec3(0.13, 0.83, 0.93);
    gl_FragColor = vec4(mix(cold, hot, clamp(v * 1.6, 0.0, 1.0)), clamp(alpha, 0.0, 1.0));
  }
`;

export function SonarReturns({
  x = 0,
  y,
  paint,
  lock,
  paused,
  width = 240,
  length = 400,
}: {
  /** Across-track position of the TRACK LINE, i.e. the ground beneath the tow
   * path. The shader draws its nadir gap down the centre of this plane, so if
   * this does not sit under the fish the scene shows sonar imagery being
   * painted somewhere the sonar is not. */
  x?: number;
  y: number;
  paint: number;
  lock: number;
  paused: boolean;
  /** Across-track extent in metres - roughly twice the sonar range per side. */
  width?: number;
  /** Along-track extent in metres. The swath is always longer than it is wide. */
  length?: number;
}) {
  const material = useRef<THREE.ShaderMaterial>(null);
  const uniforms = useMemo(
    () => ({ uScroll: { value: 0 }, uPaint: { value: 0 }, uLock: { value: 0 } }),
    []
  );

  useFrame((_, delta) => {
    if (!material.current) return;
    if (!paused) material.current.uniforms.uScroll.value += (delta * SURVEY_SPEED) / length;
    material.current.uniforms.uPaint.value = paint;
    material.current.uniforms.uLock.value = lock;
  });

  return (
    <mesh position={[x, y, 40]} rotation={[-Math.PI / 2, 0, 0]}>
      <planeGeometry args={[width, length]} />
      <shaderMaterial
        ref={material}
        uniforms={uniforms}
        vertexShader={vertexShader}
        fragmentShader={fragmentShader}
        transparent
        depthWrite={false}
      />
    </mesh>
  );
}
