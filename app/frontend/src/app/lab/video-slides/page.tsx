"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

import { useReducedMotion } from "@/hooks/useReducedMotion";

/** Full-screen title, proof and closing slides for the demo video -- NOT a
 * product route, and not linked from the console.
 *
 * Built to be screen-recorded in the same browser as the app, so the fonts and
 * colours match the footage around it. There is no voiceover in the video, so
 * every slide has to read on its own: short lines, revealed in sequence.
 *
 *   → / Space / PageDown / click   next slide
 *   ← / PageUp                     previous slide
 *   1 2 3                          jump to a slide
 *   ?s=2                           open on the proof slide (1-based)
 *   ?team=Team%20Name              team name on the closing card (hidden if absent)
 *
 * The cursor and the key hint hide after 1.5 s without mouse movement, so a
 * recording started with the mouse still shows neither.
 *
 * Every number on the proof slide is a measured result; see the comments on
 * PROOF for where each one comes from before changing any of them.
 */

const VIRIDIS = "linear-gradient(90deg, #440154, #3b528b 25%, #21918c 50%, #5ec962 75%, #fde725)";

/** Measured results only. Sources:
 *  - 8 in 10 / 6 in 10: centroid hit rate, gvU1n U-Net 0.807 +/- 0.042 (3 seeds)
 *    against gv7d3 YOLO-seg 0.607, ai/experiments/unet-scoring/RESULTS.md.
 *  - 1.3% / 42%: false alarms on empty seabed chips, same comparison.
 *  - 12 s: 40-frame NBP0505 line, full pipeline incl. U-Net, RTX 3050, 29 Sep
 *    2026 (11.8 s measured).
 *  - The "tested on" line: demo/NBP0505_line01B_demo.xtf is a byte-exact slice
 *    of RV Nathaniel B. Palmer cruise NBP0505 line 01B (2005, off Golfo de
 *    Penas, Patagonia), public data from the Marine Geoscience Data System;
 *    see demo/RAW_DATA.md. It is real archival research data, not an official
 *    or ghost-net survey, so the slide says exactly that and nothing more.
 *  - 0 above 50%: Klein 5000 V2 sea survey, ~2.1 km2, never in training; the
 *    highest calibrated confidence was 0.48 (klein-2019-eval v3, 29 Sep 2026). */
const PROOF = [
  { value: 8, suffix: " in 10", decimals: 0, label: "ghost-net sections found", note: "A standard detector finds 6 in 10" },
  { value: 1.3, suffix: "%", decimals: 1, label: "false alarms on empty seabed", note: "The standard detector: 42%" },
  { value: 12, suffix: " s", decimals: 0, label: "to process a 40‑frame survey line", note: "Measured on the survey below" },
  { value: 0, suffix: "", decimals: 0, label: "alarms above 50% confidence", note: "On 2.1 km² from a sonar it never trained on" },
];

export default function VideoSlidesPage() {
  return (
    <Suspense fallback={<div className="fixed inset-0 bg-[#07203a]" />}>
      <Slides />
    </Suspense>
  );
}

