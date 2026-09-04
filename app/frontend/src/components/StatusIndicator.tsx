import clsx from "clsx";

import type { ConnectionStatus } from "@/hooks/useRealtime";

const LABELS: Record<ConnectionStatus, string> = {
  connecting: "Connecting…",
  connected: "Live",
  reconnecting: "Reconnecting…",
  offline: "Offline",
};

const DOT_STYLES: Record<ConnectionStatus, string> = {
  connecting: "bg-slate-400 animate-pulse",
  connected: "bg-emerald-400 shadow-[0_0_0_2px_rgba(52,211,153,0.25),0_0_8px_rgba(52,211,153,0.6)]",
  reconnecting: "bg-alert-medium animate-pulse",
  offline: "bg-alert-critical",
};

export function StatusIndicator({ status }: { status: ConnectionStatus }) {
  return (
    <div className="flex items-center gap-2 text-xs text-slate-400">
      <span className={clsx("h-2 w-2 rounded-full", DOT_STYLES[status])} />
      {LABELS[status]}
    </div>
  );
}
