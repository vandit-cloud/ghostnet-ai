"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useState } from "react";

import { BUILD, PARAMS, flatten, type ParamGroup } from "@/features/seabedlab/params";
import type { BuildOpts } from "@/features/seabedlab/seabed";
import type { TargetOpts } from "@/features/seabedlab/targets";

const SeabedScene = dynamic(
  () => import("@/features/seabedlab/SeabedScene").then((m) => m.SeabedScene),
  { ssr: false, loading: () => <div className="h-full w-full bg-[#0A1826]" /> }
);

/** Isolated sandbox for the seabed clutter - NOT a product route.
 *
 * Same rules as the water lab and the map lab (docs/WATER_LAB.md):
 *   1. PARAMS is the single source of truth. Tuning means editing
 *      features/seabedlab/params.ts, never a shader body.
 *   2. THE REFERENCE IS IN THE TOOL - and here the reference is WHAT SHIPS
 *      TODAY. Press R to cycle off / wipe / blend / shipped and drag the seam.
 *      Judge a change by running the seam across the same rock twice, never
 *      from memory: memory reliably says "close enough" about props that are
 *      20x under-fogged.
 *   3. Hand tuning over as JSON with "copy params".
 *
 * Nothing here touches features/landing/hero/scene.ts. When a pass is signed
 * off it ports the other way, deliberately, in one reviewable diff.
 */
const MODES = ["patched", "wipe", "blend", "shipped"] as const;

