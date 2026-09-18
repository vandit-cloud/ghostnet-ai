/* =============================================================================
 * PARAMS - the single source of truth for the seabed look.
 *
 * House rule, same as the water lab and the map lab (docs/WATER_LAB.md rule 1):
 * every number the look depends on lives HERE, with a range and a label, and
 * tuning means changing this file or the sliders that read it - never editing
 * a shader body. Editing the shader is for changing what a feature IS.
 *
 * The lab's "copy params" button emits this as JSON. Paste an approved pass
 * into APPROVED_SEABED at the bottom to adopt it.
 * ========================================================================== */

export type Param = { v: number; min: number; max: number; step: number; label: string };
export type ParamGroup = Record<string, Param>;

/** Anything in here is a LIVE uniform: moving it re-renders, nothing rebuilds. */
export const PARAMS = {
  /* ------------------------------------------------------------------ §1 FOG
   * The integration fix. `fogMatch` is the A/B lever and the single most
   * important control in this lab: at 0 the props use the shipped
   * THREE.Fog(0x0f4b70, 30, 460), at 1 they use the water's own
   * wavelength-dependent absorption. Drag it and watch the props stop being
   * cutouts. Everything else here is secondary to that one slider. */
  fog: {
    fogMatch:   { v: 1.00, min: 0, max: 1, step: 0.01, label: "absorption match (0=old linear fog)" },
    fogDensity: { v: 0.030, min: 0, max: 0.12, step: 0.001, label: "fog density (match water: 0.030)" },
    absR:       { v: 2.90, min: 0, max: 5, step: 0.05, label: "absorb R (match water: 2.90)" },
    absG:       { v: 1.20, min: 0, max: 5, step: 0.05, label: "absorb G (match water: 1.20)" },
    absB:       { v: 0.60, min: 0, max: 5, step: 0.05, label: "absorb B (match water: 0.60)" },
  },

  /* -------------------------------------------------------------- §2 CAUSTICS
   * The props stand in a pool of moving light and currently receive none of it.
   * These re-project the SAME caustic field the floor uses onto the geometry. */
  caustics: {
    causticGain:   { v: 1.00, min: 0, max: 3, step: 0.01, label: "caustic gain on props" },
    causticUp:     { v: 0.70, min: 0, max: 1, step: 0.01, label: "up-facing bias (0=all faces lit)" },
    causticHFade:  { v: 0.055, min: 0, max: 0.3, step: 0.001, label: "fade per metre above seabed" },
    causticStrength:{ v: 2.39, min: 0, max: 6, step: 0.01, label: "strength (match water: 2.39)" },
    causticSharp:  { v: 14.8, min: 1, max: 30, step: 0.1, label: "sharpness (match water: 14.8)" },
    causticSpeed:  { v: 0.79, min: 0, max: 3, step: 0.01, label: "speed (match water: 0.79)" },
  },

  /* ----------------------------------------------------------- §3 MICRO DETAIL
   * Triplanar FBM into albedo, roughness and a derivative bump. No texture
   * files: this reuses the water shader's own fbm(), so the props are made of
   * the same noise as the seabed they sit on and cannot drift stylistically. */
  detail: {
    detailScale:  { v: 0.90, min: 0.05, max: 6, step: 0.01, label: "detail frequency (cycles/m)" },
    mottleScale:  { v: 0.22, min: 0.01, max: 2, step: 0.01, label: "mottle frequency (large blotches)" },
    mottleAmt:    { v: 0.30, min: 0, max: 1, step: 0.01, label: "albedo mottle depth" },
    bump:         { v: 0.55, min: 0, max: 3, step: 0.01, label: "bump strength (derivative)" },
    roughLo:      { v: 0.72, min: 0, max: 2, step: 0.01, label: "roughness at noise=0" },
    roughHi:      { v: 1.18, min: 0, max: 2, step: 0.01, label: "roughness at noise=1" },
    grimeAmt:     { v: 0.35, min: 0, max: 1, step: 0.01, label: "crevice darkening" },
  },

  /* -------------------------------------------------------------- §4 SEDIMENT
   * Fine silt settling on upward faces. THIS IS THE SECTION THAT MOST DECIDES
   * whether the bottom reads as a working survey site or as clean CG props -
   * see sedimentMask() in underwaterMaterial.ts, which is deliberately left
   * naive and is the thing to improve first. */
  sediment: {
    dustAmt:    { v: 0.55, min: 0, max: 1, step: 0.01, label: "sediment coverage" },
    dustLo:     { v: 0.15, min: -1, max: 1, step: 0.01, label: "normal.y where dust starts" },
    dustHi:     { v: 0.80, min: -1, max: 1, step: 0.01, label: "normal.y where dust is full" },
    dustBreak:  { v: 0.60, min: 0, max: 2, step: 0.01, label: "noise breakup of the dust edge" },
    dustR:      { v: 0.45, min: 0, max: 1, step: 0.01, label: "sediment R (match floor: 0.45)" },
    dustG:      { v: 0.44, min: 0, max: 1, step: 0.01, label: "sediment G (match floor: 0.44)" },
    dustB:      { v: 0.78, min: 0, max: 1, step: 0.01, label: "sediment B (match floor: 0.78)" },
  },

  /* ----------------------------------------------------------------- §5 GRADE
   * The props currently receive no vignette and no grain while the water
   * around them receives both. Joining them to the same screen-space grade is
   * cheap and removes a "pasted on" cue that survives even at close range. */
  grade: {
    gradeMatch: { v: 1.00, min: 0, max: 1, step: 0.01, label: "join props to water grade" },
    vignette:   { v: 0.45, min: 0, max: 1, step: 0.01, label: "vignette (match water: 0.45)" },
    grain:      { v: 0.012, min: 0, max: 0.08, step: 0.001, label: "grain (match water: 0.012)" },
  },
} satisfies Record<string, ParamGroup>;

