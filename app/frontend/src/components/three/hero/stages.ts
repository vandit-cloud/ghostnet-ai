import * as THREE from "three";

/** ---------------------------------------------------------------------------
 * The choreography table.
 *
 * Everything the hero scene does is a pure function of one number: scroll
 * progress, 0 at the top of the hero and 1 at the bottom. Keeping it pure means
 * the scene is scrubbable in both directions - scroll back up and the towfish
 * rises and the cable retracts, with no state to get out of sync.
 *
 * THESE FOUR CONSTANTS ARE THE WHOLE PACING. They are the thing to tune in the
 * sandbox at /lab/hero.
 * ------------------------------------------------------------------------- */

/** Boat idles alone. Long enough that the hero reads as a still image first. */
export const STAGE_IDLE_END = 0.22;
/** Towfish leaves the A-frame and descends. The deliberate pause of the piece. */
export const STAGE_DEPLOY_END = 0.5;
/** Sonar comes alive, swath opens, waterfall starts painting. */
export const STAGE_SEARCH_END = 0.78;
/** Remainder: a target is found and held, so the scroll ends on the payload. */

/** ---------------------------------------------------------------------------
 * The scene is in METRES, matching the survey map (projectLatLon returns metres
 * too). vessel.glb is 28 m bow to transom, towfish.glb is 1.3 m.
 * ------------------------------------------------------------------------- */

/** Working depth of the towfish. Shallower than a real deep-tow survey so the
 * boat and the fish can share a frame without the boat becoming a dot. */
export const TOW_DEPTH = 34;
/** Seabed plane. The fish must visibly fly ABOVE it - a towfish on the bottom is
 * a destroyed towfish, and anyone who has run a survey will notice. */
export const SEABED_Y = -52;

/** Survey speed over ground, in metres per second - about 4 knots, which is a
 * real working speed for a side-scan tow (too fast and the along-track sampling
 * smears; too slow and the fish stops flying and sinks).
 *
 * This number is deliberately honest even though it is nearly invisible in the
 * wide shot: 2 m/s across a 400 m swath plane takes over three minutes to
 * traverse. Forward motion in this scene is therefore sold by NEAR-FIELD
 * parallax - marine snow passing the camera and the wake astern - exactly as it
 * is in real ROV and tow footage. Speeding the far field up instead is the
 * thing that reads as a treadmill. */
export const SURVEY_SPEED = 2.0;

/** Nose-down attitude while the fish is descending, in radians.
 *
 * A towfish being paid out flies nose-down: the cable pulls up and astern while
 * the body's own weight takes it down, so it trims bow-down through the descent
 * and levels out once it is flying at depth on a taut cable. Peaks mid-descent
 * and is zero at both ends, which is what sin(pi * deploy) gives without having
 * to differentiate the eased deploy curve.
 *
 * Sign: the model's nose is at -Z, and a positive rotation about X lifts a -Z
 * point, so nose-DOWN is negative. */
export function descentPitch(deploy: number): number {
  return -Math.sin(Math.PI * deploy) * 0.26;
}

/** The towfish is drawn larger than life.
 *
 * At true scale a 1.3 m body next to a 28 m vessel is about 40 px of a 1000 px
 * frame - honest, and completely illegible as the subject of the animation.
 * This is a deliberate, declared exaggeration: the thing the hero is ABOUT has
 * to be readable. Set it to 1 to see the truthful version. */
export const TOWFISH_DISPLAY_SCALE = 2.6;

export interface SceneState {
  /** 0 stowed on deck, 1 at full working depth. */
  deploy: number;
  /** World-space position of the towfish. */
  fish: THREE.Vector3;
  /** 0 sonar off, 1 sonar at full power. */
  ping: number;
  /** 0 no returns painted, 1 waterfall fully developed. */
  paint: number;
  /** 0 target unlit, 1 target locked. */
  lock: number;
}

const clamp01 = (v: number) => Math.min(1, Math.max(0, v));

/** Normalised position within [a, b], clamped outside it. */
export function span(p: number, a: number, b: number): number {
  return clamp01((p - a) / (b - a));
}

/** Ease that starts slow, runs, then settles - the motion of a winch paying out
 * cable under load, rather than a free fall. */
export function easeInOut(t: number): number {
  return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
}

/** The tow point on the vessel: the A-frame over the transom, at deck height.
 * vessel.glb spans z -14 (bow) to +14 (transom) with the waterline at y=0, so
 * this sits just inboard of the stern on the working deck. Nudge it if the
 * cable appears to leave the hull rather than the gantry. */
export const TOW_POINT = new THREE.Vector3(0, 2.6, 13.2);

export function sceneStateFor(progress: number, elapsed: number): SceneState {
  const deploy = easeInOut(span(progress, STAGE_IDLE_END, STAGE_DEPLOY_END));
  const ping = span(progress, STAGE_DEPLOY_END - 0.06, STAGE_SEARCH_END - 0.1);
  const paint = span(progress, STAGE_DEPLOY_END, 1);
  const lock = span(progress, STAGE_SEARCH_END, 1);

  // The fish trails further astern as it goes deeper - cable is a fixed length
  // paying out, so depth and layback are coupled, never independent.
  const depth = -TOW_DEPTH * deploy;
  const layback = TOW_POINT.z + deploy * 46;
  // A towed body is never still: it yaws and heaves gently on the cable.
  const wander = deploy * Math.sin(elapsed * 0.7) * 1.4;

  return {
    deploy,
    fish: new THREE.Vector3(wander, TOW_POINT.y + depth, layback),
    ping,
    paint,
    lock,
  };
}
