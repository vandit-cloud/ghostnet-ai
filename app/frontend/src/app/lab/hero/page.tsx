"use client";

import dynamic from "next/dynamic";
import { useRef, useState } from "react";

import { usePageVisible } from "@/hooks/usePageVisible";
import { useScrollProgress } from "@/hooks/useScrollProgress";
import {
  STAGE_DEPLOY_END,
  STAGE_IDLE_END,
  STAGE_SEARCH_END,
} from "@/components/three/hero/stages";

const HeroScene = dynamic(
  () => import("@/components/three/hero/HeroScene").then((m) => m.HeroScene),
  { ssr: false, loading: () => <div className="h-full w-full bg-trench-950" /> }
);

const MARKS = [
  { at: 0, name: "idle" },
  { at: STAGE_IDLE_END, name: "deploy" },
  { at: STAGE_DEPLOY_END, name: "search" },
  { at: STAGE_SEARCH_END, name: "contact" },
  { at: 1, name: "end" },
];

/** Isolated sandbox for the scroll hero - NOT the landing page.
 *
 * Deliberately separate so the sequence can be tuned without touching the
 * console, without deciding the Atlantic palette question, and without an
 * unfinished animation ever being on a route a judge might open. It runs on
 * the repo's current cyan scale; only when the timing is signed off does any
 * of this move to a public route.
 *
 * Two drive modes, because they answer different questions:
 *   scroll - is the PACING right against real scrolling?
 *   scrub  - does each STAGE look right, held still?
 */
export default function HeroLabPage() {
  const container = useRef<HTMLDivElement>(null);
  const { progress, settled } = useScrollProgress(container);
  const pageVisible = usePageVisible();

  const [mode, setMode] = useState<"scroll" | "scrub">("scroll");
  const [scrub, setScrub] = useState(0);
  const manual = useRef(0);
  manual.current = scrub;

  const driver = mode === "scroll" ? progress : manual;
  const shown = mode === "scroll" ? settled : scrub;

  return (
    <div ref={container} style={{ height: "420vh" }} className="relative bg-trench-950">
      <div className="sticky top-0 h-screen w-full overflow-hidden">
        <HeroScene progress={driver} paused={!pageVisible} />

        <div className="pointer-events-none absolute inset-0 flex items-center">
          <div className="max-w-md px-10">
            <p className="font-mono text-xs uppercase tracking-[0.3em] text-cyan-accent">
              GhostNet-AI
            </p>
            <h1 className="mt-3 font-display text-5xl leading-tight text-foam-300">
              We find what the ocean was never meant to keep.
            </h1>
            <p className="mt-4 text-sm text-foam-300/60">
              Placeholder copy. The left column is the text lane; the vessel is
              parked on the right so the two never collide.
            </p>
          </div>
        </div>

        {/* ---- sandbox instrumentation, never ships to a public route ---- */}
        <div className="absolute bottom-6 left-1/2 w-[min(680px,92vw)] -translate-x-1/2 rounded-xl border border-cyan-accent/25 bg-abyss-950/85 p-4 backdrop-blur">
          <div className="flex items-center gap-3">
            {(["scroll", "scrub"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`rounded-md px-3 py-1 font-mono text-xs uppercase tracking-widest transition ${
                  mode === m
                    ? "bg-cyan-accent text-abyss-950"
                    : "border border-cyan-accent/30 text-cyan-accent/70"
                }`}
              >
                {m}
              </button>
            ))}
            <span className="ml-auto font-mono text-xs text-foam-300/70">
              p = {shown.toFixed(3)}
            </span>
          </div>

          <input
            type="range"
            min={0}
            max={1}
            step={0.001}
            value={scrub}
            disabled={mode !== "scrub"}
            onChange={(e) => setScrub(Number(e.target.value))}
            className="mt-3 w-full accent-cyan-accent disabled:opacity-30"
          />

          <div className="mt-2 flex justify-between font-mono text-[10px] uppercase tracking-wider text-foam-300/50">
            {MARKS.map((m) => (
              <button
                key={m.name}
                onClick={() => {
                  setMode("scrub");
                  setScrub(m.at);
                }}
                className="hover:text-cyan-accent"
              >
                {m.name}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
