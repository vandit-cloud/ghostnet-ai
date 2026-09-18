import * as THREE from "three";

import { patchUnderwater, type UnderwaterUniforms } from "./underwaterMaterial";

/* =============================================================================
 * TARGETS - the things a survey is actually looking for.
 *
 * "Target" is the survey word, and it is the right one: a wreck and a derelict
 * net are contacts, not scenery. Everything in seabed.ts is clutter that exists
 * to give the eye scale and motion reference. These two are the subject.
 *
 * WHY THIS EXISTS AT ALL. The hero's contact stage reads
 *
 *     ghost_net - 0.91 calibrated
 *     review_only - awaiting sign-off
 *
 * over a seabed containing rocks, broken slabs and coral. There is no net in it.
 * The scroll ends by announcing a detection with nothing to detect, and that is
 * the one claim on the page a marine reader would check. A wreck earns its place
 * for the same reason from the other direction: it is the canonical side-scan
 * target, and a wreck with gear snagged on it is the canonical ghost-net site -
 * lost gear fouls structure, which is exactly why structure is where you look.
 *
 * SCALE IS NOT DECORATION HERE. The hero's own readout says 12.6 m altitude and
 * a 120 m swath; the vessel GLB is 28 m. A wreck has to sit believably in that,
 * so WRECK_LEN is metres and everything derives from it.
 * ========================================================================== */

export type TargetOpts = {
  showWreck: number;
  showNet: number;
  wreckLen: number;
  wreckList: number;
  wreckBury: number;
  netPanels: number;
};

/** Seeded, for the same reason everything else here is: a target that moves
 *  between two screenshots is an hour lost to a bug that was never there. */
