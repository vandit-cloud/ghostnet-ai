"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { useAuthStore } from "@/state/auth-store";

export function RequireAuth({ children }: { children: ReactNode }) {
  const router = useRouter();
  const token = useAuthStore((s) => s.token);
  const hydrate = useAuthStore((s) => s.hydrate);
  // Every console page mounts its own AppShell, so this component remounts on
  // each navigation. Starting at `false` blanked the screen to "Loading…" on
  // every sidebar click, even though the session was already in memory. So
  // start ready when the store already holds a token -- true on any in-app
  // navigation. A hard load still begins false on server and client alike,
  // which keeps hydration consistent.
  const [ready, setReady] = useState(() => useAuthStore.getState().token !== null);

  useEffect(() => {
    hydrate();
    setReady(true);
  }, [hydrate]);

  useEffect(() => {
    if (ready && !token) {
      router.replace("/auth/login");
    }
  }, [ready, token, router]);

  if (!ready || !token) {
    // Paper, not abyss: the console is light, and a dark full-screen frame
    // between two light pages reads as a crash on a hard load.
    return <div className="flex min-h-screen items-center justify-center bg-paper text-slate-400">Loading…</div>;
  }

  return <>{children}</>;
}
