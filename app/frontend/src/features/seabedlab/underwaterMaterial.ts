import * as THREE from "three";

import { APPROVED_OPTICS, GLSL_OPTICS_PRELUDE } from "./optics";

/* =============================================================================
 * patchUnderwater() - joins a MeshStandardMaterial to the water it sits in.
 *
 * THE PROBLEM THIS SOLVES.
 * The hero renders two things with two completely different optical models and
 * composites them in one frame:
 *
 *   the water + seabed   a raymarched fragment shader with wavelength-dependent
 *                        absorption, caustics, and its own display-space grade
 *   the props on it      MeshStandardMaterial, THREE.Fog, ACES, no caustics,
 *                        no vignette, no grain
 *
 * At 80 m the shader has absorbed 99% of red out of the background while the
 * linear fog has faded the props by 12% toward a flat navy. The rocks are not
 * "low poly looking" so much as they are LIT BY A DIFFERENT OCEAN. This patch
 * makes them share one.
 *
 * WHY onBeforeCompile AND NOT A CUSTOM ShaderMaterial.
 * Rewriting these as raw shaders would mean reimplementing three's lighting,
 * shadows, instancing and env maps, and the props genuinely need all four. The
 * chunk hooks let the standard material keep doing that work while we change
 * only the five places where it disagrees with the water.
 *
 * COLOUR SPACE IS THE WHOLE TRICK - see optics.ts. The water writes display
 * values directly; the props go linear -> ACES -> sRGB. So the fog and the
 * grade are injected AFTER <colorspace_fragment>, which is the only point in
 * the pipeline where the two are speaking the same units.
 * ========================================================================== */

export type UnderwaterUniforms = {
  uTime: THREE.IUniform<number>;
  uEyeDepth: THREE.IUniform<number>;
  uSeabedY: THREE.IUniform<number>;
  uRes: THREE.IUniform<THREE.Vector2>;
  uLinearFogColor: THREE.IUniform<THREE.Color>;
  [k: string]: THREE.IUniform<unknown>;
};

/** The live-tunable set, mirrored from PARAMS. Names match 1:1 so the lab can
 *  write straight through from a slider to a uniform with no mapping table. */
const TUNABLE = [
  "fogMatch", "fogDensity", "absR", "absG", "absB",
  "causticGain", "causticUp", "causticHFade",
  "causticStrength", "causticSharp", "causticSpeed",
  "detailScale", "mottleScale", "mottleAmt", "bump", "roughLo", "roughHi", "grimeAmt",
  "dustAmt", "dustLo", "dustHi", "dustBreak", "dustR", "dustG", "dustB",
  "gradeMatch", "vignette", "grain",
] as const;

/** The shipped fog, reproduced exactly so the A/B is honest.
 *
 *  NOTE: three uploads scene.fog.color through colour management, so the
 *  0x0f4b70 in scene.ts is LINEARISED before it reaches the shader - and then
 *  mixed into an image that has already been sRGB-encoded, because
 *  <fog_fragment> sits after <colorspace_fragment>. The shipped fog therefore
 *  renders far darker than the hex suggests. That is reproduced here rather
 *  than corrected: the point of the 0 end of the fogMatch slider is to show
 *  what is on the site today, not an improved version of it. */
export const SHIPPED_FOG = { color: 0x0f4b70, near: 30, far: 460 } as const;

export function makeUnderwaterUniforms(values: Record<string, number>): UnderwaterUniforms {
  const u = {
    uTime: { value: 0 },
    uEyeDepth: { value: 16 },
    uSeabedY: { value: -APPROVED_OPTICS.seabedDepth },
    uRes: { value: new THREE.Vector2(1, 1) },
    uLinearFogColor: { value: new THREE.Color(SHIPPED_FOG.color).convertSRGBToLinear() },
    uFogNear: { value: SHIPPED_FOG.near },
    uFogFar: { value: SHIPPED_FOG.far },
    floorScale: { value: APPROVED_OPTICS.floorScale },
    causticBeat: { value: APPROVED_OPTICS.causticBeat },
    causticFade: { value: APPROVED_OPTICS.causticFade },
    quality: { value: APPROVED_OPTICS.quality },
  } as unknown as UnderwaterUniforms;

  for (const k of TUNABLE) u[k] = { value: values[k] ?? 0 };
  return u;
}

/* ---------------------------------------------------------------------------
 * The injected GLSL.
 * ------------------------------------------------------------------------- */

