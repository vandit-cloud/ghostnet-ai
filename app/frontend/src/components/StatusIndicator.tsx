import clsx from "clsx";

import type { ConnectionStatus } from "@/hooks/useRealtime";

const LABELS: Record<ConnectionStatus, string> = {
  connecting: "Connecting…",
  connected: "Live",
  reconnecting: "Reconnecting…",
  offline: "Offline",
};

/* Atlantic has no glow, and this dot was carrying the last one: an 8px mint
 * bloom written as an arbitrary-value shadow, which routed around the theme's
 * boxShadow remap entirely. The colour was stock `emerald-400` for the same
 * reason -- `theme.extend` merges, so the step nobody remapped stayed neon.
 *
 * The state is also not colour alone: the label beside the dot always spells it
 * out, and the two indeterminate states pulse while the two settled ones do
 * not. */
const DOT_STYLES: Record<ConnectionStatus, string> = {
  connecting: "bg-ink-3 animate-pulse",
  connected: "bg-emerald-500",
  reconnecting: "bg-alert-high animate-pulse",
  offline: "bg-alert-critical",
};

export function StatusIndicator({ status }: { status: ConnectionStatus }) {
  return (
    <div className="flex items-center gap-2 font-mono text-[10.5px] uppercase tracking-[0.1em] text-ink-2">
      <span className={clsx("h-2 w-2 rounded-full", DOT_STYLES[status])} aria-hidden="true" />
      {LABELS[status]}
    </div>
  );
}