export default function SeabedLabPage() {
  const [groups, setGroups] = useState(() => structuredClone(PARAMS) as Record<string, ParamGroup>);
  const [buildP, setBuildP] = useState(() => structuredClone(BUILD) as ParamGroup);
  const [mode, setMode] = useState(1);
  const [seam, setSeam] = useState(0.5);
  const [playing, setPlaying] = useState(true);
  const [copied, setCopied] = useState(false);

  const values = useMemo(() => flatten(groups), [groups]);
  const build = useMemo<BuildOpts>(
    () => ({
      rockDetail: buildP.rockDetail.v,
      headDetail: buildP.headDetail.v,
      branchRadial: buildP.branchRadial.v,
      slabBevel: buildP.slabBevel.v,
      hueJitter: buildP.hueJitter.v,
      valueJitter: buildP.valueJitter.v,
    }),
    [buildP]
  );
  const targets = useMemo<TargetOpts>(
    () => ({
      showWreck: buildP.showWreck.v,
      showNet: buildP.showNet.v,
      wreckLen: buildP.wreckLen.v,
      wreckList: buildP.wreckList.v,
      wreckBury: buildP.wreckBury.v,
      netPanels: buildP.netPanels.v,
    }),
    [buildP]
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return;
      if (e.key === "r" || e.key === "R") setMode((m) => (m + 1) % MODES.length);
      if (e.key === "ArrowLeft") setSeam((s) => Math.max(0, s - 0.02));
      if (e.key === "ArrowRight") setSeam((s) => Math.min(1, s + 0.02));
      if (e.key === " ") { e.preventDefault(); setPlaying((p) => !p); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const set = useCallback((group: string, key: string, v: number) => {
    setGroups((g) => ({ ...g, [group]: { ...g[group], [key]: { ...g[group][key], v } } }));
  }, []);

  const copy = useCallback(() => {
    const out = { ...flatten(groups), ...Object.fromEntries(
      Object.entries(buildP).map(([k, p]) => [k, p.v])) };
    navigator.clipboard.writeText(JSON.stringify(out, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 1400);
  }, [groups, buildP]);

  const Slider = ({ g, k, p }: { g: string; k: string; p: { v: number; min: number; max: number; step: number; label: string } }) => (
    <label className="block">
      <span className="flex justify-between gap-2 text-[10px] text-[#8FB4C9]">
        <span className="truncate">{p.label}</span>
        <em className="not-italic tabular-nums text-[#C4F8FF]">{p.v}</em>
      </span>
      <input
        type="range"
        min={p.min} max={p.max} step={p.step} value={p.v}
        onChange={(e) => set(g, k, Number(e.target.value))}
        className="mt-0.5 w-full accent-[#5FD4E4]"
      />
    </label>
  );

  return (
    <div className="flex h-screen bg-[#0A1826] font-mono text-xs text-[#C4F8FF]">
      <div className="relative flex-1">
        <SeabedScene
          values={values} build={build} targets={targets}
          compare={mode} seam={seam} playing={playing}
        />

        <div className="pointer-events-none absolute left-4 top-4 rounded-md bg-[#0A1826]/80 px-3 py-2 backdrop-blur">
          <div className="text-[10px] uppercase tracking-[0.25em] text-[#5FD4E4]">seabed lab</div>
          <div className="mt-1 text-[10px] text-[#8FB4C9]">
            {mode === 1 ? <>left of seam = <b className="text-white">shipped</b> · right = <b className="text-white">patched</b></>
             : mode === 2 ? <>blend {(seam * 100) | 0}% patched</>
             : <>showing <b className="text-white">{MODES[mode]}</b></>}
          </div>
          <div className="mt-1 text-[10px] text-[#8FB4C9]/70">
            R cycle · ←/→ seam · space pause · drag orbit · wheel dolly
          </div>
        </div>

        <input
          type="range" min={0} max={1} step={0.001} value={seam}
          onChange={(e) => setSeam(Number(e.target.value))}
          className="absolute bottom-5 left-1/2 w-[min(560px,80%)] -translate-x-1/2 accent-[#5FD4E4]"
        />
      </div>

      <aside className="w-[320px] shrink-0 overflow-y-auto border-l border-[#5FD4E4]/20 bg-[#08131F] p-4">
        <div className="mb-3 flex items-center gap-2">
          {MODES.map((m, i) => (
            <button key={m} onClick={() => setMode(i)}
              className={`rounded px-2 py-1 text-[10px] uppercase tracking-wider transition ${
                mode === i ? "bg-[#5FD4E4] text-[#08131F]" : "border border-[#5FD4E4]/30 text-[#5FD4E4]/70"}`}>
              {m}
            </button>
          ))}
        </div>

        <button onClick={copy}
          className="mb-4 w-full rounded border border-[#5FD4E4]/40 py-1.5 text-[10px] uppercase tracking-widest text-[#5FD4E4] hover:bg-[#5FD4E4]/10">
          {copied ? "copied ✓" : "copy params"}
        </button>

        {Object.entries(groups).map(([gname, group]) => (
          <section key={gname} className="mb-4">
            <h2 className="mb-1.5 border-b border-[#5FD4E4]/15 pb-1 text-[10px] uppercase tracking-[0.2em] text-[#5FD4E4]">
              {gname}
            </h2>
            <div className="space-y-1.5">
              {Object.entries(group).map(([k, p]) => <Slider key={k} g={gname} k={k} p={p} />)}
            </div>
          </section>
        ))}

        <section className="mb-4">
          <h2 className="mb-1.5 border-b border-[#5FD4E4]/15 pb-1 text-[10px] uppercase tracking-[0.2em] text-[#F2A65A]">
            build · rebuilds geometry
          </h2>
          <div className="space-y-1.5">
            {Object.entries(buildP).map(([k, p]) => (
              <label key={k} className="block">
                <span className="flex justify-between gap-2 text-[10px] text-[#8FB4C9]">
                  <span className="truncate">{p.label}</span>
                  <em className="not-italic tabular-nums text-[#C4F8FF]">{p.v}</em>
                </span>
                <input
                  type="range" min={p.min} max={p.max} step={p.step} value={p.v}
                  onChange={(e) => setBuildP((b) => ({ ...b, [k]: { ...b[k], v: Number(e.target.value) } }))}
                  className="mt-0.5 w-full accent-[#F2A65A]"
                />
              </label>
            ))}
          </div>
        </section>
      </aside>
    </div>
  );
}
