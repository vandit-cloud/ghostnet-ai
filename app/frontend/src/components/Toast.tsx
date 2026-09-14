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

/* Toasts are one of the surfaces the retheme could not be screenshotted
 * against, because nothing in a static fixture raises one. They were still
 * dressed for the dark console -- `bg-abyss-800` now resolves to a near-paper
 * grey, so an error toast was crimson text on off-white with a soft drop
 * shadow. On a light canvas a transient message has to be the DARKEST thing on
 * screen to be noticed at all, so each tone is a solid fill. */
const TONE_STYLES: Record<ItemTone, string> = {
  info: "border-imperial bg-imperial text-paper",
  error: "border-alert-critical bg-alert-critical text-paper",
  success: "border-emerald-500 bg-emerald-500 text-paper",
};

type ItemTone = ToastItem["tone"];

export function ToastViewport() {
  const toasts = useToastStore((s) => s.toasts);
  const dismiss = useToastStore((s) => s.dismiss);

  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`pointer-events-auto min-w-[240px] cursor-pointer border px-4 py-2.5 text-sm ${TONE_STYLES[toast.tone]}`}
          onClick={() => dismiss(toast.id)}
          role="status"
        >
          {toast.message}
        </div>
      ))}
    </div>
  );
}
