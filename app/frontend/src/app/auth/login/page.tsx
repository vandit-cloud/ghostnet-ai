"use client";

import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { ApiError } from "@/api/client";
import { useLogin } from "@/features/auth/hooks";

const HeroWaterBackdrop = dynamic(
  () => import("@/components/three/HeroWaterBackdrop").then((m) => m.HeroWaterBackdrop),
  { ssr: false }
);

export default function LoginPage() {
  const router = useRouter();
  const login = useLogin();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await login.mutateAsync({ username, password });
      router.replace("/app/dashboard");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Unable to reach the server. Please try again.");
      }
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-paper px-4 py-10">
      <HeroWaterBackdrop />
      <div className="relative z-10 grid w-full max-w-6xl gap-6 lg:grid-cols-[minmax(0,1.15fr)_430px]">
        <section className="panel hidden p-8 lg:flex lg:flex-col lg:justify-between">
          <div>
            <p className="text-[11px] uppercase tracking-[0.34em] text-cyan-accent/85">GhostNet-AI</p>
            <h1 className="mt-4 max-w-3xl font-display text-5xl font-semibold leading-[1.02] text-slate-50">
              Marine sonar intelligence built for live anomaly review.
            </h1>
            <p className="mt-5 max-w-2xl text-base leading-8 text-slate-300">
              Monitor field surveys, track vessel movement, inspect detections in 2D and 3D, and turn analyst decisions into exportable evidence.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-2xl border border-abyss-600/70 bg-skytint/42 p-4">
              <p className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Realtime</p>
              <p className="mt-2 text-sm text-slate-200">Processing stages and survey progress stay visible during ingestion.</p>
            </div>
            <div className="rounded-2xl border border-abyss-600/70 bg-skytint/42 p-4">
              <p className="text-[11px] uppercase tracking-[0.24em] text-slate-500">GIS</p>
              <p className="mt-2 text-sm text-slate-200">Map detections against tracks, uncertainty rings, and vessel playback.</p>
            </div>
            <div className="rounded-2xl border border-abyss-600/70 bg-skytint/42 p-4">
              <p className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Reports</p>
              <p className="mt-2 text-sm text-slate-200">Export operational artifacts for downstream analysis and compliance review.</p>
            </div>
          </div>
        </section>

        <section className="panel relative mx-auto w-full max-w-md p-8">
          <div className="mb-8">
            <p className="text-[11px] uppercase tracking-[0.32em] text-cyan-accent/80">Secure Access</p>
            <h2 className="mt-3 font-display text-3xl font-semibold text-slate-50">Operator sign-in</h2>
            <p className="mt-2 text-sm leading-7 text-slate-400">Enter your credentials to open the GhostNet command console.</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="username" className="mb-2 block text-[11px] font-medium uppercase tracking-[0.26em] text-slate-500">
                Username or email
              </label>
              <input
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoComplete="username"
                className="w-full rounded-2xl border border-abyss-600/80 bg-skytint/42 px-3 py-3 text-sm text-slate-100 outline-none focus:border-cyan-accent focus:shadow-glow-cyan"
              />
            </div>
            <div>
              <label htmlFor="password" className="mb-2 block text-[11px] font-medium uppercase tracking-[0.26em] text-slate-500">
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                className="w-full rounded-2xl border border-abyss-600/80 bg-skytint/42 px-3 py-3 text-sm text-slate-100 outline-none focus:border-cyan-accent focus:shadow-glow-cyan"
              />
            </div>

            {error ? <p className="text-sm text-alert-critical">{error}</p> : null}

            <div className="relative pt-2">
              {login.isPending ? (
                <span
                  aria-hidden
                  className="pointer-events-none absolute inset-0 -m-1 animate-ping rounded-2xl border-2 border-cyan-accent/70"
                />
              ) : null}
              <button
                type="submit"
                disabled={login.isPending}
                className="relative w-full border border-imperial bg-imperial py-3 text-sm font-medium uppercase tracking-[0.22em] text-paper transition hover:bg-imperial-deep disabled:opacity-60"
              >
                {login.isPending ? "Signing In..." : "Enter Console"}
              </button>
            </div>
          </form>

          <div className="mt-6 rounded-2xl border border-abyss-600/70 bg-skytint/42 px-4 py-3 text-xs leading-6 text-slate-500">
            Self-service password recovery is not available in this build. Contact your system administrator if you need access recovery.
          </div>
        </section>
      </div>
    </div>
  );
}
