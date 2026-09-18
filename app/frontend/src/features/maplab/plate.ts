/* =============================================================================
 * The survey "plate" — parameters for the 3D reproduction.
 *
 * Single source of truth for docs/SURVEY_MAP_PLATE_SPEC.md. Tuning means
 * changing PARAMS, never editing a component.
 *
 * WHY THIS IS A REAL 3D SCENE AND NOT A DRAWN ONE.
 * The first cut of this lab painted the whole plate onto a 2D canvas: a
 * procedural sea, a procedural hull, and the overlay projected through a
 * hand-fitted pinhole model. It reproduced the reference's geometry and looked
 * synthetic, because every one of those pieces was a second, worse copy of
 * something the project already owns:
 *
 *   water  -> components/three/OceanSurface.tsx  (the real shader, already
 *             used by the 3D survey view and the login page)
 *   vessel -> public/models/vessel.glb via ModelSlot, with the primitive
 *             Vessel.tsx as the documented fallback
 *   camera -> an actual THREE.PerspectiveCamera, so perspective is exact
 *             instead of fitted
 *
 * So the only thing this feature now owns is the OVERLAY: the coverage slabs,
 * the grid, the dashed route, the nodes and the target. That is the part the
 * reference actually contributes, and the part that has to survive the move
 * onto Leaflet and into Scene3D.
 *
 * UNITS. Survey geometry is authored in SWATH WIDTHS and multiplied by
 * `SWATH_M` on the way into the scene. World axes follow the project's
 * convention (Scene3D, Vessel.tsx): +X starboard, +Y up, bow toward -Z, so
 * "along-track, away from the camera" is -Z.
 * ========================================================================== */

/** Survey space. `u` across-track (+starboard), `v` along-track (+away). */
export interface SurveyPoint {
  u: number;
  v: number;
}

/** One swath width, in metres. 75 m per side is a mid-range side-scan setting.
 *
 * This single number sets the whole composition, and it is worth recording why
 * it is the one to reach for. When the frame reads wrong -- "the boat looks
 * like a toy" -- the instinct is to scale the hull. That is always the wrong
 * move here: vessel.glb measures exactly 28.00 units, so it is the ONE object
 * in the scene with a known real size, which makes it the scale reference for
 * everything else rather than a thing to be adjusted. What was actually wrong
 * was the survey around it: too wide, and the pattern runs past the horizon
 * leaving the hull as the only small object in an empty frame; too narrow, and
 * the legs collapse into a strip. 150 m is the value that keeps the whole
 * pattern legible from the camera in PARAMS.camera. See also §14 of the spec:
 * no single value reproduces the reference's framing, and that is a property
 * of the reference, not of this number. */
export const SWATH_M = 150;

/** Which parts of the plate are drawn.
 *
 * Lives here, not in PlateScene, on purpose: the lab page needs the type and
 * the defaults at module scope, and importing them from PlateScene would pull
 * three/fiber/drei into the page chunk and defeat that component's own
 * `dynamic(..., { ssr: false })`. plate.ts is plain data with no imports. */
export interface PlateLayers {
  water: boolean;
  detections: boolean;
  vessel: boolean;
  wake: boolean;
  swath: boolean;
  grid: boolean;
  edges: boolean;
  route: boolean;
  nodes: boolean;
  target: boolean;
}

export const DEFAULT_LAYERS: PlateLayers = {
  water: true,
  detections: true,
  vessel: true,
  wake: true,
  swath: true,
  grid: true,
  edges: true,
  route: true,
  nodes: true,
  target: true,
};

