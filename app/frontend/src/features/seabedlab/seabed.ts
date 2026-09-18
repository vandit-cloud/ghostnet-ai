import * as THREE from "three";

import { patchUnderwater, type UnderwaterUniforms } from "./underwaterMaterial";

/* =============================================================================
 * The seabed clutter, rebuilt.
 *
 * PLACEMENT IS UNCHANGED AND DELIBERATELY SO. Same seeds (20260914, 77003,
 * 5150, 31337), same lane() bias, same counts, same sink depths as
 * features/landing/hero/scene.ts. The only things that move are TESSELLATION
 * and MATERIAL.
 *
 * That is not laziness, it is what makes the lab's wipe mean anything: if the
 * rocks also moved, every comparison would be confounded and there would be no
 * way to tell a better material from a luckier arrangement. Clumping and scour
 * are Phase 3 and belong in their own pass, against a signed-off Phase 2.
 * ========================================================================== */

export type BuildOpts = {
  rockDetail: number;
  headDetail: number;
  branchRadial: number;
  slabBevel: number;
  hueJitter: number;
  valueJitter: number;
};

/** Verbatim from scene.ts. Seeded, never Math.random(): a scene that reshuffles
 *  on reload cannot be tuned, and a rock that moves between two screenshots is
 *  an hour lost to a bug that was never there. */