function rng(seed: number) {
  return function () {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/* ---------------------------------------------------------------------------
 * THE HULL.
 *
 * Swept sections, not a primitive. A box reads as a box and a squashed cylinder
 * reads as a pipe; what makes a hull legible from 40 m in bad visibility is the
 * PLAN TAPER - full amidships, fine at the bow - and the V of the sections.
 * Those two silhouette cues survive fog and low contrast when surface detail
 * does not.
 *
 * `t` runs 0 at the broken stern to 1 at the bow. The geometry deliberately
 * STOPS SHORT of t=0: the after third of this vessel is gone, and the exposed
 * frames beyond it are what say "wreck" rather than "boat parked on the sand".
 * ------------------------------------------------------------------------- */
function hullGeometry(len: number, beam: number, depth: number, segL = 26, segR = 18) {
  const pos: number[] = [];
  const idx: number[] = [];

  /** Beam/draft multiplier along the length. Full at 0.45 (amidships sits a
   *  little aft of centre on most working hulls), fining to a point at the bow. */
  const plan = (t: number) => Math.sin(Math.PI * Math.pow(THREE.MathUtils.clamp(t, 0, 1), 0.78));

  for (let i = 0; i <= segL; i++) {
    const t = 0.32 + (i / segL) * 0.68; // the intact forward two-thirds
    const z = (t - 0.5) * len;
    const p = Math.max(plan(t), 0.03);
    const b = beam * p;
    const d = depth * Math.max(Math.pow(p, 0.55), 0.06);
    // Sheer: the deck line rises toward the bow, which is most of what stops a
    // hull reading as an extruded shape.
    const sheer = depth * 0.18 * Math.pow(Math.max(t - 0.45, 0) / 0.55, 2);

    for (let j = 0; j <= segR; j++) {
      const a = (j / segR) * Math.PI * 2;
      const c = Math.cos(a);
      const x = b * Math.sin(a);
      // Crowned deck above the waterline, rounded-V below it.
      const y = c > 0 ? c * depth * 0.10 + sheer : -d * Math.pow(-c, 1.35);
      pos.push(x, y, z);
    }
  }

  const ring = segR + 1;
  for (let i = 0; i < segL; i++) {
    for (let j = 0; j < segR; j++) {
      const a = i * ring + j, b = a + 1, c = a + ring, d2 = c + 1;
      idx.push(a, c, b, b, c, d2);
    }
  }

  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  return g;
}

/* ---------------------------------------------------------------------------
 * A NET PANEL.
 *
 * A subdivided plane, draped in JS into a catenary and then billowed per-frame
 * in the vertex shader. The drape is baked because it is a SHAPE, not motion:
 * recomputing a hang curve every frame to get the same curve back is work for
 * nothing, and baking it means the billow only has to carry the small live part.
 *
 * `netUv` is a custom attribute rather than the plane's own `uv`, because three
 * only declares `uv` in the vertex shader when something defines USE_UV - a
 * material with no maps has no UVs at all, and the net has no maps by design.
 * Carrying our own attribute avoids attaching a dummy texture to force it.
 * ------------------------------------------------------------------------- */
function netPanel(w: number, h: number, sag: number, segX = 20, segY = 16) {
  const g = new THREE.PlaneGeometry(w, h, segX, segY);
  const p = g.getAttribute("position");
  const uv = g.getAttribute("uv");

  for (let i = 0; i < p.count; i++) {
    const u = uv.getX(i), v = uv.getY(i);
    // Catenary-ish hang across the span, deepest mid-panel.
    const hang = Math.sin(Math.PI * u) * sag;
    // Held at the top edge, pooling at the bottom: the lower third folds back
    // on itself rather than ending in a straight cut, which is what a net that
    // has settled actually does.
    const pool = Math.pow(Math.max(0.34 - v, 0) / 0.34, 2);
    p.setZ(i, p.getZ(i) - hang - pool * sag * 1.4);
    p.setY(i, p.getY(i) + pool * h * 0.10);
  }
  p.needsUpdate = true;
  g.computeVertexNormals();
  g.setAttribute("netUv", new THREE.Float32BufferAttribute(Array.from(uv.array), 2));
  return g;
}

export type TargetHandles = {
  group: THREE.Group;
  materials: THREE.MeshStandardMaterial[];
  dispose: () => void;
};

export function buildTargets(
  uniforms: UnderwaterUniforms,
  opts: TargetOpts,
  patched: boolean
): TargetHandles {
  const group = new THREE.Group();
  const materials: THREE.MeshStandardMaterial[] = [];
  const geos: THREE.BufferGeometry[] = [];
  const rnd = rng(0xc0ffee);

  const mat = (
    baseHex: number,
    params: THREE.MeshStandardMaterialParameters,
    variant: "solid" | "net" = "solid"
  ) => {
    const m = new THREE.MeshStandardMaterial({ ...params, color: baseHex });
    if (patched) patchUnderwater(m, uniforms, variant);
    materials.push(m);
    return m;
  };

  /* ======================================================================
   * THE WRECK
   * ==================================================================== */
  const wreck = new THREE.Group();
  wreck.visible = opts.showWreck > 0.5;
  group.add(wreck);

  const LEN = opts.wreckLen;
  const BEAM = LEN * 0.27;
  const DEPTH = LEN * 0.20;

  /* Steel that has been down long enough to lose its gear is not steel-coloured
     any more: it is iron oxide under a biofilm. A grey hull reads as a model of
     a hull. */
  const hullMat = mat(0x6a5a44, { roughness: 0.93, metalness: 0.08 });
  const hullGeo = hullGeometry(LEN, BEAM, DEPTH);
  geos.push(hullGeo);
  const hull = new THREE.Mesh(hullGeo, hullMat);
  hull.receiveShadow = true;
  wreck.add(hull);

  /* EXPOSED FRAMES where the after third has gone. Half-torus arcs on the
     section the hull would have had if it continued, so the ribs line up with
     the plating that is still there rather than floating behind it. */
  const ribMat = mat(0x5d4f3c, { roughness: 0.95, metalness: 0.10 });
  const ribGeo = new THREE.TorusGeometry(1, 0.035, 5, 20, Math.PI);
  geos.push(ribGeo);
  for (let k = 0; k < 5; k++) {
    const t = 0.30 - k * 0.055;
    const p = Math.sin(Math.PI * Math.pow(Math.max(t, 0.02), 0.78));
    const rib = new THREE.Mesh(ribGeo, ribMat);
    rib.scale.set(BEAM * p, DEPTH * p * 1.15, 1);
    rib.position.set(0, 0, (t - 0.5) * LEN);
    rib.rotation.z = Math.PI; // open side up, following the hull's V
    // Frames buckle as a hull collapses; dead-straight ribs read as a fish skeleton.
    rib.rotation.x = (rnd() - 0.5) * 0.18;
    rib.rotation.y = (rnd() - 0.5) * 0.12;
    wreck.add(rib);
  }

  /* A deckhouse, well forward. Without one the silhouette is a smooth shell and
     the eye has nothing to read as "built". */
  const houseGeo = new THREE.BoxGeometry(BEAM * 0.52, DEPTH * 0.55, LEN * 0.14);
  geos.push(houseGeo);
  const house = new THREE.Mesh(houseGeo, hullMat);
  house.position.set(0, DEPTH * 0.28, LEN * 0.10);
  house.rotation.z = 0.05;
  house.receiveShadow = true;
  wreck.add(house);

  /* Attitude. A wreck almost never sits upright: it lists, it is down by one
     end, and it is part buried. All three at once is what separates a wreck
     from a boat model placed on the sand. */
  wreck.rotation.set(0.05, 0.42, THREE.MathUtils.degToRad(opts.wreckList));
  wreck.position.set(-7, DEPTH * (0.5 - opts.wreckBury), -64);

  /* ======================================================================
   * THE GHOST NET
   *
   * Snagged on the wreck, which is the whole point: derelict gear fouls
   * structure, and structure is where a survey looks. A net lying on open sand
   * would be a weaker picture AND a weaker claim.
   * ==================================================================== */
  const nets = new THREE.Group();
  nets.visible = opts.showNet > 0.5;
  group.add(nets);

  /* Faded polypropylene under biofouling. Nets are made in high-visibility
     colours and the sea takes that out of them within a season or two, so a
     bright green net is a new net, which is not what this is. */
  const netMat = mat(
    0x7d9c7a,
    { roughness: 0.96, metalness: 0.0, side: THREE.DoubleSide, alphaTest: 0.5 },
    "net"
  );

  const PANELS = Math.max(1, Math.round(opts.netPanels));
  for (let i = 0; i < PANELS; i++) {
    const w = 5.5 + rnd() * 4.5;
    const h = 4.0 + rnd() * 3.5;
    const g = netPanel(w, h, 1.5 + rnd() * 1.4);
    geos.push(g);
    const panel = new THREE.Mesh(g, netMat);

    /* Draped from the wreck's rail down onto the seabed, fanning aft along the
       hull. Each panel starts on the structure and ends on the bottom, which is
       how a trawl that has parted actually lies. */
    const along = -0.18 + (i / Math.max(PANELS - 1, 1)) * 0.62;
    panel.position.set(
      -7 + Math.sin(0.42) * along * LEN + (rnd() - 0.5) * 3.0,
      DEPTH * (0.5 - opts.wreckBury) + h * 0.34,
      -64 + Math.cos(0.42) * along * LEN + (rnd() - 0.5) * 3.0
    );
    /* DRAPED, NOT STANDING. Panels left near-vertical read as fence: a flat
       grid held up at right angles to the bottom is the one attitude netting
       never holds once it is off a boat. Tipping them toward horizontal so they
       lie ACROSS the hull and spill onto the sand is what turns a grid into
       gear - the silhouette stops being a rectangle standing in open water and
       becomes a sheet following relief. */
    panel.rotation.set(
      -1.15 + (rnd() - 0.5) * 0.7,
      0.42 + (rnd() - 0.5) * 1.6,
      (rnd() - 0.5) * 0.8
    );
    nets.add(panel);
  }

  /* A BUNCHED MASS. A parted net does not only drape - most of its length ends
     up in a bundle where it dragged and balled up. This is the shape people who
     have seen ghost gear recognise first, and it is the one the detector is
     really being asked about. */
  const ballGeo = new THREE.IcosahedronGeometry(1, 2);
  {
    const a = ballGeo.getAttribute("position");
    for (let i = 0; i < a.count; i++) {
      const x = a.getX(i), y = a.getY(i), z = a.getZ(i);
      const k = 1 + 0.42 * (Math.sin(x * 3.3 + y * 2.1) * 0.5 + Math.cos(z * 2.9 - x * 1.7) * 0.5);
      a.setXYZ(i, x * k, y * k * 0.62, z * k);
    }
    ballGeo.computeVertexNormals();
    const uvs: number[] = [];
    const n = ballGeo.getAttribute("position");
    for (let i = 0; i < n.count; i++) {
      // Cheap spherical mapping: good enough for a mesh pattern on a blob, and
      // the seam it leaves is hidden in the tear field.
      uvs.push(
        0.5 + Math.atan2(n.getZ(i), n.getX(i)) / (2 * Math.PI),
        0.5 + Math.asin(THREE.MathUtils.clamp(n.getY(i) / 1.4, -1, 1)) / Math.PI
      );
    }
    ballGeo.setAttribute("netUv", new THREE.Float32BufferAttribute(uvs, 2));
  }
  geos.push(ballGeo);
  for (let i = 0; i < 2; i++) {
    const ball = new THREE.Mesh(ballGeo, netMat);
    const r = 1.5 + rnd() * 1.1;
    ball.scale.setScalar(r);
    ball.position.set(-7 + (rnd() - 0.5) * 13, r * 0.42, -64 + (rnd() - 0.5) * 16);
    ball.rotation.set(rnd() * 3.14, rnd() * 6.28, rnd() * 3.14);
    nets.add(ball);
  }

  return {
    group,
    materials,
    dispose: () => {
      for (const g of geos) g.dispose();
      for (const m of materials) m.dispose();
    },
  };
}
