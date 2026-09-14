"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";

import { NAV_ITEMS } from "@/utils/nav";

/* The console's left rail, in Atlantic.
 *
 * This is the one surface in the console that stays blue. The main area is
 * paper, so the rail is what tells you at a glance which half of the screen is
 * chrome and which is content -- and it is the only place the wordmark appears
 * in its on-blue form, with the sky stroke through "Net".
 *
 * The active item is marked THREE ways: a sky bar on the leading edge, an
 * imperial fill, and paper text. Colour alone would not survive the rail being
 * printed, photographed for a deck, or read by anyone with low blue
 * discrimination -- and on a blue ground, blue-on-blue is exactly the contrast
 * pair that fails first. */
export function Sidebar() {
  const pathname = usePathname();

  return (
    <nav className="hidden w-[264px] shrink-0 flex-col overflow-y-auto bg-atlantic md:flex">
      <div className="px-6 pb-6 pt-7">
        <p className="font-display text-[27px] font-black uppercase leading-none text-paper">
          Ghost
          <i className="not-italic text-transparent [-webkit-text-stroke:1.2px_theme(colors.skytint.DEFAULT)]">Net</i>
          -AI
        </p>
        <p className="mt-3 font-mono text-[10px] uppercase tracking-[0.18em] text-paper/40">
          Marine sonar intelligence
        </p>
      </div>

      <p className="px-6 pb-2 pt-3 font-mono text-[10px] uppercase tracking-[0.18em] text-paper/40">
        Operations
      </p>

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
                    className={clsx(
                      "font-mono text-[11px]",
                      active ? "text-skytint" : "text-paper/40"
                    )}
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

      <div className="mt-auto px-6 pb-6 pt-8">
        <div className="border-t border-skytint/22 pt-3 font-mono text-[10.5px] leading-[1.9] tracking-[0.06em] text-paper/40">
          <p>SIH26057 · contract v1.2.0</p>
          <p>All detections review_only</p>
        </div>
      </div>
    </nav>
  );
}