function rng(seed: number) {
  return function () {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Verbatim from scene.ts. Deformed by POSITION, not per vertex: Icosahedron is
 *  non-indexed, so every corner is duplicated once per face - jitter them
 *  independently and the solid tears open along every edge. */
function lumpy(geo: THREE.BufferGeometry, amt: number) {
  const a = geo.getAttribute("position");
  for (let i = 0; i < a.count; i++) {
    const x = a.getX(i), y = a.getY(i), z = a.getZ(i);
    const k = 1 + amt * (Math.sin(x * 4.1 + y * 2.3) * 0.5 + Math.cos(z * 3.7 - x * 1.9) * 0.5);
    a.setXYZ(i, x * k, y * k, z * k);
  }
  geo.computeVertexNormals();
  return geo;
}

/** A second, finer deformation that only pays off once there are enough
 *  vertices to carry it. At detail 0 (20 faces) this does nothing visible,
 *  which is exactly why the shipped rocks read as dice however they are lit. */
function crease(geo: THREE.BufferGeometry, amt: number, freq: number) {
  const a = geo.getAttribute("position");
  for (let i = 0; i < a.count; i++) {
    const x = a.getX(i), y = a.getY(i), z = a.getZ(i);
    const n =
      Math.sin(x * freq + y * freq * 0.7) *
      Math.cos(z * freq * 1.3 - y * freq * 0.5) *
      Math.sin(y * freq * 1.9 + x * freq * 0.3);
    const k = 1 + amt * n;
    a.setXYZ(i, x * k, y * k, z * k);
  }
  geo.computeVertexNormals();
  return geo;
}

/** A LANE, not a rectangle. Verbatim from scene.ts: rnd()*rnd() biases toward
 *  zero, piling clutter near the lane centre without a hard edge. */
function lane(rnd: () => number, spread: number, zNear: number, zFar: number): [number, number] {
  const side = rnd() < 0.5 ? -1 : 1;
  return [side * spread * rnd() * rnd() + (rnd() - 0.5) * 10, zNear + (zFar - zNear) * rnd()];
}

/** Per-instance colour. InstancedMesh has supported this since r125, so 58
 *  identical rocks were always a choice. Hue moves a little and VALUE moves a
 *  lot, which is how real rubble varies: same mineral, different wear, wetness
 *  and biofilm. Jittering hue hard instead gives a bag of sweets. */
function tint(base: THREE.Color, rnd: () => number, hue: number, value: number) {
  const hsl = { h: 0, s: 0, l: 0 };
  base.getHSL(hsl);
  return new THREE.Color().setHSL(
    (hsl.h + (rnd() - 0.5) * hue + 1) % 1,
    THREE.MathUtils.clamp(hsl.s * (1 + (rnd() - 0.5) * 0.5), 0, 1),
    THREE.MathUtils.clamp(hsl.l * (1 + (rnd() - 0.5) * value), 0.02, 0.95)
  );
}

export type SeabedHandles = {
  group: THREE.Group;
  materials: THREE.MeshStandardMaterial[];
  dispose: () => void;
};

export function buildSeabed(
  uniforms: UnderwaterUniforms,
  opts: BuildOpts,
  patched: boolean
): SeabedHandles {
  const group = new THREE.Group();
  const materials: THREE.MeshStandardMaterial[] = [];
  const geos: THREE.BufferGeometry[] = [];

  const mat = (params: THREE.MeshStandardMaterialParameters) => {
    const m = new THREE.MeshStandardMaterial(params);
    if (patched) patchUnderwater(m, uniforms);
    materials.push(m);
    return m;
  };

  /* Shared scatter. castShadow stays OFF - the same call scene.ts makes, for
     the same reason: a 30 m water column scatters a small object's shadow into
     nothing, and the towfish's shadow is the one carrying information. Letting
     fifty rocks compete with it buries the only cue for how high it is flying. */
  function scatter(
    mesh: THREE.InstancedMesh,
    n: number,
    seed: number,
    base: THREE.Color,
    place: (
      i: number, rnd: () => number,
      pos: THREE.Vector3, scl: THREE.Vector3, e: THREE.Euler
    ) => void
  ) {
    const rnd = rng(seed);
    const m = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler();
    const pos = new THREE.Vector3(), scl = new THREE.Vector3();
    for (let i = 0; i < n; i++) {
      place(i, rnd, pos, scl, e);
      q.setFromEuler(e);
      mesh.setMatrixAt(i, m.compose(pos, q, scl));
      mesh.setColorAt(i, tint(base, rnd, opts.hueJitter, opts.valueJitter));
    }
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    mesh.castShadow = false;
    mesh.receiveShadow = true;
    group.add(mesh);
    return mesh;
  }

  // ------------------------------------------------------------------ rubble
  const rockGeo = crease(
    lumpy(new THREE.IcosahedronGeometry(1, opts.rockDetail), 0.55),
    opts.rockDetail > 0 ? 0.13 : 0,
    3.1
  );
  geos.push(rockGeo);
  const rocks = new THREE.InstancedMesh(rockGeo, mat({ color: 0x6b6f66, roughness: 0.95, metalness: 0.0 }), 58);
  scatter(rocks, 58, 20260914, new THREE.Color(0x6b6f66), (_i, rnd, pos, scl, e) => {
    const [x, z] = lane(rnd, 58, -8, -168);
    const r = 0.35 + rnd() * rnd() * 2.4;
    /* SUNK, not resting. A rock on a soft bottom is partly buried; objects
       sitting on the surface like props on a table is the giveaway of dressed
       CG terrain. */
    pos.set(x, r * 0.62 - r * 0.34, z);
    scl.set(r * (0.8 + rnd() * 0.5), r * (0.55 + rnd() * 0.4), r * (0.8 + rnd() * 0.5));
    e.set(rnd() * 3.14, rnd() * 6.28, rnd() * 3.14);
  });

  // ---------------------------------------------- broken slabs: man-made
  const slabGeo = opts.slabBevel
    ? crease(new THREE.BoxGeometry(1, 1, 1, 3, 2, 3), 0.045, 5.5)
    : new THREE.BoxGeometry(1, 1, 1);
  geos.push(slabGeo);
  const slabs = new THREE.InstancedMesh(slabGeo, mat({ color: 0x585d5c, roughness: 0.88, metalness: 0.05 }), 16);
  scatter(slabs, 16, 77003, new THREE.Color(0x585d5c), (_i, rnd, pos, scl, e) => {
    const [x, z] = lane(rnd, 46, -14, -150);
    const w = 1.2 + rnd() * 3.4;
    pos.set(x, 0.18, z);
    scl.set(w, 0.22 + rnd() * 0.35, w * (0.4 + rnd() * 0.7));
    /* Tipped, never level. Debris through surf does not settle flat, and a flat
       slab reads instantly as a placed box. */
    e.set((rnd() - 0.5) * 0.5, rnd() * 6.28, (rnd() - 0.5) * 0.5);
  });

  // --------------------------------------------------- coral: branching
  const branchGeo = new THREE.CylinderGeometry(0.055, 0.17, 1, opts.branchRadial, 3, true);
  branchGeo.translate(0, 0.5, 0);
  geos.push(branchGeo);
  const coralMat = mat({ color: 0xa8614c, roughness: 0.92, metalness: 0.0, side: THREE.DoubleSide });
  const CLUSTERS = 11, PER = 14;
  const coral = new THREE.InstancedMesh(branchGeo, coralMat, CLUSTERS * PER);
  {
    const rnd = rng(5150);
    const sites: [number, number, number][] = [];
    for (let c = 0; c < CLUSTERS; c++) {
      const [x, z] = lane(rnd, 50, -18, -160);
      sites.push([x, z, 0.6 + rnd() * 1.5]);
    }
    const m = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler();
    const pos = new THREE.Vector3(), scl = new THREE.Vector3();
    const base = new THREE.Color(0xa8614c);
    let i = 0;
    for (const [cx, cz, size] of sites) {
      /* One colour per COLONY, not per branch. A colony is one organism; tinting
         its branches independently is the detail that would say "instanced
         cylinders" out loud. */
      const colonyTint = tint(base, rnd, opts.hueJitter, opts.valueJitter);
      for (let b = 0; b < PER; b++) {
        const az = (b / PER) * 6.2831 + rnd() * 0.5;
        const up = rnd();
        const tilt = 0.15 + up * 0.85 + rnd() * 0.25;
        const len = size * (1.4 - up * 0.7) * (0.7 + rnd() * 0.6);
        const rad = size * up * 0.45;
        pos.set(cx + Math.cos(az) * rad, size * 0.15 + up * size * 0.5, cz + Math.sin(az) * rad);
        scl.set(size * 0.55, len, size * 0.55);
        e.set(Math.cos(az) * tilt, az, Math.sin(az) * tilt, "ZYX");
        q.setFromEuler(e);
        coral.setMatrixAt(i, m.compose(pos, q, scl));
        coral.setColorAt(i, colonyTint);
        i++;
      }
    }
    coral.instanceMatrix.needsUpdate = true;
    if (coral.instanceColor) coral.instanceColor.needsUpdate = true;
    coral.castShadow = false;
    coral.receiveShadow = true;
    group.add(coral);
  }

  // ------------------------------------------------ coral: massive heads
  const headGeo = crease(
    lumpy(new THREE.SphereGeometry(1, 12 * (1 + opts.headDetail), 8 * (1 + opts.headDetail)), 0.28),
    opts.headDetail > 0 ? 0.07 : 0,
    6.5
  );
  geos.push(headGeo);
  const heads = new THREE.InstancedMesh(headGeo, mat({ color: 0x9a8455, roughness: 0.95, metalness: 0.0 }), 13);
  scatter(heads, 13, 31337, new THREE.Color(0x9a8455), (_i, rnd, pos, scl, e) => {
    const [x, z] = lane(rnd, 44, -20, -155);
    const r = 0.7 + rnd() * 1.7;
    pos.set(x, r * 0.42, z);
    scl.set(r, r * 0.62, r * (0.85 + rnd() * 0.3));
    e.set(0, rnd() * 6.28, 0);
  });

  return {
    group,
    materials,
    dispose: () => {
      for (const g of geos) g.dispose();
      for (const m of materials) m.dispose();
    },
  };
}
