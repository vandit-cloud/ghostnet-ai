/* =============================================================================
 * THE SHARED OPTICAL MODEL.
 *
 * Everything in here is MIRRORED from the landing hero's water shader
 * (features/landing/hero/scene.ts). It is duplicated, not imported, for one
 * reason: scene.ts builds its whole shader as a local `const FRAG` inside
 * initHero(), so there is nothing to import without refactoring a file that is
 * still marked as a verbatim port. This lab must not touch that file.
 *
 * THE DUPLICATION IS THE POINT OF THE LAB, AND ALSO ITS ONE HAZARD.
 * These values exist here so the lab can render props against the REAL optical
 * model rather than an approximation of it - a fog match judged against
 * approximate fog is worth nothing. But if scene.ts is ever re-tuned and this
 * file is not, the lab starts lying. `npm run lab:check` (scripts/check_optics.py)
 * diffs the two and fails loudly; run it before trusting a tuning session.
 *
 * When this work ports back into the hero, THIS file becomes the source and
 * scene.ts imports from it. Until then: mirror, verify, never diverge.
 * ========================================================================== */

/** ---------------------------------------------------------------------------
 * The subset of scene.ts's APPROVED block that the seabed props need.
 * Copied verbatim from scene.ts:149. Keys match exactly so a diff is mechanical.
 * ------------------------------------------------------------------------- */
export const APPROVED_OPTICS = {
  // --- absorption (spec §20/§22/§24) -----------------------------------------
  // The three multipliers are NORMALISED at use so they shift COLOUR without
  // also raising mean density. Red dies ~4.8x faster than blue, which is the
  // entire reason the hero's water goes blue with distance.
  fogDensity: 0.03,
  absR: 2.9,
  absG: 1.2,
  absB: 0.6,

  // --- seabed / caustics -----------------------------------------------------
  floorScale: 6,
  causticStrength: 2.39,
  causticSharp: 14.8,
  causticSpeed: 0.79,
  causticBeat: 4,
  causticFade: 0.32,

  // --- grade (applied in DISPLAY space, after colour encode) -----------------
  vignette: 0.45,
  grain: 0.012,

  // --- quality gate: 1 enables the third caustic octave ----------------------
  quality: 1,

  // --- geometry of the scene, needed to place the props ----------------------
  seabedDepth: 30,
  camY: 6.75,
} as const;

/** The working camera depth the hero settles at once submerged (scene.ts WORK_Y).
 *  The fog's in-scattered colour is waterAt(eyeDepth), so the lab needs it. */
export const WORK_Y = -16;

/** ---------------------------------------------------------------------------
 * SECTION 1 - NOISE. Verbatim from scene.ts:197-203.
 * Shared helpers, not a look. Do not tune. (docs/WATER_LAB.md rule 1.)
 * ------------------------------------------------------------------------- */
export const GLSL_NOISE = /* glsl */ `
float h21(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7)))*43758.5453); }
float nse(vec2 p){
  vec2 i=floor(p), f=fract(p); f=f*f*(3.0-2.0*f);
  return mix(mix(h21(i),h21(i+vec2(1,0)),f.x), mix(h21(i+vec2(0,1)),h21(i+vec2(1,1)),f.x), f.y);
}
float fbm(vec2 p){ float a=0.5,v=0.0; for(int i=0;i<5;i++){ v+=a*nse(p); p*=2.03; a*=0.5; } return v; }
`;

/** ---------------------------------------------------------------------------
 * SECTION 2 - CAUSTICS. Verbatim from scene.ts.
 * Requires uniforms: causticSharp, causticBeat, quality.
 *
 * Three spatial frequencies at different directions and phases (spec §34), so
 * no single translated layer is legible as a moving texture.
 * ------------------------------------------------------------------------- */
