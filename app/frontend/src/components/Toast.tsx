"use client";

import { create } from "zustand";

interface ToastItem {
  id: number;
  message: string;
  tone: "info" | "error" | "success";
}

interface ToastState {
  toasts: ToastItem[];
  push: (message: string, tone?: ToastItem["tone"]) => void;
  dismiss: (id: number) => void;
}

let nextId = 1;

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  push: (message, tone = "info") => {
    const id = nextId++;
    set((s) => ({ toasts: [...s.toasts, { id, message, tone }] }));
    setTimeout(() => {
      set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
    }, 4000);
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));

const TONE_STYLES: Record<ToastItem["tone"], string> = {
  info: "border-cyan-accent/40 bg-abyss-800 text-slate-100",
  error: "border-alert-critical/40 bg-abyss-800 text-alert-critical",
  success: "border-emerald-500/40 bg-abyss-800 text-emerald-300",
};

export function ToastViewport() {
  const toasts = useToastStore((s) => s.toasts);
  const dismiss = useToastStore((s) => s.dismiss);

  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`pointer-events-auto min-w-[240px] rounded-md border px-4 py-2 text-sm shadow-lg ${TONE_STYLES[toast.tone]}`}
          onClick={() => dismiss(toast.id)}
          role="status"
        >
          {toast.message}
        </div>
      ))}
    </div>
  );
}
