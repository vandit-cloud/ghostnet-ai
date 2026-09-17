import type { Metadata } from "next";

import { HeroSection } from "@/features/landing/HeroSection";
import { CtaBand, LandingFooter } from "@/features/landing/LandingFooter";
import { LandingNav } from "@/features/landing/LandingNav";
import {
  DetectionSection,
  EvidenceSection,
  MethodSection,
  OutputsSection,
  SpecSection,
} from "@/features/landing/LandingSections";

import "@/features/landing/landing.css";

/* =============================================================================
 * The public landing page.
 *
 * `/` used to redirect straight into /app/dashboard, which meant the project
 * had no front door: anyone arriving at the URL was dropped into an operational
 * console behind an auth gate, with nothing explaining what the thing is or
 * what its numbers mean. This is that front door.
 *
 * Its design is the finalised Atlantic direction, ported from the standalone
 * demo — see scripts/port_hero_scene.py and scripts/port_landing_css.py for
 * what was copied and what was adapted. The console still lives at /app/*.
 *
 * Everything except the hero is a server component. The hero is the only part
 * with a lifecycle, and three.js is code-split behind it.
 * ========================================================================== */

export const metadata: Metadata = {
  title: "GhostNet-AI — find the nets the ocean kept hidden",
  description:
    "GhostNet-AI reads side-scan sonar and flags abandoned fishing gear as polygons, not pins — with calibrated confidence and a human review gate.",
};

export default function LandingPage() {
  return (
    <div className="landing">
      <LandingNav />
      <HeroSection />
      <DetectionSection />
      <OutputsSection />
      <MethodSection />
      <EvidenceSection />
      <SpecSection />
      <CtaBand />
      <LandingFooter />
    </div>
  );
}
