"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";

import { NAV_ITEMS } from "@/utils/nav";

export function Sidebar() {
  const pathname = usePathname();

  return (
    <nav className="hidden w-72 shrink-0 flex-col overflow-y-auto border-r border-abyss-600/70 bg-trench-950/90 px-4 py-5 md:flex">
      <div className="panel mb-6 px-4 py-4">
        <div className="flex items-start gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-cyan-accent/30 bg-cyan-accent/10 text-xs font-semibold tracking-[0.28em] text-cyan-accent">
            GN
          </div>
          <div className="min-w-0">
            <p className="font-display text-lg font-semibold tracking-wide text-slate-50">GhostNet-AI</p>
            <p className="text-xs uppercase tracking-[0.28em] text-cyan-accent/80">Marine Sonar Intelligence</p>
          </div>
        </div>
        <div className="mt-4 rounded-2xl border border-cyan-accent/15 bg-cyan-accent/5 px-3 py-3">
          <p className="text-[11px] uppercase tracking-[0.28em] text-cyan-accent/75">Command posture</p>
          <p className="mt-2 text-sm text-slate-200">Live survey monitoring, geospatial review, and evidence reporting in one console.</p>
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-400">
            <div className="rounded-xl border border-abyss-600/70 bg-black/10 px-2 py-2">Realtime feed</div>
            <div className="rounded-xl border border-abyss-600/70 bg-black/10 px-2 py-2">GIS ready</div>
          </div>
        </div>
      </div>

      <ul className="flex flex-col gap-2">
        {NAV_ITEMS.map((item) => {
          const active = pathname?.startsWith(item.href);
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                className={clsx(
                  "group block rounded-2xl border px-3 py-3 transition",
                  active
                    ? "border-cyan-accent/35 bg-cyan-accent/10 text-slate-50 shadow-glow-cyan"
                    : "border-transparent bg-white/[0.02] text-slate-400 hover:border-abyss-600 hover:bg-white/[0.03] hover:text-slate-100"
                )}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-semibold">{item.label}</span>
                  <span
                    className={clsx(
                      "rounded-full border px-2 py-0.5 text-[10px] font-medium tracking-[0.24em]",
                      active ? "border-cyan-accent/40 text-cyan-accent" : "border-abyss-600/80 text-slate-500"
                    )}
                  >
                    {item.index}
                  </span>
                </div>
                <p className={clsx("mt-1.5 text-xs leading-5", active ? "text-cyan-50/80" : "text-slate-500 group-hover:text-slate-300")}>
                  {item.detail}
                </p>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
