/* =============================================================================
 * The boustrophedon route, built in survey space.
 *
 * Output is a densely sampled centreline plus the across-track normal at every
 * sample, which is all the renderer needs: the ribbon is the centreline offset
 * by +/- half a swath, the grid is the same offsets at fractions of a swath,
 * and the nodes are a subset of the samples.
 *
 * ON TURN SHAPE. The turns are the detail implementations get wrong. They are
 * NOT square corners (no vessel turns like that) and NOT plain semicircles
 * (too mechanical, and they leave a hole at the apex). They are TEARDROP
 * turns: the route overshoots past the end of the leg, swings through 180°
 * bulging outward, and rejoins the next leg tangentially. A standard polyline
 * fillet cannot produce this -- the fillet tangent length goes to infinity as
 * the turn angle approaches 180° -- so each turn is constructed explicitly as
 * a half-ellipse between the two leg ends, with the overshoot as its bulge.
 * ========================================================================== */

import { PARAMS, type SurveyPoint } from "./plate";

export interface Sample extends SurveyPoint {
  /** Unit across-track normal at this sample, in survey space. */
  nu: number;
  nv: number;
  /** Cumulative distance along the centreline, in swath widths. */
  d: number;
  /** Which leg this sample belongs to; -1 while in a turn. */
  leg: number;
}

export type NodeKind = "turn" | "tick" | "terminal";

export interface RouteNode extends SurveyPoint {
  kind: NodeKind;
}

/**
 * A slab boundary: one vertex of the decimated centreline, carrying the MITRED
 * offset direction at that vertex.
 *
 * The swath is drawn as flat quads between consecutive slab vertices. Offsets
 * are mitred rather than simply perpendicular so that adjacent quads share an
 * exact edge: take the perpendicular on each side independently and every
 * corner opens a wedge-shaped gap on the outside and overlaps on the inside,
 * which is visible as a scalloped boundary the moment the route turns.
 *
 * `ms` is the mitre scale -- how much further out the offset point sits than
 * the half swath, which is 1/cos(half the turn angle). It is capped at
 * `PARAMS.swath.mitreLimit`: an unclamped near-180° join sends that point to
 * infinity.
 */
export interface SlabVertex extends SurveyPoint {
  /** Unit mitred offset direction (+starboard). */
  mu: number;
  mv: number;
  /** Mitre scale, >= 1, capped. */
  ms: number;
  d: number;
}

export interface Route {
  samples: Sample[];
  slabs: SlabVertex[];
  nodes: RouteNode[];
  /** Where the target marker goes -- the far end, past the last node. */
  target: SurveyPoint;
  /** Total centreline length, in swath widths. */
  length: number;
}

/** The vessel sits at the origin of survey space. In the 2D draft this was
 *  back-derived from the hull's measured position in the reference frame;
 *  with a real camera the vessel simply IS the origin and the camera is
 *  placed relative to it. */
function vesselU(): number {
  return 0;
}

function legGeometry(i: number) {
  const { legHalfLen, legTaper, legDrift } = PARAMS.survey;
  const half = legHalfLen * Math.pow(legTaper, i);
  const centre = legDrift * i;
  return { left: centre - half, right: centre + half, half, centre };
}

function legV(i: number): number {
  return PARAMS.survey.outboundV + i * PARAMS.survey.legSpacing;
}

/** A quarter-ellipse from `from` heading +v, arriving at `to` heading +/-u. */
function quarterTurn(from: SurveyPoint, to: SurveyPoint, steps: number): SurveyPoint[] {
  const du = to.u - from.u;
  const dv = to.v - from.v;
  const out: SurveyPoint[] = [];
  for (let i = 1; i <= steps; i++) {
    const t = (i / steps) * (Math.PI / 2);
    out.push({ u: from.u + du * Math.sin(t), v: from.v + dv * (1 - Math.cos(t)) });
  }
  return out;
}

/**
 * The 180° teardrop, as a half-ellipse from P to Q bulging by `bulge` in
 * `dir`. Parametrised on t in (0, pi]: the cosine term walks u and v from P to
 * Q, the sine term pushes the apex outward. Unequal endpoints (the legs taper,
 * so they are never quite equal) fall out of this for free.
 */
