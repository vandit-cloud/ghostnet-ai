"use client";

import type { ReactNode } from "react";

export function Modal({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-imperial/50 p-4" role="dialog" aria-modal="true">
      <div className="w-full max-w-lg border border-rule bg-paper p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-display text-[27px] font-extrabold uppercase leading-none text-imperial">{title}</h2>
          <button
            onClick={onClose}
            aria-label="Close"
            className="border border-rule px-2 py-1 font-mono text-[11px] text-ink-2 transition hover:border-imperial hover:text-imperial"
          >
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