export const PARAMS = {
  /* ---- camera -------------------------------------------------------------
   * Derived from the reference, then expressed as something a real camera can
   * do. Two measurements fix it:
   *
   *   horizon at fy 0.076  -> the view centre sits (0.5 - 0.076) of the frame
   *                           below the horizon, so pitch = 0.424 * fov
   *   vessel  at fy 0.755  -> the vessel is 0.255 of the frame below centre,
   *                           which with that pitch puts the camera ~150 m up
   *                           and ~285 m astern
   *
   * At that distance a 28 m hull (HERO_VESSEL_MODEL_BRIEF.md) occupies about
   * 11% of frame height against the reference's 15% -- close, and the rest is
   * the reference's slightly longer lens. Do NOT close the gap by scaling the
   * model: the vessel is the only object in the scene with a known real size,
   * so it is the scale reference for everything else. Change the lens instead.
   */
  camera: {
    fov: 42, // matches Scene3D, so the two views read as the same lens
    height: 150, // metres above the waterline
    astern: 285, // metres behind the vessel
    pitchDeg: -17.8, // 0.424 * fov, which lands the horizon at fy 0.076
    near: 1,
    far: 6000,
  },

  /* ---- survey layout ------------------------------------------------------
   * Boustrophedon (lawnmower): parallel traverses joined by 180° turns at
   * alternating ends. All in swath widths; multiply by SWATH_M for metres.
   *
   * `legSpacing` is deliberately SMALLER than 1.0 -- 0.85, a 15% overlap
   * between adjacent swaths. That overlap is why the coverage reads as one
   * sheet instead of stripes, and it is also correct survey practice: you plan
   * overlap so each pass's nadir gap is covered by its neighbour. */
  survey: {
    legs: 6,
    legSpacing: 0.85, // 128 m between traverse centrelines
    outboundV: 1.73, // 260 m out before the first turn
    sternTrail: 1.2, // 180 m of already-scanned water BEHIND the vessel, so
    // the coverage runs off the bottom of frame instead of
    // ending in a hard line under the hull. The vessel sits
    // inside its own coverage, which is what a towed sonar
    // actually produces.
    legHalfLen: 2.2, // 330 m half-traverse
    legTaper: 0.94, // each leg out is 6% shorter: the area of interest is a
    // wedge, not a rectangle. A perfect rectangle of legs is
    // the classic synthetic-looking failure.
    legDrift: 0.05, // each leg's centre walks +u, so the pattern leans the way
    // the reference's does
    turnRadius: 0.62, // MUST exceed 0.5 (half a swath) or the coverage's inner
    // offset edge folds back through itself and throws a
    // chevron at every turn
    turnOvershoot: 0.13,
    swathWidthM: SWATH_M,
  },

  /* ---- coverage slabs -----------------------------------------------------
   * THE FORM: flat, mitred, hard-edged quads laid along the route -- not a
   * smooth swept corridor. This is the reference's own construction, chosen
   * deliberately over the swept ribbon: crisper at small map sizes, and it is
   * what the plate reads as.
   *
   * `slabStep` is the facet size in swath widths, and it doubles as the
   * across-track "ping line" spacing, because in a slab rendering those are
   * the same edge.
   *
   * `mitreLimit` caps the spike at a sharp join. Uncapped, a near-180° corner
   * projects its mitred offset point toward infinity and the quad fires off
   * the edge of the world; at the cap the join degrades to a bevel, which is
   * what the reference's turns actually show. */
  swath: {
    slabStep: 0.12,
    mitreLimit: 2.0,
    color: "#2E9BE0", // --sky lifted toward --atlantic; the one derived hue
    opacity: 0.3,
    opacityStern: 0.42, // the slabs in the wake are the brightest: they are the
    // part being acquired RIGHT NOW, and saying so is the
    // whole point of anchoring the coverage to the vessel
    edgeColor: "#7FD4FF",
    edgeOpacity: 0.55,
    /** Metres above the waterline. Small but non-zero: coplanar with the ocean
     *  mesh it z-fights, and the fight is worst at distance where the depth
     *  buffer has least precision -- exactly where the far legs are. */
    y: 0.6,
  },

  /* ---- the survey grid inside the slabs ------------------------------------
   * What makes the coverage read as SURVEY DATA rather than as a coloured
   * highlighter stroke. Built from the same mitred vertices as the slabs, so
   * it converges with them through every turn. */
  grid: {
    color: "#C4F8FF", // --sky, exactly
    opacity: 0.10,
    across: 16, // along-track lines, i.e. divisions across the swath
    edgeFade: 0.08, // outermost divisions dropped, so the grid never touches
    // the bright outer edge
    y: 0.9,
  },

  /* ---- route line ---------------------------------------------------------
   * The dash is what makes this read as a PLAN rather than a path already
   * travelled. */
  line: {
    color: "#EAF9FF", // --paper, cooled
    dash: 16, // metres
    gap: 10,
    halfWidth: 0.9, // metres. WebGL ignores `linewidth` on virtually every
    // platform, so the line is a thin ribbon mesh laid on the
    // water, not a THREE.Line -- which also means it takes
    // perspective correctly instead of staying 1px at range.
    y: 1.4,
  },

  /* ---- waypoint nodes -----------------------------------------------------
   * Two sizes, and the distinction is SEMANTIC, not decorative: a turn node is
   * a commitment (the vessel changes heading), a tick is just a time mark.
   * Nodes are never labelled -- the moment one gets text, the image stops
   * reading as a sea surface and starts reading as a diagram. */
  nodes: {
    turnRadius: 4, // metres
    tickRadius: 2.5,
    ticksPerLeg: 2,
    color: "#FFFFFF",
    halo: "#8FDCFF",
    haloScale: 2.6,
    y: 1.8,
  },

  /* ---- target marker ------------------------------------------------------
   * Pennant + ring + core at the far end. The short LEAD-OUT past the ring is
   * what makes it read as "next waypoint, survey continues" rather than "end
   * of data" -- a few lines of code carrying the whole meaning. */
  target: {
    leadOut: 0.22, // swath widths past the final node
    ringRadius: 9, // metres
    ringWidth: 1.6,
    coreRadius: 3,
    pennantH: 12,
    pennantRise: 9,
    color: "#FFFFFF",
    halo: "#9FE2FF",
    pulsePeriod: 2.0,
    y: 2.2,
  },

  /* ---- scene --------------------------------------------------------------
   * Fog and light are tuned to the reference's daylight, not to Scene3D's
   * darker survey mood: the plate is a bright, high-sun shot. `fogColor`
   * doubles as the sky, so horizon haze and sky are the same value and the
   * join is seamless by construction rather than by matching two numbers. */
  scene: {
    fogColor: "#9FC4DC",
    fogNear: 500,
    fogFar: 2600,
    /* Daylight water, passed into OceanSurface. Its own defaults are the dusk
     * tones the 3D survey view wants; these are the same three roles read off
     * the reference -- deep body, shallow body, and what the surface reflects
     * from the sky. */
    waterDeep: "#2A6FA8",
    waterShallow: "#2D7FB5",
    waterSky: "#BCD9EA",
    /* Peak wave amplitude, in metres, passed to OceanSurface.
     *
     * The plane has to be 9 km across to reach the horizon, and the shader's
     * historical default ties wave HEIGHT to plane size -- which at that size
     * is a 10.8 m swell that closes straight over a 28 m hull with ~3 m of
     * freeboard. A calm sea is also simply the right call for this shot: the
     * subject is the coverage pattern, and chop at survey scale is noise in
     * front of it. */
    waveHeight: 0.8,
    // Up and to the LEFT: the reference's sun glitter runs down the left edge
    // and every shadow in it points away from there.
    sunPosition: [-900, 700, 400] as const,
    sunIntensity: 1.05,
    ambientIntensity: 0.55,
    // Fill from the sky, so the hull's shadowed side is sea-lit rather than
    // black. Without it the GLB's navy paint reads as a silhouette at this
    // distance and the vessel stops being legible as a vessel.
    hemiIntensity: 0.9,
    oceanSize: 9000,
  },

  /* ---- vessel -------------------------------------------------------------
   * The model's own contract (public/models/README.md): bow along Blender +Y,
   * which the glTF exporter maps to -Z, and ORIGIN AT THE WATERLINE. So the
   * correct placement is y = 0, no rotation, no scale -- the hull sits in the
   * water at its authored size and sails away from the camera along the route.
   * Anything else here would be compensating for a bad export rather than
   * placing a good one. */
  vessel: {
    y: 0,
    headingDeg: 0, // bow toward -Z: away from the camera, along the route
    scale: 1, // authored at real metres
  },

  motion: {
    dashPeriod: 2.4, // seconds per dash cycle, marching toward the target
  },
} as const;
