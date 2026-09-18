"use client";

/* =============================================================================
 * The overlay: coverage slabs, survey grid, dashed route, nodes, target.
 *
 * This is the only part of the plate this feature owns. The water is
 * OceanSurface, the hull is vessel.glb, and the camera is a real one -- see
 * the header of plate.ts.
 *
 * Everything here is built ONCE from survey-space geometry and laid flat on
 * the water at a few centimetres of clearance. Nothing is projected by hand:
 * the perspective is whatever the camera does, which is what makes the same
 * geometry usable from any viewpoint (and, later, from Leaflet's).
 * ========================================================================== */

import { useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

import { PARAMS, SWATH_M, type SurveyPoint } from "./plate";
import { buildRoute, slabOffset, type Route, type SlabVertex } from "./route";

export function useSurveyRoute(): Route {
  return useMemo(() => buildRoute(), []);
}

/** Free a geometry's GPU buffers when the component that built it goes away.
 *  three has no finalizer, so an unmounted mesh's BufferGeometry stays
 *  allocated; every layer toggle in the lab unmounts these. */
function useDisposable(geometry: THREE.BufferGeometry) {
  useEffect(() => () => geometry.dispose(), [geometry]);
}

function push(arr: number[], p: SurveyPoint, y: number) {
  arr.push(p.u * SWATH_M, y, -p.v * SWATH_M);
}

/** 1 at the vessel, 0 by the first turn. Drives the "being acquired right now"
 *  brightening of the near slabs. */
function sternWeight(v: number): number {
  return Math.min(1, Math.max(0, 1 - v / PARAMS.survey.outboundV));
}

/* ---------------------------------------------------------------------------
 * Coverage slabs
 * ------------------------------------------------------------------------ */

export function CoverageSlabs({ route }: { route: Route }) {
  const geometry = useMemo(() => {
    const S = PARAMS.swath;
    const positions: number[] = [];
    const colors: number[] = [];
    const base = new THREE.Color(S.color);
    const lift = S.opacityStern / S.opacity;

    for (let i = 1; i < route.slabs.length; i++) {
      const a = route.slabs[i - 1];
      const b = route.slabs[i];

      const al = slabOffset(a, -0.5);
      const ar = slabOffset(a, 0.5);
      const bl = slabOffset(b, -0.5);
      const br = slabOffset(b, 0.5);

      // Two triangles, hard-edged: no smoothing between slabs, which is the
      // whole point of the form.
      for (const p of [al, ar, br, al, br, bl]) push(positions, p, S.y);

      /* The stern lift is applied as COLOUR, not as per-vertex alpha.
       * Adjacent legs overlap by 15% (PARAMS.survey.legSpacing), and alpha
       * there would stack into a bright seam the reference does not have.
       * Brightening the colour instead leaves the overlap invisible, because
       * every fragment still composites exactly once at the material's single
       * opacity. */
      const ka = 1 + sternWeight(a.v) * (lift - 1);
      const kb = 1 + sternWeight(b.v) * (lift - 1);
      for (const k of [ka, ka, kb, ka, kb, kb]) {
        colors.push(
          Math.min(1, base.r * k),
          Math.min(1, base.g * k),
          Math.min(1, base.b * k)
        );
      }
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    geo.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
    return geo;
  }, [route]);
  useDisposable(geometry);

  return (
    <mesh geometry={geometry} renderOrder={1}>
      <meshBasicMaterial
        vertexColors
        transparent
        opacity={PARAMS.swath.opacity}
        side={THREE.DoubleSide}
        depthWrite={false}
        toneMapped={false}
      />
    </mesh>
  );
}

/* ---------------------------------------------------------------------------
 * Outer edge + survey grid
 * ------------------------------------------------------------------------ */

/** True where the mitre has been clamped, i.e. inside a turn tight enough that
 *  the inner offset edge folds through itself. The FILL does not care -- it
 *  composites as a union and the fold is invisible -- but a stroked edge draws
 *  the fold, and it lands as a bright chevron across the middle of the
 *  coverage. So the edge simply stops at the turns, which is also true to the
 *  reference: the inside of a turn is interior water, scanned twice. */
function folded(s: SlabVertex): boolean {
  return s.ms > PARAMS.swath.mitreLimit - 1e-6;
}

export function SwathEdges({ route }: { route: Route }) {
  const geometry = useMemo(() => {
    const positions: number[] = [];
    for (const side of [-0.5, 0.5]) {
      for (let i = 1; i < route.slabs.length; i++) {
        const a = route.slabs[i - 1];
        const b = route.slabs[i];
        if (folded(a) || folded(b)) continue;
        push(positions, slabOffset(a, side), PARAMS.swath.y + 0.05);
        push(positions, slabOffset(b, side), PARAMS.swath.y + 0.05);
      }
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    return geo;
  }, [route]);
  useDisposable(geometry);

  return (
    <lineSegments geometry={geometry} renderOrder={2}>
      <lineBasicMaterial
        color={PARAMS.swath.edgeColor}
        transparent
        opacity={PARAMS.swath.edgeOpacity}
        depthWrite={false}
        toneMapped={false}
      />
    </lineSegments>
  );
}

export function SurveyGrid({ route }: { route: Route }) {
  const geometry = useMemo(() => {
    const G = PARAMS.grid;
    const positions: number[] = [];

    // Along-track divisions. Built from the same mitred vertices as the slabs,
    // so they converge with the coverage through every turn instead of sliding
    // off it -- which is what a screen-space or world-axis grid would do.
    for (let j = 1; j < G.across; j++) {
      const f = j / G.across;
      if (Math.min(f, 1 - f) < G.edgeFade) continue;
      const k = -0.5 + f;
      for (let i = 1; i < route.slabs.length; i++) {
        push(positions, slabOffset(route.slabs[i - 1], k), G.y);
        push(positions, slabOffset(route.slabs[i], k), G.y);
      }
    }

    // Across-track "ping" lines: one per slab boundary, because in a slab
    // rendering the facet edge and the ping line are the same edge.
    for (const s of route.slabs) {
      push(positions, slabOffset(s, -0.5 + G.edgeFade), G.y);
      push(positions, slabOffset(s, 0.5 - G.edgeFade), G.y);
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    return geo;
  }, [route]);
  useDisposable(geometry);

  return (
    <lineSegments geometry={geometry} renderOrder={2}>
      <lineBasicMaterial
        color={PARAMS.grid.color}
        transparent
        opacity={PARAMS.grid.opacity}
        depthWrite={false}
        toneMapped={false}
      />
    </lineSegments>
  );
}

/* ---------------------------------------------------------------------------
 * The dashed route line
 * ------------------------------------------------------------------------ */

const routeVertex = /* glsl */ `
  attribute float aDist;
  varying float vDist;
  #include <fog_pars_vertex>
  void main() {
    vDist = aDist;
    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    gl_Position = projectionMatrix * mvPosition;
    #include <fog_vertex>
  }
`;

const routeFragment = /* glsl */ `
  uniform vec3 uColor;
  uniform float uDash;
  uniform float uGap;
  uniform float uOffset;
  varying float vDist;
  #include <fog_pars_fragment>
  void main() {
    // The dash is cut in the FRAGMENT shader off a per-vertex arc length, so
    // the phase is continuous along the whole polyline by construction. A
    // per-segment dash pattern restarts at every vertex and stutters visibly
    // at each turn, which is the classic tell of a naive implementation.
    float m = mod(vDist - uOffset, uDash + uGap);
    if (m > uDash) discard;
    gl_FragColor = vec4(uColor, 1.0);
    #include <fog_fragment>
  }
`;

export function RouteLine({ route, paused }: { route: Route; paused: boolean }) {
  const material = useRef<THREE.ShaderMaterial>(null);

  const geometry = useMemo(() => {
    const L = PARAMS.line;
    const positions: number[] = [];
    const dists: number[] = [];
    let run = 0;

    /* A thin ribbon MESH, not a THREE.Line. WebGL ignores `linewidth` on
     * virtually every platform, so a Line is locked to one pixel: it would
     * stay the same width at the horizon as at the stern, which reads as a
     * sticker on the screen rather than a mark on the water. A ribbon takes
     * perspective like everything else. */
    for (let i = 1; i < route.samples.length; i++) {
      const a = route.samples[i - 1];
      const b = route.samples[i];
      const segM = Math.hypot(b.u - a.u, b.v - a.v) * SWATH_M;

      const hw = L.halfWidth / SWATH_M;
      const al = { u: a.u - a.nu * hw, v: a.v - a.nv * hw };
      const ar = { u: a.u + a.nu * hw, v: a.v + a.nv * hw };
      const bl = { u: b.u - b.nu * hw, v: b.v - b.nv * hw };
      const br = { u: b.u + b.nu * hw, v: b.v + b.nv * hw };

      for (const p of [al, ar, br, al, br, bl]) push(positions, p, L.y);
      const d0 = run;
      const d1 = run + segM;
      dists.push(d0, d0, d1, d0, d1, d1);
      run = d1;
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    geo.setAttribute("aDist", new THREE.Float32BufferAttribute(dists, 1));
    return geo;
  }, [route]);

  useDisposable(geometry);

  useFrame((_, delta) => {
    if (paused || !material.current) return;
    const L = PARAMS.line;
    const speed = (L.dash + L.gap) / PARAMS.motion.dashPeriod;
    material.current.uniforms.uOffset.value += delta * speed;
  });

  const uniforms = useMemo(
    () => ({
      /* The fog uniforms have to be merged in BY HAND. `fog` on a
       * ShaderMaterial only tells three to inject the fog shader chunks; the
       * renderer then writes straight into `uniforms.fogColor.value` and
       * friends, and if they are not there it throws "Cannot read properties
       * of undefined (reading 'value')" once per frame per material. Cloned
       * rather than spread, because UniformsLib's entries are shared objects
       * and two materials writing one uniform is a bug waiting on a second
       * fogged shader. */
      ...THREE.UniformsUtils.clone(THREE.UniformsLib.fog),
      uColor: { value: new THREE.Color(PARAMS.line.color) },
      uDash: { value: PARAMS.line.dash },
      uGap: { value: PARAMS.line.gap },
      uOffset: { value: 0 },
    }),
    []
  );

  return (
    <mesh geometry={geometry} renderOrder={3}>
      <shaderMaterial
        ref={material}
        vertexShader={routeVertex}
        fragmentShader={routeFragment}
        uniforms={uniforms}
        side={THREE.DoubleSide}
        depthWrite={false}
        fog
      />
    </mesh>
  );
}

/* ---------------------------------------------------------------------------
 * Nodes and target
 * ------------------------------------------------------------------------ */

export function WaypointNodes({ route }: { route: Route }) {
  const N = PARAMS.nodes;
  return (
    <group>
      {route.nodes.map((node, i) => {
        const r = node.kind === "turn" ? N.turnRadius : N.tickRadius;
        const pos: [number, number, number] = [node.u * SWATH_M, N.y, -node.v * SWATH_M];
        return (
          <group key={i} position={pos} rotation={[-Math.PI / 2, 0, 0]} renderOrder={4}>
            <mesh>
              <circleGeometry args={[r * N.haloScale, 24]} />
              <meshBasicMaterial
                color={N.halo}
                transparent
                opacity={node.kind === "turn" ? 0.22 : 0.14}
                depthWrite={false}
                toneMapped={false}
              />
            </mesh>
            <mesh position={[0, 0, 0.1]}>
              <circleGeometry args={[r, 20]} />
              <meshBasicMaterial color={N.color} depthWrite={false} toneMapped={false} />
            </mesh>
          </group>
        );
      })}
    </group>
  );
}

export function TargetMarker({ route, paused }: { route: Route; paused: boolean }) {
  const T = PARAMS.target;
  const ring = useRef<THREE.Group>(null);
  const clock = useRef(0);

  useFrame((_, delta) => {
    if (paused || !ring.current) return;
    clock.current += delta;
    const pulse = 0.5 + 0.5 * Math.sin((clock.current / T.pulsePeriod) * Math.PI * 2);
    ring.current.scale.setScalar(1 + 0.12 * pulse);
  });

  const pos: [number, number, number] = [
    route.target.u * SWATH_M,
    T.y,
    -route.target.v * SWATH_M,
  ];

  return (
    <group position={pos} renderOrder={5}>
      <group ref={ring} rotation={[-Math.PI / 2, 0, 0]}>
        <mesh>
          <ringGeometry args={[T.ringRadius - T.ringWidth, T.ringRadius, 32]} />
          <meshBasicMaterial color={T.color} transparent opacity={0.95} depthWrite={false} toneMapped={false} />
        </mesh>
        <mesh position={[0, 0, 0.1]}>
          <circleGeometry args={[T.coreRadius, 16]} />
          <meshBasicMaterial color={T.color} depthWrite={false} toneMapped={false} />
        </mesh>
        <mesh position={[0, 0, -0.1]}>
          <circleGeometry args={[T.ringRadius * 3, 24]} />
          <meshBasicMaterial color={T.halo} transparent opacity={0.16} depthWrite={false} toneMapped={false} />
        </mesh>
      </group>

      {/* The pennant is the one part of the overlay that stands UP off the
          water. It has to: a flat marker at this range is a few pixels and
          disappears into the grid, and the whole job of this element is to be
          findable at a glance. */}
      <mesh position={[0, T.pennantRise + T.pennantH / 2, 0]}>
        <coneGeometry args={[T.pennantH * 0.42, T.pennantH, 3]} />
        <meshBasicMaterial color={T.color} depthWrite={false} toneMapped={false} />
      </mesh>
    </group>
  );
}
