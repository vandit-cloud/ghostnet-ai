import clsx from "clsx";
import type { HTMLAttributes, ReactNode } from "react";

type Glow = "none" | "cyan" | "critical" | "unknown";

const GLOW_CLASSES: Record<Glow, string> = {
  none: "",
  cyan: "shadow-glow-cyan border-cyan-accent/50",
  critical: "shadow-glow-critical border-alert-critical/50",
  unknown: "shadow-glow-unknown border-alert-unknown/50",
};

/** Shared surface for every card/panel in the app (spec: avoid the "generic
 * SaaS admin panel" flat-box look). A subtle top-edge highlight + gradient
 * surface instead of a plain border-everywhere box. `glow` is opt-in and
 * reserved for the spec's explicit glow list (selected / critical / live
 * system state) — never the default. */
export function Panel({
  children,
  className,
  glow = "none",
  ...rest
}: { children: ReactNode; className?: string; glow?: Glow } & HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={clsx("panel p-4 transition-shadow", GLOW_CLASSES[glow], className)} {...rest}>
      {children}
    </div>
  );
}