function Slides() {
  const params = useSearchParams();
  const team = params.get("team")?.trim() || "";
  const start = Math.min(3, Math.max(1, Number(params.get("s")) || 1)) - 1;
  const [slide, setSlide] = useState(start);
  const [idle, setIdle] = useState(true);
  const reduced = useReducedMotion();
  const count = 3;

  const go = useCallback((n: number) => setSlide(() => Math.min(count - 1, Math.max(0, n))), []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (["ArrowRight", " ", "PageDown", "Enter"].includes(e.key)) { e.preventDefault(); setSlide((s) => Math.min(count - 1, s + 1)); }
      else if (["ArrowLeft", "PageUp", "Backspace"].includes(e.key)) { e.preventDefault(); setSlide((s) => Math.max(0, s - 1)); }
      else if (/^[1-3]$/.test(e.key)) go(Number(e.key) - 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go]);

  // Hide the cursor and the hint while the mouse is still.
  const idleTimer = useRef<ReturnType<typeof setTimeout>>();
  useEffect(() => {
    const onMove = () => {
      setIdle(false);
      clearTimeout(idleTimer.current);
      idleTimer.current = setTimeout(() => setIdle(true), 1500);
    };
    window.addEventListener("mousemove", onMove);
    return () => { window.removeEventListener("mousemove", onMove); clearTimeout(idleTimer.current); };
  }, []);

  return (
    <main
      className="fixed inset-0 select-none overflow-hidden bg-[#07203a] text-paper"
      style={{ cursor: idle ? "none" : "default" }}
      onClick={() => setSlide((s) => Math.min(count - 1, s + 1))}
    >
      {/* The console's 14 px imperial band, so the slides read as the same product. */}
      <div className="absolute inset-x-0 top-0 z-10 h-[14px] bg-imperial" />
      <Backdrop />
      <Frame active={slide === 0} reduced={reduced}><TitleSlide active={slide === 0} reduced={reduced} /></Frame>
      <Frame active={slide === 1} reduced={reduced}><ProofSlide active={slide === 1} reduced={reduced} /></Frame>
      <Frame active={slide === 2} reduced={reduced}><ClosingSlide active={slide === 2} reduced={reduced} team={team} /></Frame>
      <div
        className="absolute bottom-5 right-6 z-20 font-mono text-[11px] uppercase tracking-[0.2em] text-skytint/70 transition-opacity duration-300"
        style={{ opacity: idle ? 0 : 1 }}
        aria-hidden
      >
        {slide + 1} / {count} · ← → to move
      </div>
    </main>
  );
}

/** The same SVG turbulence the console's `.grain` uses. Drawn as its own layer:
 *  `.grain` sets `position: relative`, which beat `absolute` here and collapsed
 *  the backdrop to zero height. */
const GRAIN = "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='260' height='260'><filter id='g'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/><feColorMatrix type='saturate' values='0'/></filter><rect width='260' height='260' filter='url(%23g)' opacity='0.5'/></svg>\")";

/** Deep water: the processing scene's navy, lifting to Atlantic at the top. */
function Backdrop() {
  return (
    <>
      <div
        className="absolute inset-0"
        style={{ background: "radial-gradient(120% 90% at 50% 0%, #0F4B70 0%, #0B3A58 38%, #07203a 72%, #041626 100%)" }}
        aria-hidden
      />
      <div className="pointer-events-none absolute inset-0" style={{ backgroundImage: GRAIN, mixBlendMode: "multiply", opacity: 0.13 }} aria-hidden />
    </>
  );
}

function Frame({ active, reduced, children }: { active: boolean; reduced: boolean; children: React.ReactNode }) {
  return (
    <section
      className="absolute inset-0 flex items-center justify-center px-[6vw] pt-[14px]"
      style={{ opacity: active ? 1 : 0, transition: reduced ? "none" : "opacity 600ms ease", pointerEvents: active ? "auto" : "none" }}
      aria-hidden={!active}
    >
      {children}
    </section>
  );
}

/** Staggered entrance: each child rises in `delay` ms after the slide opens. */
function Reveal({ active, reduced, delay, children, className = "" }: {
  active: boolean; reduced: boolean; delay: number; children: React.ReactNode; className?: string;
}) {
  const [shown, setShown] = useState(false);
  useEffect(() => {
    if (!active) { setShown(false); return; }
    if (reduced) { setShown(true); return; }
    const id = setTimeout(() => setShown(true), delay);
    return () => clearTimeout(id);
  }, [active, reduced, delay]);
  return (
    <div
      className={className}
      style={{
        opacity: shown ? 1 : 0,
        transform: shown ? "none" : "translateY(18px)",
        transition: reduced ? "none" : "opacity 700ms ease, transform 700ms cubic-bezier(.2,.7,.2,1)",
      }}
    >
      {children}
    </div>
  );
}