function teardrop(from: SurveyPoint, to: SurveyPoint, dir: 1 | -1, steps: number): SurveyPoint[] {
  const midU = (from.u + to.u) / 2;
  const midV = (from.v + to.v) / 2;
  const halfU = (to.u - from.u) / 2;
  const halfV = (to.v - from.v) / 2;
  const bulge = PARAMS.survey.turnRadius + PARAMS.survey.turnOvershoot;

  const out: SurveyPoint[] = [];
  for (let i = 1; i <= steps; i++) {
    const t = (i / steps) * Math.PI;
    out.push({
      u: midU - halfU * Math.cos(t) + dir * bulge * Math.sin(t),
      v: midV - halfV * Math.cos(t),
    });
  }
  return out;
}

/** Straight run, exclusive of `from`, inclusive of `to`. */
function straight(from: SurveyPoint, to: SurveyPoint, steps: number): SurveyPoint[] {
  const out: SurveyPoint[] = [];
  for (let i = 1; i <= steps; i++) {
    const t = i / steps;
    out.push({ u: from.u + (to.u - from.u) * t, v: from.v + (to.v - from.v) * t });
  }
  return out;
}

export function buildRoute(): Route {
  const { legs, outboundV, turnRadius, ticksPerLegFallback } = {
    ...PARAMS.survey,
    ticksPerLegFallback: PARAMS.nodes.ticksPerLeg,
  };

  const u0 = vesselU();
  // Start BEHIND the vessel. The swath then runs off the bottom of the frame
  // rather than ending in a hard straight line under the hull, and the vessel
  // reads as sitting inside water it has already scanned -- which is the true
  // statement about a towed sonar and also what the reference shows.
  const raw: SurveyPoint[] = [{ u: u0, v: -PARAMS.survey.sternTrail }];
  const nodes: RouteNode[] = [];

  // --- the outbound run, straight out of the stern, then a 90° turn onto the
  // first traverse. The vessel is mid-pattern: leg 0 is entered part-way
  // along, which is what a survey in progress actually looks like.
  const turnEntry = { u: u0, v: legV(0) - turnRadius };
  raw.push(...straight(raw[raw.length - 1], turnEntry, 10));
  const leg0Entry = { u: u0 + turnRadius, v: legV(0) };
  raw.push(...quarterTurn(turnEntry, leg0Entry, 14));

  let cursor = leg0Entry;
  // Leg 0 runs to starboard; every leg after it alternates.
  let heading: 1 | -1 = 1;

  for (let i = 0; i < legs; i++) {
    const g = legGeometry(i);
    const end = { u: heading === 1 ? g.right : g.left, v: legV(i) };

    nodes.push({ ...cursor, kind: "turn" });
    const span = Math.abs(end.u - cursor.u);
    raw.push(...straight(cursor, end, Math.max(12, Math.round(span * 40))));

    // Tick nodes, evenly spaced inside the leg (never at its ends).
    for (let t = 1; t <= ticksPerLegFallback; t++) {
      const f = t / (ticksPerLegFallback + 1);
      nodes.push({ u: cursor.u + (end.u - cursor.u) * f, v: end.v, kind: "tick" });
    }
    nodes.push({ ...end, kind: "turn" });

    if (i === legs - 1) {
      cursor = end;
      break;
    }

    const nextG = legGeometry(i + 1);
    const nextStart = { u: heading === 1 ? nextG.right : nextG.left, v: legV(i + 1) };
    raw.push(...teardrop(end, nextStart, heading, 26));
    cursor = nextStart;
    heading = heading === 1 ? -1 : 1;
  }

  // --- the lead-out. Three lines of code, and they carry the whole meaning of
  // the target marker: the survey CONTINUES past it, this is the next
  // waypoint and not the end of the data.
  const target: SurveyPoint = { u: cursor.u + heading * PARAMS.target.leadOut, v: cursor.v };
  raw.push(...straight(cursor, target, 6));

  const framed = withFrames(raw);
  return { ...framed, slabs: buildSlabs(framed.samples), nodes, target };
}

