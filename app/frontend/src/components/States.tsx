import type { ReactNode } from "react";

import { Panel } from "@/components/Panel";

/* Loading, empty and error, in Atlantic.
 *
 * The skeleton used to be a cyan-lit gradient sweeping across a dark bar, which
 * on paper reads as a smear. It is now a flat rule-coloured block with a slow
 * pulse: quieter, and it does not pretend to be content. */
export function LoadingSkeleton({ rows = 3, label }: { rows?: number; label?: string }) {
  return (
    <div className="space-y-2.5" role="status" aria-live="polite">
      {label ? (
        <p className="font-mono text-[10.5px] uppercase tracking-[0.12em] text-ink-3">{label}</p>
      ) : null}
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-10 w-full animate-pulse bg-rule-2" />
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
      <p className="font-mono text-[10.5px] uppercase tracking-[0.18em] text-ink-3">
        No active data
      </p>
      <p className="font-display text-[27px] font-extrabold uppercase leading-[0.94] text-imperial">
        {title}
      </p>
      {description ? (
        <p className="max-w-md text-sm font-light leading-[1.66] text-ink-2">{description}</p>
      ) : null}
      {action}
    </Panel>
  );
}

/* The error state keeps the mockup's banner construction -- a heavy leading
 * edge and a tinted ground -- rather than a centred notice, because an error
 * here is nearly always something the operator has to act on. */
export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex items-center gap-4 border border-alert-critical/40 border-l-[5px] border-l-alert-critical bg-alert-critical/[0.06] px-5 py-4">
      <p className="shrink-0 font-display text-[24px] font-extrabold uppercase leading-none tracking-[0.03em] text-alert-critical">
        Error
      </p>
      <p className="flex-1 text-[13.5px] font-light leading-[1.6] text-ink-2">{message}</p>
      {onRetry ? (
        <button
          onClick={onRetry}
          className="shrink-0 border border-alert-critical px-4 py-2 font-mono text-[10.5px] uppercase tracking-[0.12em] text-alert-critical transition hover:bg-alert-critical hover:text-paper"
        >
          Retry
        </button>
      ) : null}
    </div>
  );
}
