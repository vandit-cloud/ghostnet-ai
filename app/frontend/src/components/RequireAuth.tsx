"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { useAuthStore } from "@/state/auth-store";

export function RequireAuth({ children }: { children: ReactNode }) {
  const router = useRouter();
  const token = useAuthStore((s) => s.token);
  const hydrate = useAuthStore((s) => s.hydrate);
  const [ready, setReady] = useState(false);

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
    return <div className="flex min-h-screen items-center justify-center bg-abyss-950 text-slate-400">Loading…</div>;
  }

  return <>{children}</>;
}
