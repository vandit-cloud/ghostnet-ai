import clsx from "clsx";
import type { HTMLAttributes, ReactNode } from "react";

type Tone = "none" | "accent" | "tint" | "critical" | "unknown" | "blue";

/* Atlantic has no glass and no glow, so "emphasis" cannot be a halo any more.
 * Each tone is a change of GROUND instead -- which is what the mockup does, and
 * which survives the greyscale test a coloured shadow does not. */
const TONE_CLASSES: Record<Tone, string> = {
  none: "",
  // The one loud card on a screen: imperial fill, paper contents.
  accent: "panel-accent",
  // The quiet pick-out: a sky wash, still dark ink.
  tint: "panel-tint",
  // Chrome that shows water rather than data.
  blue: "panel-blue",
  critical: "panel-critical",
  unknown: "panel-unknown",
};

/**
 * The shared surface for every card in the console.
 *
 * `.panel` in globals.css carries the geometry (1px rule, paper ground, square
 * corners); this adds the tone. `glow` is kept as an alias for `tone` because
 * roughly thirty call sites pass it, and renaming them all in the same change
 * as the retheme would make both harder to review.
 */
export function Panel({
  children,
  className,
  tone,
  glow,
  ...rest
}: {
  children: ReactNode;
  className?: string;
  tone?: Tone;
  /** @deprecated Alias for `tone`, kept for the existing call sites. */
  glow?: "none" | "cyan" | "critical" | "unknown";
} & HTMLAttributes<HTMLDivElement>) {
  // "cyan" was the old accent's name; in Atlantic that emphasis is the sky tint.
  const resolved: Tone = tone ?? (glow === "cyan" ? "tint" : (glow as Tone) ?? "none");

  return (
    <div className={clsx("panel p-4", TONE_CLASSES[resolved], className)} {...rest}>
      {children}
    </div>
  );
}
