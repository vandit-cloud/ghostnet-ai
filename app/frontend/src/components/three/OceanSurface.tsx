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
  /* Peak wave amplitude, in world units.
   *
   * This used to be A1 * uWaveScale -- i.e. the wave HEIGHT scaled with the
   * plane's size along with its wavelength. That is right for a scene where
   * everything is sized off the survey extent, and badly wrong for one
   * containing an object of a known real size. A 9000-unit plane (needed to
   * reach the horizon) gives uWaveScale 6 and so a 10.8 m swell, which is
   * taller than a 28 m survey vessel's freeboard: the water simply closes over
   * the hull. Amplitude is therefore its own uniform now, defaulting to the
   * old expression so every existing caller is unaffected. */
  uniform float uWaveAmp;
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
    // The two components keep their original 1.1 : 0.7 ratio, so the wave
    // SHAPE is untouched and only its height changes.
    float a1 = (A1 / (A1 + A2)) * uWaveAmp;
    float a2 = (A2 / (A1 + A2)) * uWaveAmp;

    float phase1 = pos.x * f1 + uTime * S1;
    float phase2 = pos.y * f2 + uTime * S2;
    float wave = sin(phase1) * a1 + sin(phase2) * a2;
    pos.z += wave;

    // The analytic slope. At the default amplitude a*f still cancels
    // uWaveScale exactly, so the lighting character is unchanged for existing
    // callers; a caller that calms the water gets a correspondingly gentler
    // slope, which is what makes calm water read as calm rather than as the
    // same choppy normal map on a flatter surface.
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
  /* The three water tones, promoted from shader constants to uniforms.
   *
   * They were tuned for the survey view's dusk mood, and they are the right
   * default -- every existing caller gets exactly the values it had. But the
   * plate lab needs the same water under a bright midday sun, and the
   * alternative to exposing these was a second copy of the shader, which is
   * how two oceans drift apart. Defaults preserve the old look byte for byte;
   * see the prop defaults below. */
  uniform vec3 uDeepColor;
  uniform vec3 uShallowColor;
  uniform vec3 uSkyColor;
  uniform vec3 uFogColor;
  uniform float uFogNear;
  uniform float uFogFar;
  varying vec3 vNormal;
  varying vec3 vWorldPosition;

  void main() {
    vec3 deep = uDeepColor;
    vec3 shallow = uShallowColor;
    vec3 skyReflection = uSkyColor;

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

/** A colour built from values that are ALREADY linear, bypassing the sRGB
 *  decode `new THREE.Color(hex)` would apply. */
function linear(r: number, g: number, b: number): THREE.Color {
  return new THREE.Color().setRGB(r, g, b, THREE.LinearSRGBColorSpace);
}

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
  deepColor,
  shallowColor,
  skyColor,
  sunDirection,
  waveHeight,
}: {
  paused: boolean;
  size?: number;
  speed?: number;
  opacity?: number;
  y?: number;
  fogNear?: number;
  fogFar?: number;
  fogColor?: string;
  /** Water body tones. Default to the survey view's dusk palette. */
  deepColor?: string;
  shallowColor?: string;
  skyColor?: string;
  /** Where the sun is, for the specular glint. Defaults to the existing
   *  over-the-right-shoulder direction. */
  sunDirection?: [number, number, number];
  /** Peak wave amplitude in world units. Defaults to the historical
   *  size-scaled height (1.8 * size / 1500), which is what every caller that
   *  omits it has always rendered. Pass an absolute value when the scene
   *  contains something of a known real size -- a hull, a marker -- that the
   *  waves must not swallow. */
  waveHeight?: number;
}) {
  const materialRef = useRef<THREE.ShaderMaterial>(null);
  const waveScale = Math.max(1, size / REFERENCE_SIZE);
  // 1.8 is A1 + A2 from the shader: the old `A1*scale + A2*scale` peak.
  const waveAmp = waveHeight ?? 1.8 * waveScale;
  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uOpacity: { value: opacity },
      /* Seeded here, not in the render body below, for the same reason the
       * colours are: that block runs during render and materialRef is null on
       * the first one, so a value written only there is dropped until some
       * later prop change happens to re-render. The default is the shader's
       * original over-the-right-shoulder sun. */
      uSunDirection: {
        value: sunDirection
          ? new THREE.Vector3(...sunDirection).normalize()
          : new THREE.Vector3(0.35, 0.65, 0.4).normalize(),
      },
      /* Seeded with the shader's ORIGINAL literals, and seeded in LINEAR
       * space on purpose.
       *
       * Those literals were raw vec3s in the fragment shader, i.e. already
       * linear working-space values. Writing them back as `new THREE.Color
       * ("#040D13")` would round-trip them through sRGB decoding and land
       * roughly a factor of ten darker -- a silent regression on the login
       * page and the 3D survey view, neither of which passes these props.
       * A caller that DOES pass a hex gets the normal sRGB interpretation,
       * which is what anyone writing "#2E9BE0" expects. */
      uDeepColor: { value: deepColor ? new THREE.Color(deepColor) : linear(0.016, 0.05, 0.075) },
      uShallowColor: { value: shallowColor ? new THREE.Color(shallowColor) : linear(0.04, 0.15, 0.19) },
      uSkyColor: { value: skyColor ? new THREE.Color(skyColor) : linear(0.35, 0.55, 0.62) },
      // eslint-disable-next-line react-hooks/exhaustive-deps
      uFogColor: { value: new THREE.Color(fogColor) },
      uFogNear: { value: fogNear },
      uFogFar: { value: fogFar },
      uWaveScale: { value: waveScale },
      uWaveAmp: { value: waveAmp },
    }),
    /* fogColor/fogNear/fogFar/waveScale/waveAmp are deliberately NOT deps.
     * This memo SEEDS the uniform objects once; those five are then kept in
     * sync every render by the block below, which is safe for them precisely
     * because they are prop-driven (a change to one re-renders the component).
     * Adding them here would rebuild every uniform object and hand the
     * material a new `uniforms` identity on every fog tweak, forcing a shader
     * recompile mid-scene. */
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [opacity, deepColor, shallowColor, skyColor, sunDirection]
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
    materialRef.current.uniforms.uWaveAmp.value = waveAmp;
    /* The colours are resolved in the useMemo above, not here.
     *
     * This block runs during RENDER, and a react-three-fiber scene re-renders
     * only when React props change -- useFrame does not. So a uniform written
     * only from here is written once, at mount, when materialRef is still
     * null, and every later value is silently dropped. That is exactly how the
     * daylight water tones appeared to have no effect: they were being set on
     * a ref that did not exist yet. The fog values below survive because
     * Scene3D re-renders them as props. */
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