const FRAG_PRELUDE = /* glsl */ `
varying vec3 vWPos;
varying vec3 vWNrm;

uniform float uTime, uEyeDepth, uSeabedY, uFogNear, uFogFar;
uniform vec2  uRes;
uniform vec3  uLinearFogColor;
uniform float floorScale, causticBeat, causticFade, quality;
uniform float fogMatch, fogDensity, absR, absG, absB;
uniform float causticGain, causticUp, causticHFade;
uniform float causticStrength, causticSharp, causticSpeed;
uniform float detailScale, mottleScale, mottleAmt, bump, roughLo, roughHi, grimeAmt;
uniform float dustAmt, dustLo, dustHi, dustBreak, dustR, dustG, dustB;
uniform float gradeMatch, vignette, grain;

${GLSL_OPTICS_PRELUDE}

/* Triplanar FBM. The props have no useful UVs - they are instanced primitives,
   and a sphere's UVs pinch at the poles while a lumpy icosahedron has none
   worth the name - so the noise is projected from world space on three axes and
   blended by the normal. The pow(w,4) sharpens the blend so the three
   projections do not cross-fade into mush on a 45 degree face. */
float triFbm(vec3 p, vec3 n){
  vec3 w = abs(n); w = pow(w, vec3(4.0)); w /= max(w.x+w.y+w.z, 1e-4);
  return fbm(p.yz)*w.x + fbm(p.xz)*w.y + fbm(p.xy)*w.z;
}

/* ===========================================================================
 * sedimentMask() - HOW MUCH SILT HAS SETTLED ON THIS PIXEL.
 *
 * >>> THIS IS THE DECISION POINT. The implementation below is deliberately
 * >>> NAIVE and is the first thing to replace - see the note in the chat.
 *
 * 'n' is the world normal, 'detail' is triplanar FBM in 0..1 at this point,
 * 'hAbove' is metres above the seabed plane. Returns 0..1.
 * ======================================================================== */
float sedimentMask(vec3 n, float detail, float hAbove){
  // TODO(you): a clean smoothstep on normal.y alone gives a hard horizontal
  // waterline across every rock - the giveaway of procedural dressing. Break
  // it with 'detail', and consider whether height above the bottom should
  // matter (silt is resuspended near the floor and settles thickest there).
  return smoothstep(dustLo, dustHi, n.y) * dustAmt;
}

/* Mikkelsen surface-gradient bump. Perturbs a normal from a height field
   without tangents - which these instanced primitives do not have and are not
   worth generating for.

   BOTH the normal and the position derivatives must be in the SAME space. The
   normal three hands us here is VIEW space, so the positions are too
   (-vViewPosition); only the height value itself is world-anchored, so the
   detail does not swim across the rock as the camera moves. */
vec3 perturbBump(vec3 n, vec3 vpos, float h, float scale){
  vec3 sx = dFdx(vpos), sy = dFdy(vpos);
  float dhx = dFdx(h), dhy = dFdy(h);
  vec3 R1 = cross(sy, n), R2 = cross(n, sx);
  float det = dot(sx, R1);
  if (abs(det) < 1e-8) return n;
  vec3 grad = sign(det)*(dhx*R1 + dhy*R2);
  return normalize(abs(det)*n - scale*grad);
}
`;

const VERT_PRELUDE = /* glsl */ `
varying vec3 vWPos;
varying vec3 vWNrm;
`;

/* World position and normal, instancing included.
   modelMatrix alone is NOT enough here: three applies instanceMatrix inside
   <project_vertex>, so a naive modelMatrix*position puts every one of the 58
   rocks at the origin of the field and the caustics would not move with them. */
const VERT_BODY = /* glsl */ `
  vec4 uwWorld = vec4(transformed, 1.0);
  vec3 uwNrm = objectNormal;
  #ifdef USE_INSTANCING
    uwWorld = instanceMatrix * uwWorld;
    uwNrm = mat3(instanceMatrix) * uwNrm;
  #endif
  vWPos = (modelMatrix * uwWorld).xyz;
  vWNrm = normalize(mat3(modelMatrix) * uwNrm);
`;