/** ---------------------------------------------------------------------------
 * REBUILD params. Changing one of these rebuilds geometry or re-seeds the
 * scatter, which is why they are separate: they cannot be live uniforms, and
 * dragging them is not free.
 * ------------------------------------------------------------------------- */
export const BUILD = {
  /* Tessellation. The shipped hero uses IcosahedronGeometry(1, 0) - detail 0,
     TWENTY faces. That is a d20, and at the scale these render it reads as one.
     Detail 2 is 320 faces; under InstancedMesh the whole rubble field is still
     a single draw call, so this is close to free. */
  rockDetail:   { v: 2, min: 0, max: 3, step: 1, label: "rock subdivision (shipped: 0)" },
  headDetail:   { v: 2, min: 0, max: 3, step: 1, label: "coral head subdivision" },
  branchRadial: { v: 7, min: 3, max: 16, step: 1, label: "coral branch sides (shipped: 5)" },
  slabBevel:    { v: 1, min: 0, max: 1, step: 1, label: "bevel + jitter the slabs (shipped: 0)" },

  /* Per-instance variation. All 58 rocks currently ship the exact same
     0x6b6f66. InstancedMesh has had setColorAt() since r125 and it costs one
     extra buffer, so a clone army is a choice, not a constraint. */
  hueJitter:   { v: 0.045, min: 0, max: 0.3, step: 0.005, label: "per-instance hue spread" },
  valueJitter: { v: 0.22, min: 0, max: 1, step: 0.01, label: "per-instance value spread" },
} satisfies ParamGroup;

/** Flatten a group set into the plain {key: number} the uniforms want. */
export function flatten(groups: Record<string, ParamGroup>): Record<string, number> {
  const out: Record<string, number> = {};
  for (const g of Object.values(groups)) for (const [k, p] of Object.entries(g)) out[k] = p.v;
  return out;
}

/** Paste an approved tuning pass here. Empty = the defaults above are current. */
export const APPROVED_SEABED: Record<string, number> = {};