/** Attach across-track normals and cumulative distance to a raw centreline. */
function withFrames(raw: SurveyPoint[]): { samples: Sample[]; length: number } {
  const samples: Sample[] = [];
  let d = 0;

  for (let i = 0; i < raw.length; i++) {
    const curr = raw[i];
    const prev = raw[i - 1] ?? curr;
    const next = raw[i + 1] ?? curr;

    const du = next.u - prev.u;
    const dv = next.v - prev.v;
    const len = Math.hypot(du, dv) || 1;
    // Normal is the tangent rotated 90°: across-track, +starboard.
    const nu = dv / len;
    const nv = -du / len;

    if (i > 0) d += Math.hypot(curr.u - prev.u, curr.v - prev.v);
    samples.push({ ...curr, nu, nv, d, leg: -1 });
  }

  return { samples, length: d };
}


/* ---------------------------------------------------------------------------
 * Slabs
 * ------------------------------------------------------------------------ */

/**
 * Decimate the centreline to slab boundaries and compute the MITRED offset
 * direction at each one.
 *
 * Mitred, not perpendicular. If each quad took the perpendicular on its own
 * two ends independently, every corner would open a wedge-shaped gap on the
 * outside of the turn and overlap on the inside -- a scalloped boundary that
 * is obvious the moment the route bends. Sharing one mitred offset between
 * the quads on either side of a vertex is what makes the run of slabs read as
 * a single hard-edged sheet.
 *
 * The mitre scale is 1/cos(half the turn angle), which diverges as the turn
 * approaches 180°. It is capped at PARAMS.swath.mitreLimit; past the cap the
 * join degrades to a bevel, which is what the reference's turns show anyway.
 */
function buildSlabs(samples: Sample[]): SlabVertex[] {
  const step = PARAMS.swath.slabStep;

  // Keep the first and last sample, plus one every `step` of arc length. The
  // turns therefore get several facets and the straight legs get few, which is
  // both cheaper and closer to the reference's faceting.
  const kept: Sample[] = [];
  let next = -Infinity;
  for (let i = 0; i < samples.length; i++) {
    const s = samples[i];
    if (i === 0 || i === samples.length - 1 || s.d >= next) {
      kept.push(s);
      next = s.d + step;
    }
  }

  return kept.map((p, i) => {
    const prev = kept[i - 1] ?? p;
    const nextP = kept[i + 1] ?? p;

    const inDir = dir(prev, p) ?? dir(p, nextP) ?? { u: 0, v: 1 };
    const outDir = dir(p, nextP) ?? inDir;

    // Across-track normals of the two adjacent segments, +starboard.
    const n1 = { u: inDir.v, v: -inDir.u };
    const n2 = { u: outDir.v, v: -outDir.u };

    let mu = n1.u + n2.u;
    let mv = n1.v + n2.v;
    const len = Math.hypot(mu, mv);

    let ms = 1;
    if (len < 1e-6) {
      // A true reversal: the bisector is undefined. Fall back to the incoming
      // normal rather than emitting NaN.
      mu = n1.u;
      mv = n1.v;
    } else {
      mu /= len;
      mv /= len;
      const cosHalf = mu * n1.u + mv * n1.v;
      ms = Math.min(PARAMS.swath.mitreLimit, 1 / Math.max(cosHalf, 1e-3));
    }

    return { u: p.u, v: p.v, mu, mv, ms, d: p.d };
  });
}

function dir(a: SurveyPoint, b: SurveyPoint): { u: number; v: number } | null {
  const du = b.u - a.u;
  const dv = b.v - a.v;
  const len = Math.hypot(du, dv);
  if (len < 1e-9) return null;
  return { u: du / len, v: dv / len };
}

/** A point offset across-track from a slab vertex, `k` in swath widths
 *  (+/-0.5 is the swath edge). Uses the mitred direction and scale, so points
 *  at the same `k` on consecutive vertices join without a gap. */
export function slabOffset(s: SlabVertex, k: number): SurveyPoint {
  return { u: s.u + s.mu * k * s.ms, v: s.v + s.mv * k * s.ms };
}