export function patchUnderwater(
  material: THREE.MeshStandardMaterial,
  uniforms: UnderwaterUniforms
): THREE.MeshStandardMaterial {
  /* three's fog is replaced wholesale, not layered on. Leaving it on would mean
     two fogs stacked, and the A/B slider could never reach a clean 0 or 1. */
  material.fog = false;
  material.customProgramCacheKey = () => "ghostnet-underwater-v1";

  material.onBeforeCompile = (shader) => {
    Object.assign(shader.uniforms, uniforms);

    shader.vertexShader = shader.vertexShader
      .replace("#include <common>", `#include <common>\n${VERT_PRELUDE}`)
      .replace("#include <project_vertex>", `#include <project_vertex>\n${VERT_BODY}`);

    shader.fragmentShader = shader.fragmentShader
      .replace("#include <common>", `#include <common>\n${FRAG_PRELUDE}`)

      /* ---- 1. ALBEDO: mottle, crevice grime, settled sediment ------------- */
      .replace(
        "#include <map_fragment>",
        /* glsl */ `#include <map_fragment>
        {
          float uwDetail = triFbm(vWPos*detailScale, vWNrm);
          float uwMottle = triFbm(vWPos*mottleScale, vWNrm);
          float uwH = vWPos.y - uSeabedY;

          // Large blotches: the single flat albedo is most of why 58 identical
          // rocks read as 58 copies of one rock.
          diffuseColor.rgb *= mix(1.0-mottleAmt, 1.0+mottleAmt, uwMottle);

          // Cheap AO proxy: the low ground of the high-frequency field is where
          // dirt collects and light does not reach.
          diffuseColor.rgb *= 1.0 - grimeAmt*(1.0-uwDetail);

          // Silt on top. Matched to the floor colour by default so a dusted
          // face and the sediment behind it are the same material.
          float uwDust = clamp(sedimentMask(vWNrm, uwDetail, uwH), 0.0, 1.0);
          diffuseColor.rgb = mix(diffuseColor.rgb, vec3(dustR,dustG,dustB), uwDust);
        }`
      )

      /* ---- 2. ROUGHNESS: kill the uniform sheen --------------------------- */
      .replace(
        "#include <roughnessmap_fragment>",
        /* glsl */ `#include <roughnessmap_fragment>
        {
          float uwR = triFbm(vWPos*detailScale*1.7, vWNrm);
          roughnessFactor = clamp(roughnessFactor * mix(roughLo, roughHi, uwR), 0.04, 1.0);
        }`
      )

      /* ---- 3. NORMAL: derivative bump from the same field ----------------- */
      .replace(
        "#include <normal_fragment_maps>",
        /* glsl */ `#include <normal_fragment_maps>
        if (bump > 0.001) {
          float uwH = triFbm(vWPos*detailScale*2.3, vWNrm);
          normal = perturbBump(normal, -vViewPosition, uwH, bump*0.06);
        }`
      )

      /* ---- 4. CAUSTICS: the same field the floor uses --------------------- */
      .replace(
        "#include <lights_fragment_end>",
        /* glsl */ `#include <lights_fragment_end>
        if (causticGain > 0.001) {
          /* Identical mapping to the floor (scene.ts: fuv = (p.xz + vec2(53,17))
             * floorScale*0.1). Any deviation and the dapple on a rock slides
             against the dapple on the sand it is sitting on. */
          vec2 uwCuv = (vWPos.xz + vec2(53.0,17.0))*(floorScale*0.1);
          float uwC = caustics(uwCuv, uTime*causticSpeed);

          // Light arrives from above: a vertical face catches a glancing share,
          // an overhang none. causticUp=0 disables the bias entirely.
          float uwUp = mix(1.0, clamp(vWNrm.y*0.5+0.5, 0.0, 1.0), causticUp);

          // Caustics are a focused image of the surface and defocus with
          // distance from the plane they converge on.
          float uwHF = exp(-max(vWPos.y - uSeabedY, 0.0)*causticHFade);

          // Same optical-distance fade the floor applies.
          float uwD = length(vViewPosition);
          float uwFade = mix(1.0, exp(-uwD*0.09), causticFade);

          // Tinted by albedo: caustic light bouncing off a rock is the rock's
          // colour, not white. Added as indirect diffuse so it respects AO.
          reflectedLight.indirectDiffuse +=
            vec3(0.85,0.95,1.0) * uwC * causticStrength * causticGain
            * uwUp * uwHF * uwFade * diffuseColor.rgb;
        }`
      )

      /* ---- 5. FOG + GRADE, in DISPLAY space ------------------------------
       * After <colorspace_fragment> is the ONLY correct place for this. Ahead
       * of it the frame is linear and ACES has not run; the water is neither.
       * ------------------------------------------------------------------ */
      .replace(
        "#include <colorspace_fragment>",
        /* glsl */ `#include <colorspace_fragment>
        {
          float uwDist = length(vViewPosition);

          // (a) what ships today: linear ramp to a flat colour, no wavelength.
          float uwLin = smoothstep(uFogNear, uFogFar, uwDist);
          vec3 uwOld = mix(gl_FragColor.rgb, uLinearFogColor, uwLin);

          // (b) the water's own model: exp(-density * path) per channel.
          vec3 uwNew = absorptionMix(
            gl_FragColor.rgb, waterAt(uEyeDepth), uwDist, fogDensity,
            vec3(absR, absG, absB));

          gl_FragColor.rgb = mix(uwOld, uwNew, fogMatch);

          // The screen-space tail of the water's grade, which the props have
          // never received. Cheap, and it removes a cue that survives even at
          // ranges where the fog difference is invisible.
          if (gradeMatch > 0.001) {
            vec2 uwFrag = gl_FragCoord.xy/uRes;
            vec3 uwG = screenGrade(gl_FragColor.rgb, uwFrag, -uEyeDepth,
                                   vignette, grain, uTime);
            gl_FragColor.rgb = mix(gl_FragColor.rgb, uwG, gradeMatch);
          }
        }`
      );
  };

  material.needsUpdate = true;
  return material;
}
