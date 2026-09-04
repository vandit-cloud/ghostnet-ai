"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

const vertexShader = `
  uniform float uTime;
  varying float vElevation;
  void main() {
    vec3 pos = position;
    float wave = sin(pos.x * 0.02 + uTime * 0.6) * 1.1 + sin(pos.y * 0.035 + uTime * 0.4) * 0.7;
    pos.z += wave;
    vElevation = wave;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
  }
`;

const fragmentShader = `
  uniform float uOpacity;
  varying float vElevation;
  void main() {
    vec3 deep = vec3(0.015, 0.05, 0.08);
    vec3 shallow = vec3(0.05, 0.19, 0.24);
    vec3 crest = vec3(0.08, 0.35, 0.42);
    float t = clamp((vElevation + 1.8) / 3.6, 0.0, 1.0);
    vec3 base = mix(deep, shallow, t);
    float highlight = smoothstep(0.78, 1.0, t);
    gl_FragColor = vec4(mix(base, crest, highlight * 0.5), uOpacity);
  }
`;

/** Ambient (Level 1) ocean motion only - a lightweight vertex-displacement
 * shader, not a physically simulated ocean. Pauses cleanly when `paused`.
 * `speed`/`opacity`/`y` let a second, faster/dimmer layer be stacked above
 * the base surface for a depth-parallax feel (e.g. the login background)
 * without duplicating the shader. */
export function OceanSurface({
  paused,
  size = 2400,
  speed = 1,
  opacity = 1,
  y = 0,
}: {
  paused: boolean;
  size?: number;
  speed?: number;
  opacity?: number;
  y?: number;
}) {
  const materialRef = useRef<THREE.ShaderMaterial>(null);
  const uniforms = useMemo(() => ({ uTime: { value: 0 }, uOpacity: { value: opacity } }), [opacity]);

  useFrame((_, delta) => {
    if (paused) return;
    if (materialRef.current) {
      materialRef.current.uniforms.uTime.value += delta * speed;
    }
  });

  return (
    <mesh position={[0, y, 0]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow={false}>
      <planeGeometry args={[size, size, 96, 96]} />
      <shaderMaterial
        ref={materialRef}
        uniforms={uniforms}
        vertexShader={vertexShader}
        fragmentShader={fragmentShader}
        transparent={opacity < 1}
      />
    </mesh>
  );
}
