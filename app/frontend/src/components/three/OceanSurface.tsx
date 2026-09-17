"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

// Two summed sine waves, differentiated ANALYTICALLY (dHeight/dx, dHeight/dy)
// to build a real per-fragment normal instead of only a height-based color
// band. Height-band-only shading is why the old surface read as a flat
// painted grid rather than water: it had no normal, so it could not catch
// light or reflect anything -- every wave crest was just a slightly
// different flat color, which aliases into a checkerboard at a shallow
// viewing angle.
//
// uWaveScale re-tunes wavelength/amplitude together (see the JS side below)
// so the wave pattern stays resolvable by this mesh's FIXED subdivision
// count regardless of how large `size` is. Without it, a survey-scaled
// plane (tens of thousands of units, for a real multi-km survey line) packs
// several wave cycles into a single grid cell -- the mesh can't resolve
// them, so they average into a flat gradient. Scaling wavelength up (and
// amplitude to match, so the slope/normal magnitude is unchanged) keeps the
// same visual "choppiness" the small login/hero-page ocean already has.
const vertexShader = `
  uniform float uTime;
  uniform float uWaveScale;
  varying vec3 vNormal;
  varying vec3 vWorldPosition;

  const float A1 = 1.1;
  const float F1 = 0.02;
  const float S1 = 0.6;
  const float A2 = 0.7;
  const float F2 = 0.035;
  const float S2 = 0.4;

  void main() {
    vec3 pos = position;
    float f1 = F1 / uWaveScale;
    float f2 = F2 / uWaveScale;
    float a1 = A1 * uWaveScale;
    float a2 = A2 * uWaveScale;

    float phase1 = pos.x * f1 + uTime * S1;
    float phase2 = pos.y * f2 + uTime * S2;
    float wave = sin(phase1) * a1 + sin(phase2) * a2;
    pos.z += wave;

    // a*f cancels uWaveScale exactly, so the slope (and therefore the
    // lighting/specular character) stays the same regardless of scale --
    // only the wavelength and height visibly change.
    float dHdx = cos(phase1) * a1 * f1;
    float dHdy = cos(phase2) * a2 * f2;
    // Pre-rotation local up is +Z (the mesh is rotated flat in Scene3D), so
    // the slope terms go in x/y and the "up" component stays dominant for a
    // gentle sea rather than a jagged one.
    vec3 localNormal = normalize(vec3(-dHdx, -dHdy, 1.0));
    vNormal = normalize(normalMatrix * localNormal);

    vec4 worldPos = modelMatrix * vec4(pos, 1.0);
    vWorldPosition = worldPos.xyz;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
  }
`;

// Real water shading: a deep base tint, a Fresnel term that brightens toward
// the horizon/grazing angles (why real water looks pale near the edges of a
// view and dark looking straight down), a tight specular sun glint, and a
// manual distance fade to the same fog colour the rest of the scene fades
// to -- not three.js's built-in fog chunks, which assume internal variable
// names (`mvPosition`) this fully custom shader never defines.
// cameraPosition is one of three.js's automatically-supplied uniforms for
// any non-raw ShaderMaterial.
const fragmentShader = `
  uniform float uOpacity;
  uniform vec3 uSunDirection;
  uniform vec3 uFogColor;
  uniform float uFogNear;
  uniform float uFogFar;
  varying vec3 vNormal;
  varying vec3 vWorldPosition;

  void main() {
    vec3 deep = vec3(0.016, 0.05, 0.075);
    vec3 shallow = vec3(0.04, 0.15, 0.19);
    vec3 skyReflection = vec3(0.35, 0.55, 0.62);

    vec3 normal = normalize(vNormal);
    vec3 toCamera = cameraPosition - vWorldPosition;
    float camDist = length(toCamera);
    vec3 viewDir = toCamera / max(camDist, 0.0001);

    float fresnel = pow(1.0 - clamp(dot(normal, viewDir), 0.0, 1.0), 3.0);
    vec3 base = mix(deep, shallow, clamp(normal.y * 1.4 - 0.4, 0.0, 1.0));
    vec3 color = mix(base, skyReflection, fresnel * 0.55);

    vec3 halfVec = normalize(uSunDirection + viewDir);
    float specular = pow(max(dot(normal, halfVec), 0.0), 120.0);
    color += vec3(0.8, 0.92, 0.95) * specular * 0.8;

    float fogFactor = clamp((camDist - uFogNear) / max(uFogFar - uFogNear, 0.0001), 0.0, 1.0);
    color = mix(color, uFogColor, fogFactor);

    gl_FragColor = vec4(color, uOpacity);
  }
`;

// The wavelength/amplitude/mesh-density combination the login/hero pages
// already look good at -- everything else is scaled relative to this.
const REFERENCE_SIZE = 1500;

/** Ambient (Level 1) ocean motion only - a lightweight vertex-displacement
 * shader, not a physically simulated ocean. Pauses cleanly when `paused`.
 * `speed`/`opacity`/`y` let a second, faster/dimmer layer be stacked above
 * the base surface for a depth-parallax feel (e.g. the login background)
 * without duplicating the shader.
 *
 * `fogNear`/`fogFar`/`fogColor` should match whatever `<fog>` the parent
 * scene declares (Scene3D computes these from the survey's extent) -- this
 * shader can't read scene fog automatically since it's fully custom, so the
 * distance fade is computed by hand from the same numbers. */
export function OceanSurface({
  paused,
  size = 2400,
  speed = 1,
  opacity = 1,
  y = 0,
  fogNear = 600,
  fogFar = 5280,
  fogColor = "#072639",
}: {
  paused: boolean;
  size?: number;
  speed?: number;
  opacity?: number;
  y?: number;
  fogNear?: number;
  fogFar?: number;
  fogColor?: string;
}) {
  const materialRef = useRef<THREE.ShaderMaterial>(null);
  const waveScale = Math.max(1, size / REFERENCE_SIZE);
  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uOpacity: { value: opacity },
      uSunDirection: { value: new THREE.Vector3(0.35, 0.65, 0.4).normalize() },
      uFogColor: { value: new THREE.Color(fogColor) },
      uFogNear: { value: fogNear },
      uFogFar: { value: fogFar },
      uWaveScale: { value: waveScale },
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }),
    [opacity]
  );

  useFrame((_, delta) => {
    if (paused) return;
    if (materialRef.current) {
      materialRef.current.uniforms.uTime.value += delta * speed;
    }
  });

  if (materialRef.current) {
    materialRef.current.uniforms.uFogNear.value = fogNear;
    materialRef.current.uniforms.uFogFar.value = fogFar;
    materialRef.current.uniforms.uFogColor.value.set(fogColor);
    materialRef.current.uniforms.uWaveScale.value = waveScale;
  }

  return (
    <mesh position={[0, y, 0]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow={false}>
      <planeGeometry args={[size, size, 160, 160]} />
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
