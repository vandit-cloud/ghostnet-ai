"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

import { useReducedMotion } from "@/hooks/useReducedMotion";
import { DEFAULT_LAYERS, PARAMS, SWATH_M, type PlateLayers } from "@/features/maplab/plate";

const PlateScene = dynamic(
  () => import("@/features/maplab/PlateScene").then((m) => m.PlateScene),
  { ssr: false, loading: () => <div className="h-full w-full bg-[#9FC4DC]" /> }
);

const REFERENCE = "/lab/survey-plate-reference.png";

/** Isolated sandbox for the survey map plate — NOT a product route.
 *
 * Same rules as the water lab (docs/WATER_LAB.md):
 *   1. PARAMS is the single source of truth. Tuning means editing
 *      features/maplab/plate.ts, never a component.
 *   2. THE REFERENCE IS IN THE TOOL. Press R to cycle off / wipe / blend and
 *      drag the seam. Judge a feature by running the seam through it twice,
 *      never from memory — memory reliably says "close enough" about a swath
 *      that is 30% too bright.
 *
 * Deliberately on /lab so an unfinished composition is never on a route a
 * judge might open.
 */
export default function MapLabPage() {
  const [orbit, setOrbit] = useState(false);
  const [compare, setCompare] = useState<"off" | "wipe" | "blend">("off");
  const [seam, setSeam] = useState(0.5);
  const [layers, setLayers] = useState<PlateLayers>(DEFAULT_LAYERS);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const reduced = useReducedMotion();
  const [playing, setPlaying] = useState(true);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "r" || e.key === "R") {
        setCompare((c) => (c === "off" ? "wipe" : c === "wipe" ? "blend" : "off"));
      }
      if (e.key === "ArrowLeft") setSeam((s) => Math.max(0, s - 0.02));
      if (e.key === "ArrowRight") setSeam((s) => Math.min(1, s + 0.02));
      if (e.key === " ") {
        e.preventDefault();
        setPlaying((p) => !p);
      }
      if (e.key === "o" || e.key === "O") setOrbit((v) => !v);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const toggle = (key: keyof PlateLayers) => setLayers((l) => ({ ...l, [key]: !l[key] }));

  return (
    <div className="min-h-screen bg-[#0A1826] p-6 font-mono text-xs text-[#C4F8FF]">
      <header className="mb-4 flex flex-wrap items-baseline gap-x-6 gap-y-1">
        <h1 className="font-display text-lg uppercase tracking-[0.3em] text-white">
          Survey plate lab
        </h1>
        <p className="text-[#7FB4D4]">
          docs/SURVEY_MAP_PLATE_SPEC.md &middot; R = compare &middot; &larr;&rarr; = seam &middot; O
          = orbit &middot; space = pause
        </p>
      </header>

      <div className="flex flex-wrap gap-6">
        {/* Square stage, because the reference is square. Letterbox, never
            stretch, or every measured fraction in the spec is a lie. */}
        <div
          className="relative aspect-square w-full max-w-[760px] overflow-hidden border border-[#1E3F5C]"
          onMouseMove={(e) => {
            if (compare !== "wipe") return;
            const rect = e.currentTarget.getBoundingClientRect();
            setSeam((e.clientX - rect.left) / rect.width);
          }}
        >
          <PlateScene
            layers={layers}
            paused={!playing || reduced}
            orbit={orbit}
            selectedId={selectedId}
            onSelect={(id) => setSelectedId((prev) => (prev === id ? null : id))}
            className="absolute inset-0 h-full w-full"
          />

          {compare !== "off" && (
            <div
              className="pointer-events-none absolute inset-0 bg-cover bg-center"
              style={{
                backgroundImage: `url(${REFERENCE})`,
                opacity: compare === "blend" ? 0.5 : 1,
                clipPath: compare === "wipe" ? `inset(0 0 0 ${seam * 100}%)` : undefined,
              }}
            />
          )}
          {compare === "wipe" && (
            <div
              className="pointer-events-none absolute inset-y-0 w-px bg-[#EAF9FF]"
              style={{ left: `${seam * 100}%` }}
            />
          )}

          <div className="pointer-events-none absolute bottom-2 left-2 text-[10px] uppercase tracking-[0.2em] text-white/70">
            {compare === "off"
              ? orbit
                ? "reproduction — orbit"
                : "reproduction"
              : compare === "wipe"
                ? `wipe ${Math.round(seam * 100)}%`
                : "blend 50%"}
          </div>
        </div>

        <aside className="w-[268px] space-y-5">
          <section>
            <h2 className="mb-2 uppercase tracking-[0.2em] text-[#7FB4D4]">Layers</h2>
            <div className="grid grid-cols-2 gap-1">
              {(Object.keys(layers) as (keyof PlateLayers)[]).map((key) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => toggle(key)}
                  className={
                    layers[key]
                      ? "border border-[#2E9BE0] bg-[#2E9BE0]/20 px-2 py-1 text-left text-white"
                      : "border border-[#1E3F5C] px-2 py-1 text-left text-[#5E90B0]"
                  }
                >
                  {key}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={() => setLayers(DEFAULT_LAYERS)}
              className="mt-2 w-full border border-[#1E3F5C] px-2 py-1 text-[#7FB4D4] hover:text-white"
            >
              reset layers
            </button>
          </section>

          <section>
            <h2 className="mb-2 uppercase tracking-[0.2em] text-[#7FB4D4]">Camera</h2>
            <dl className="space-y-0.5 text-[#5E90B0]">
              <Row k="fov" v={`${PARAMS.camera.fov}°`} />
              <Row k="height" v={`${PARAMS.camera.height} m`} />
              <Row k="astern" v={`${PARAMS.camera.astern} m`} />
              <Row k="pitch" v={`${PARAMS.camera.pitchDeg}°`} />
            </dl>
            <p className="mt-2 leading-relaxed">
              Pitch is set as an angle, not by aiming at a point: the composition is defined by
              where the horizon lands, and only the angle controls that.
            </p>
          </section>

          <section>
            <h2 className="mb-2 uppercase tracking-[0.2em] text-[#7FB4D4]">Survey</h2>
            <dl className="space-y-0.5 text-[#5E90B0]">
              <Row k="swath width" v={`${SWATH_M} m`} />
              <Row k="range/side" v={`${SWATH_M / 2} m`} />
              <Row k="line spacing" v={`${Math.round(PARAMS.survey.legSpacing * SWATH_M)} m`} />
              <Row k="overlap" v={`${Math.round((1 - PARAMS.survey.legSpacing) * 100)}%`} />
              <Row k="leg length" v={`${Math.round(PARAMS.survey.legHalfLen * 2 * SWATH_M)} m`} />
              <Row k="legs" v={String(PARAMS.survey.legs)} />
            </dl>
            <p className="mt-2 leading-relaxed">
              Spacing is under the swath width on purpose. That overlap covers each pass&apos;s
              nadir gap with its neighbour, and it is why the coverage reads as one sheet rather
              than stripes.
            </p>
          </section>

          <section>
            <h2 className="mb-2 uppercase tracking-[0.2em] text-[#7FB4D4]">Scene</h2>
            <p className="leading-relaxed text-[#5E90B0]">
              Water is <span className="text-white">OceanSurface</span>, the same shader as the 3D
              survey view. Hull is <span className="text-white">vessel.glb</span> at its authored
              28 m, origin at the waterline, bow toward &minus;Z — no scale or offset applied. If
              you see the primitive box boat, the GLB failed to load; check the console.
            </p>
          </section>
        </aside>
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between">
      <dt>{k}</dt>
      <dd className="text-white">{v}</dd>
    </div>
  );
}
