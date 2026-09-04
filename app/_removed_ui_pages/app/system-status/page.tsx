"use client";

import clsx from "clsx";

import { AppShell } from "@/components/AppShell";
import { ErrorState, LoadingSkeleton } from "@/components/States";
import { useSystemStatus } from "@/features/system/hooks";
import type { SystemComponentState } from "@/types";

const STATE_STYLES: Record<SystemComponentState, string> = {
  ONLINE: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
  ACTIVE: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
  LIVE: "border-cyan-accent/50 bg-cyan-accent/10 text-cyan-accent",
  CONNECTING: "border-alert-medium/40 bg-alert-medium/10 text-alert-medium",
  STALE: "border-alert-medium/40 bg-alert-medium/10 text-alert-medium",
  OFFLINE: "border-slate-600/40 bg-slate-700/20 text-slate-400",
  ERROR: "border-alert-critical/40 bg-alert-critical/10 text-alert-critical",
};

const DOT_STYLES: Record<SystemComponentState, string> = {
  ONLINE: "bg-emerald-400",
  ACTIVE: "bg-emerald-400",
  LIVE: "bg-cyan-accent animate-pulse",
  CONNECTING: "bg-alert-medium animate-pulse",
  STALE: "bg-alert-medium",
  OFFLINE: "bg-slate-500",
  ERROR: "bg-alert-critical",
};

export default function SystemStatusPage() {
  const { data, isLoading, isError, refetch, dataUpdatedAt } = useSystemStatus();

  return (
    <AppShell title="System Status">
      {isLoading ? (
        <LoadingSkeleton rows={6} label="Checking system components…" />
      ) : isError || !data ? (
        <ErrorState message="Unable to reach the backend to check system status." onRetry={() => refetch()} />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {data.components.map((c) => (
              <div key={c.name} className={clsx("rounded-lg border p-4", STATE_STYLES[c.state])}>
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-slate-100">{c.name}</p>
                  <span className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide">
                    <span className={clsx("h-1.5 w-1.5 rounded-full", DOT_STYLES[c.state])} />
                    {c.state}
                  </span>
                </div>
                {c.detail && <p className="mt-2 text-xs text-slate-400">{c.detail}</p>}
              </div>
            ))}
          </div>
          <p className="mt-4 text-xs text-slate-500">
            Last checked {dataUpdatedAt ? new Date(dataUpdatedAt).toLocaleTimeString() : "—"}. Refreshes automatically every 10s.
          </p>
        </>
      )}
    </AppShell>
  );
}
