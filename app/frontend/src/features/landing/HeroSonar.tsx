"use client";

import dynamic from "next/dynamic";
import { useRef } from "react";

import { useIsCompact } from "@/hooks/useIsCompact";
import { useReducedMotion } from "@/hooks/useReducedMotion";
import { usePageVisible } from "@/hooks/usePageVisible";
import { useScrollProgress } from "@/hooks/useScrollProgress";
import { STAGE_DEPLOY_END, STAGE_IDLE_END, STAGE_SEARCH_END } from "@/components/three/hero/stages";

const HeroScene = dynamic(() => import("@/components/three/hero/HeroScene").then((m) => m.HeroScene), {
  ssr: false,
  loading: () => <div className="h-full w-full bg-trench-950" />,
});

const STAGES = [
  { until: STAGE_IDLE_END, label: "On station", detail: "Survey vessel holding the line." },
  { until: STAGE_DEPLOY_END, label: "Deploying", detail: "Towfish away, cable paying out." },
  { until: STAGE_SEARCH_END, label: "Ensonifying", detail: "Side-scan swath open, seabed painting." },
  { until: 1.01, label: "Contact", detail: "Ghost net returned. Flagged for review." },
];

/** The scroll-driven hero.
 *
 * The Canvas is position:sticky inside a tall container - the container's
 * height IS the length of the animation, so `HERO_SCROLL_VH` is the single
 * knob for how much scrolling the whole sequence takes. */
const HERO_SCROLL_VH = 420;

export function HeroSonar({ children }: { children?: React.ReactNode }) {
  const container = useRef<HTMLDivElement>(null);
  const { progress, settled } = useScrollProgress(container);
  const compact = useIsCompact();
  const reducedMotion = useReducedMotion();
  const pageVisible = usePageVisible();

  // Phones and reduced-motion users get a still frame, never a blank space.
  // Scroll-jacking a touch device is unpleasant, and an empty hero is worse
  // than a simple one.
  if (compact || reducedMotion) {
    return (
      <section className="relative overflow-hidden bg-trench-950">
        <div
          className="h-[70vh] min-h-[420px] w-full bg-cover bg-center"
          style={{ backgroundImage: "url(/models/hero-poster.jpg)" }}
          role="img"
          aria-label="Survey vessel towing a side-scan sonar over the seabed"
        />
        <div className="absolute inset-0 flex items-center px-6">{children}</div>
      </section>
    );
  }

  const stage = STAGES.find((s) => settled < s.until) ?? STAGES[STAGES.length - 1];

  return (
    <div ref={container} style={{ height: `${HERO_SCROLL_VH}vh` }} className="relative">
      <div className="sticky top-0 h-screen w-full overflow-hidden bg-trench-950">
        <HeroScene progress={progress} paused={!pageVisible} />

        <div className="pointer-events-none absolute inset-0 flex items-center">
          <div className="pointer-events-auto w-full max-w-xl px-8 md:px-16">{children}</div>
        </div>

        <div className="pointer-events-none absolute bottom-10 left-8 md:left-16">
          <p className="font-mono text-xs uppercase tracking-[0.3em] text-cyan-accent">{stage.label}</p>
          <p className="mt-1 text-sm text-foam-300/70">{stage.detail}</p>
        </div>
      </div>
    </div>
  );
}
