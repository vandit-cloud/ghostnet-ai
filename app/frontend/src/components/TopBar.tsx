"use client";

import { useRouter } from "next/navigation";

import { useAuthStore } from "@/state/auth-store";

export function TopBar({ title, onMenuClick }: { title: string; onMenuClick?: () => void }) {
  const router = useRouter();
  const displayName = useAuthStore((s) => s.displayName);
  const clearSession = useAuthStore((s) => s.clearSession);

  return (
    <header className="flex items-center justify-between border-b border-abyss-600/70 bg-trench-950/80 px-4 py-4 backdrop-blur-xl sm:px-6">
      <div className="flex min-w-0 items-center gap-3">
        <button
          onClick={onMenuClick}
          aria-label="Open menu"
          className="-ml-1 rounded-xl border border-abyss-600/70 bg-abyss-900/70 p-1.5 text-slate-300 hover:border-cyan-accent/30 hover:bg-abyss-700/60 md:hidden"
        >
          <svg width="22" height="22" viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
            <path d="M3 6h16" />
            <path d="M3 11h16" />
            <path d="M3 16h16" />
          </svg>
        </button>
        <div className="min-w-0">
          <p className="text-[11px] uppercase tracking-[0.32em] text-cyan-accent/80">Operational Console</p>
          <h1 className="truncate font-display text-xl font-semibold text-slate-100">{title}</h1>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2 sm:gap-3">
        <div className="hidden rounded-full border border-cyan-accent/20 bg-cyan-accent/10 px-3 py-1 text-[11px] uppercase tracking-[0.28em] text-cyan-accent lg:inline-flex">
          Secure Link
        </div>
        {displayName ? (
          <span className="hidden rounded-full border border-abyss-600/80 bg-white/[0.03] px-3 py-1.5 text-sm text-slate-300 sm:inline">
            {displayName}
          </span>
        ) : null}
        <button
          onClick={() => {
            clearSession();
            router.push("/auth/login");
          }}
          className="rounded-full border border-abyss-600/80 bg-white/[0.03] px-3 py-1.5 text-xs font-medium uppercase tracking-[0.22em] text-slate-300 transition hover:border-cyan-accent/50 hover:text-cyan-accent"
        >
          Log Out
        </button>
      </div>
    </header>
  );
}
