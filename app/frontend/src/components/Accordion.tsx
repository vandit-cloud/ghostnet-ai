"use client";

import { useState, type ReactNode } from "react";
import clsx from "clsx";

import { Panel } from "@/components/Panel";

export function ExpandableSection({
  title,
  defaultOpen = false,
  children,
}: {
  title: string;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <Panel className="!p-0">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-semibold uppercase tracking-wide text-slate-300 hover:bg-abyss-700/30"
      >
        {title}
        <svg
          width="14"
          height="14"
          viewBox="0 0 14 14"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          className={clsx("shrink-0 text-slate-500 transition-transform", open && "rotate-180")}
        >
          <path d="M2 5l5 5 5-5" />
        </svg>
      </button>
      {open && <div className="space-y-1 border-t border-abyss-700 px-4 py-3">{children}</div>}
    </Panel>
  );
}