export const GLSL_CAUSTICS = /* glsl */ `
float causticLayer(vec2 p, float t){
  float v = 0.0;
  for (int i=0;i<3;i++){
    float fi=float(i);
    vec2 q = p*(1.0+fi*0.8) + vec2(t*(0.30+fi*0.11), -t*(0.22+fi*0.09));
    v += (1.0-abs(fbm(q)*2.0-1.0))*(1.0-fi*0.22);
  }
  return pow(clamp(v/2.34,0.0,1.0), causticSharp);
}
float caustics(vec2 uv, float t){
  float c  = causticLayer(uv, t);
  c += causticLayer(uv*causticBeat+23.0, -t*0.62)*0.55;
  if (quality > 0.5) c += causticLayer(uv*causticBeat*2.7+71.0, t*0.34)*0.28;
  return c;
}
`;

/** ---------------------------------------------------------------------------
 * The four-band GhostNet depth ramp (spec §23/§25). Verbatim from scene.ts:266.
 *
 * NOTE THE COLOUR SPACE. These are DISPLAY-space values: the water shader
 * writes gl_FragColor straight out with no <colorspace_fragment>, so whatever
 * this returns is what the monitor shows. Anything mixing toward it must
 * therefore also be in display space, or the match is off by a gamma curve.
 * ------------------------------------------------------------------------- */
export const GLSL_WATER_AT = /* glsl */ `
vec3 waterAt(float depthM){
  vec3 c = vec3(0.380,0.600,0.712);
  c = mix(c, vec3(0.059,0.294,0.439), smoothstep( 1.0,27.0,depthM));
  c = mix(c, vec3(0.027,0.166,0.408), smoothstep(17.0,43.0,depthM));
  c = mix(c, vec3(0.004,0.054,0.261), smoothstep(31.0,57.0,depthM));
  return c;
}
`;

/** ---------------------------------------------------------------------------
 * The absorption blend, factored out so the props and the water cannot use two
 * different curves. `path` is the optical path in metres.
 *
 * Normalising `ab` by its own mean is what keeps absR/absG/absB a pure COLOUR
 * control: raise all three and nothing happens, which is the intended
 * behaviour and is why fogDensity stays meaningful. Un-normalised, the three
 * sliders silently re-tune fogDensity behind you (docs/WATER_LAB.md §20).
 * ------------------------------------------------------------------------- */
export const GLSL_ABSORPTION = /* glsl */ `
vec3 absorptionMix(vec3 col, vec3 waterCol, float path, float density, vec3 abIn){
  vec3 ab = abIn;
  ab /= max((ab.r+ab.g+ab.b)/3.0, 1e-4);
  return mix(col, waterCol, clamp(1.0 - exp(-path*density*ab), 0.0, 1.0));
}
`;

/** ---------------------------------------------------------------------------
 * The screen-space tail of SECTION 11 - GRADE, verbatim from scene.ts:427-430.
 *
 * ONLY the vignette and grain, deliberately. The exposure / Reinhard /
 * saturation steps ahead of them shape the water's RAW radiance into display
 * values; the props have already been through ACES and an sRGB encode, so
 * running those again would be a second tonemap on an image that has had one.
 *
 * Vignette and grain are different in kind: they are applied to the finished
 * frame, and the props currently skip them entirely. That is a real part of why
 * they sit proud of the water even at close range where fog is negligible.
 * ------------------------------------------------------------------------- */
export const GLSL_SCREEN_GRADE = /* glsl */ `
vec3 screenGrade(vec3 col, vec2 frag, float camYNow, float vignetteAmt, float grainAmt, float t){
  vec2 vc = (frag-0.5)*vec2(1.06,1.0);
  float vigAmt = mix(0.22, vignetteAmt, clamp(-camYNow/8.0, 0.0, 1.0));
  col *= clamp(1.0 - vigAmt*pow(clamp(length(vc)*1.42,0.0,1.0),2.15), 0.0, 1.0);
  col += (h21(gl_FragCoord.xy + fract(t)) - 0.5)*grainAmt;
  return col;
}
`;

/** Everything a patched material needs, in dependency order. */
export const GLSL_OPTICS_PRELUDE =
  GLSL_NOISE + GLSL_CAUSTICS + GLSL_WATER_AT + GLSL_ABSORPTION + GLSL_SCREEN_GRADE;
