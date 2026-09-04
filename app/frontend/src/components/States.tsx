import type { ReactNode } from "react";

import { Panel } from "@/components/Panel";

export function LoadingSkeleton({ rows = 3, label }: { rows?: number; label?: string }) {
  return (
    <div className="space-y-3" role="status" aria-live="polite">
      {label ? <p className="text-sm text-slate-400">{label}</p> : null}
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="h-10 w-full animate-pulse rounded-2xl border border-abyss-600/40 bg-gradient-to-r from-abyss-700/60 via-teal-glass/60 to-abyss-700/60"
        />
      ))}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <Panel className="flex flex-col items-center justify-center gap-3 px-6 py-12 text-center">
      <p className="text-[11px] uppercase tracking-[0.3em] text-cyan-accent/75">No Active Data</p>
      <p className="text-lg font-semibold text-slate-100">{title}</p>
      {description ? <p className="max-w-md text-sm leading-7 text-slate-400">{description}</p> : null}
      {action}
    </Panel>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <Panel glow="critical" className="flex flex-col items-center justify-center gap-3 border-alert-critical/40 bg-alert-critical/5 px-6 py-10 text-center">
      <p className="text-[11px] uppercase tracking-[0.28em] text-alert-critical/80">System Warning</p>
      <p className="text-sm font-medium text-alert-critical">{message}</p>
      {onRetry ? (
        <button
          onClick={onRetry}
          className="rounded-full border border-alert-critical/50 px-4 py-2 text-sm text-alert-critical transition hover:bg-alert-critical/10"
        >
          Retry
        </button>
      ) : null}
    </Panel>
  );
}
