"use client";

import { useRouter } from "next/navigation";

import { useAuthStore } from "@/state/auth-store";

/* The console's top bar, in Atlantic: paper, with a single rule under it.
 *
 * It used to be the darkest thing on the page. Inverted, the title is the loud
 * element instead -- 40px of the display face in imperial -- and the chrome
 * around it recedes to mono labels and outlined pills. */
export function TopBar({ title, onMenuClick }: { title: string; onMenuClick?: () => void }) {
  const router = useRouter();
  const displayName = useAuthStore((s) => s.displayName);
  const clearSession = useAuthStore((s) => s.clearSession);

  return (
    <header className="flex items-center gap-4 border-b border-rule bg-paper px-5 py-4 sm:px-8">
      <button
        onClick={onMenuClick}
        aria-label="Open menu"
        className="-ml-1 border border-rule p-1.5 text-ink-2 transition hover:border-imperial hover:text-imperial md:hidden"
      >
        <svg width="22" height="22" viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
          <path d="M3 6h16" />
          <path d="M3 11h16" />
          <path d="M3 16h16" />
        </svg>
      </button>

      <div className="min-w-0">
        <p className="font-mono text-[10.5px] uppercase tracking-[0.12em] text-ink-3">
          Operational console
        </p>
        <h1 className="truncate font-display text-[34px] font-extrabold uppercase leading-[0.88] text-imperial sm:text-[40px]">
          {title}
        </h1>
      </div>

      <div className="ml-auto flex shrink-0 items-center gap-2">
        {/* The live pill is the mockup's one filled chrome element: a solid
            imperial block with a sky square, so "connected" is legible from
            across a room during a demo. */}
        <span className="hidden items-center border border-transparent bg-imperial px-3 py-[7px] font-mono text-[10.5px] uppercase tracking-[0.1em] text-paper lg:inline-flex">
          <i className="mr-[7px] inline-block h-1.5 w-1.5 bg-skytint" />
          Secure link
        </span>
        {displayName ? (
          <span className="hidden border border-rule px-3 py-[7px] font-mono text-[10.5px] uppercase tracking-[0.1em] text-ink-2 sm:inline-block">
            {displayName}
          </span>
        ) : null}
        <button
          onClick={() => {
            clearSession();
            router.push("/auth/login");
          }}
          className="border border-rule px-3 py-[7px] font-mono text-[10.5px] uppercase tracking-[0.1em] text-ink-2 transition hover:border-imperial hover:text-imperial"
        >
          Log out
        </button>
      </div>
    </header>
  );
}
