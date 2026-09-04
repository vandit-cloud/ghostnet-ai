"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import clsx from "clsx";

import { NAV_ITEMS } from "@/utils/nav";

export function MobileNav({ open, onClose }: { open: boolean; onClose: () => void }) {
  const pathname = usePathname();

  useEffect(() => {
    onClose();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex md:hidden" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <nav className="relative flex w-72 max-w-[84vw] flex-col overflow-y-auto border-r border-abyss-600 bg-trench-950 px-4 py-5 shadow-xl">
        <div className="panel mb-5 flex items-start justify-between gap-3 px-4 py-4">
          <div>
            <p className="font-display text-lg font-semibold tracking-wide text-slate-50">GhostNet-AI</p>
            <p className="text-xs uppercase tracking-[0.28em] text-cyan-accent/80">Marine Sonar Intelligence</p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close menu"
            className="rounded-xl border border-abyss-600/80 bg-abyss-900/80 p-2 text-slate-400 hover:border-cyan-accent/30 hover:text-slate-100"
          >
            x
          </button>
        </div>
        <ul className="flex flex-col gap-2">
          {NAV_ITEMS.map((item) => {
            const active = pathname?.startsWith(item.href);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={clsx(
                    "block rounded-2xl border px-3 py-3 transition",
                    active
                      ? "border-cyan-accent/35 bg-cyan-accent/10 text-slate-50 shadow-glow-cyan"
                      : "border-transparent bg-white/[0.02] text-slate-400 hover:border-abyss-600 hover:bg-white/[0.03] hover:text-slate-200"
                  )}
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-semibold">{item.label}</span>
                    <span className={clsx("text-[10px] tracking-[0.24em]", active ? "text-cyan-accent" : "text-slate-500")}>
                      {item.index}
                    </span>
                  </div>
                  <p className={clsx("mt-1.5 text-xs leading-5", active ? "text-cyan-50/80" : "text-slate-500")}>{item.detail}</p>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </div>
  );
}