function Kicker({ children }: { children: React.ReactNode }) {
  return <p className="font-mono text-[clamp(11px,0.85vw,16px)] uppercase tracking-[0.32em] text-skytint/85">{children}</p>;
}

function ViridisRule({ className = "" }: { className?: string }) {
  return <div className={`h-[3px] ${className}`} style={{ background: VIRIDIS }} aria-hidden />;
}

function TitleSlide({ active, reduced }: { active: boolean; reduced: boolean }) {
  return (
    <div className="w-full max-w-[1300px]">
      <Reveal active={active} reduced={reduced} delay={150}><Kicker>SIH26057 · Marine debris detection</Kicker></Reveal>
      <Reveal active={active} reduced={reduced} delay={450}>
        <h1 className="mt-5 font-display text-[clamp(44px,6.2vw,120px)] font-black uppercase leading-[0.95] text-paper">
          Lost fishing nets<br />keep catching marine life<br />for years.
        </h1>
      </Reveal>
      <Reveal active={active} reduced={reduced} delay={1500}>
        <p className="mt-8 max-w-[900px] text-[clamp(18px,1.7vw,32px)] leading-snug text-paper/85">
          Side-scan sonar can find them. But one survey is thousands of noisy frames, far too many for people to read.
        </p>
      </Reveal>
      <Reveal active={active} reduced={reduced} delay={2700}>
        <ViridisRule className="mt-10 w-[min(420px,40vw)]" />
        <p className="mt-6 font-display text-[clamp(32px,3.6vw,68px)] font-black uppercase leading-none text-skytint">
          GhostNet-AI reads them.
        </p>
      </Reveal>
    </div>
  );
}

/** Counts up from 0 once, when its slide opens. */
function CountUp({ active, reduced, value, decimals, delay }: {
  active: boolean; reduced: boolean; value: number; decimals: number; delay: number;
}) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    if (!active) { setShown(0); return; }
    if (reduced || value === 0) { setShown(value); return; }
    let raf = 0;
    const t0 = performance.now() + delay;
    const step = (t: number) => {
      const k = Math.min(1, Math.max(0, (t - t0) / 1100));
      setShown(value * (1 - Math.pow(1 - k, 3)));
      if (k < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [active, reduced, value, delay]);
  return <>{shown.toFixed(decimals)}</>;
}

function ProofSlide({ active, reduced }: { active: boolean; reduced: boolean }) {
  return (
    <div className="w-full max-w-[1500px]">
      <Reveal active={active} reduced={reduced} delay={100}><Kicker>Measured, not claimed</Kicker></Reveal>
      <Reveal active={active} reduced={reduced} delay={300}>
        <h2 className="mt-4 font-display text-[clamp(38px,4.6vw,88px)] font-black uppercase leading-none text-paper">
          What the numbers say
        </h2>
        <ViridisRule className="mt-6 w-[min(420px,40vw)]" />
      </Reveal>
      <div className="mt-[5vh] grid grid-cols-2 gap-[1.6vw] lg:grid-cols-4">
        {PROOF.map((p, i) => (
          <Reveal key={p.label} active={active} reduced={reduced} delay={700 + i * 450}>
            <div className="h-full border border-skytint/25 bg-[#07203a]/55 p-[1.6vw] backdrop-blur-sm">
              <p className="font-display text-[clamp(52px,5.8vw,112px)] font-black leading-none text-paper tabular-nums">
                <CountUp active={active} reduced={reduced} value={p.value} decimals={p.decimals} delay={700 + i * 450} />
                <span className="text-skytint">{p.suffix}</span>
              </p>
              <p className="mt-3 text-[clamp(16px,1.35vw,26px)] font-medium leading-tight text-paper [text-wrap:balance]">{p.label}</p>
              <p className="mt-2 font-mono text-[clamp(11px,0.85vw,15px)] leading-snug tracking-[0.04em] text-skytint/80 [text-wrap:balance]">{p.note}</p>
            </div>
          </Reveal>
        ))}
      </div>
      <Reveal active={active} reduced={reduced} delay={2600}>
        <div className="mt-[3.5vh] flex items-center gap-4 border-l-[3px] border-[#5ec962] bg-[#07203a]/55 px-5 py-3 backdrop-blur-sm">
          <svg viewBox="0 0 20 20" className="h-[clamp(18px,1.4vw,26px)] w-[clamp(18px,1.4vw,26px)] shrink-0 text-[#5ec962]" aria-hidden>
            <path d="M3 10.5l4.2 4.2L17 5" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <div>
            <p className="text-[clamp(15px,1.3vw,24px)] leading-snug text-paper">
              <span className="font-medium">Tested on real archived survey data:</span>{" "}
              <span className="text-skytint">RV Nathaniel B. Palmer, cruise NBP0505 (2005), Golfo de Penas, Patagonia</span>
            </p>
            <p className="mt-1 font-mono text-[clamp(11px,0.85vw,15px)] tracking-[0.04em] text-paper/65">
              Public side-scan data · Marine Geoscience Data System (MGDS)
            </p>
          </div>
        </div>
      </Reveal>
      <Reveal active={active} reduced={reduced} delay={3000}>
        <p className="mt-[3vh] max-w-[1100px] font-mono text-[clamp(11px,0.9vw,16px)] leading-relaxed tracking-[0.03em] text-paper/70">
          Ghost-net results come from a small test set (11 image tiles from 2 sites), so every net detection stays
          review-only until a person confirms it.
        </p>
      </Reveal>
    </div>
  );
}

