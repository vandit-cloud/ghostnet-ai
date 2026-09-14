"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import clsx from "clsx";

import { NAV_ITEMS } from "@/utils/nav";

/** The phone drawer. Deliberately the same blue rail as the desktop sidebar
 *  rather than a separate design, so the console reads as one thing at both
 *  sizes. */
export function MobileNav({ open, onClose }: { open: boolean; onClose: () => void }) {
  const pathname = usePathname();

  useEffect(() => {
    onClose();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex md:hidden" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-imperial/50" onClick={onClose} />
      <nav className="relative flex w-[264px] max-w-[84vw] flex-col overflow-y-auto bg-atlantic">
        <div className="flex items-start justify-between gap-3 px-6 pb-6 pt-7">
          <div>
            <p className="font-display text-[27px] font-black uppercase leading-none text-paper">
              Ghost
              <i className="not-italic text-transparent [-webkit-text-stroke:1.2px_theme(colors.skytint.DEFAULT)]">Net</i>
              -AI
            </p>
            <p className="mt-3 font-mono text-[10px] uppercase tracking-[0.18em] text-paper/40">
              Marine sonar intelligence
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close menu"
            className="border border-skytint/22 px-2 py-1 font-mono text-[11px] text-paper/74 transition hover:border-skytint hover:text-paper"
          >
            ESC
          </button>
        </div>

        <ul className="flex flex-col">
          {NAV_ITEMS.map((item) => {
            const active = pathname?.startsWith(item.href);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={clsx(
                    "block border-l-[3px] px-6 py-3 transition",
                    active
                      ? "border-skytint bg-imperial/55 text-paper"
                      : "border-transparent text-paper/74 hover:bg-imperial/25 hover:text-paper"
                  )}
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className={clsx("text-sm", active ? "font-medium" : "font-normal")}>
                      {item.label}
                    </span>
                    <span
                      className={clsx("font-mono text-[11px]", active ? "text-skytint" : "text-paper/40")}
                    >
                      {item.index}
                    </span>
                  </div>
                  <p
                    className={clsx(
                      "mt-1 text-xs leading-5",
                      active ? "text-paper/74" : "text-paper/40"
                    )}
                  >
                    {item.detail}
                  </p>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </div>
  );
}