function ClosingSlide({ active, reduced, team }: { active: boolean; reduced: boolean; team: string }) {
  const steps = ["Raw sonar in", "Verified detections", "Mapped · reviewed · reported"];
  return (
    <div className="flex w-full max-w-[1400px] flex-col items-center text-center">
      <Reveal active={active} reduced={reduced} delay={150}>
        {/* The sidebar's wordmark, scaled up: solid "Ghost", sky-stroked "Net". */}
        <p className="font-display text-[clamp(64px,9vw,176px)] font-black uppercase leading-none text-paper">
          Ghost
          <i className="not-italic text-transparent [-webkit-text-stroke:3px_theme(colors.skytint.DEFAULT)]">Net</i>
          -AI
        </p>
      </Reveal>
      <Reveal active={active} reduced={reduced} delay={650}>
        <p className="mt-5 font-mono text-[clamp(13px,1.1vw,20px)] uppercase tracking-[0.3em] text-skytint/90">
          Marine sonar intelligence for ghost gear
        </p>
        <ViridisRule className="mx-auto mt-8 w-[min(520px,50vw)]" />
      </Reveal>
      <div className="mt-[6vh] flex flex-wrap items-center justify-center gap-x-[1.4vw] gap-y-3">
        {steps.map((s, i) => (
          <Reveal key={s} active={active} reduced={reduced} delay={1200 + i * 500} className="flex items-center gap-[1.4vw]">
            {i > 0 && (
              <svg viewBox="0 0 32 16" className="h-[clamp(12px,1.1vw,20px)] w-[clamp(24px,2.2vw,40px)] text-skytint/70" aria-hidden>
                <path d="M0 8h29M22 1l8 7-8 7" fill="none" stroke="currentColor" strokeWidth="2" />
              </svg>
            )}
            <span className="border border-skytint/30 bg-[#07203a]/55 px-[1.4vw] py-[0.9vh] text-[clamp(16px,1.5vw,30px)] font-medium text-paper">
              {s}
            </span>
          </Reveal>
        ))}
      </div>
      <Reveal active={active} reduced={reduced} delay={2900}>
        <p className="mt-[7vh] font-mono text-[clamp(12px,1vw,18px)] uppercase tracking-[0.28em] text-paper/75">
          SIH26057{team ? ` · ${team}` : ""}
        </p>
      </Reveal>
    </div>
  );
}
