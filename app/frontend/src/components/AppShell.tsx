"use client";

import { useState, type ReactNode } from "react";

import { MobileNav } from "@/components/MobileNav";
import { RequireAuth } from "@/components/RequireAuth";
import { Sidebar } from "@/components/Sidebar";
import { TopBar } from "@/components/TopBar";

export function AppShell({ title, children }: { title: string; children: ReactNode }) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  return (
    <RequireAuth>
      <div className="relative flex h-screen overflow-hidden bg-abyss-950 text-slate-100">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.12),transparent_22%),radial-gradient(circle_at_top_right,rgba(14,165,233,0.1),transparent_20%)]" />
        <Sidebar />
        <MobileNav open={mobileNavOpen} onClose={() => setMobileNavOpen(false)} />
        <div className="relative flex min-w-0 flex-1 flex-col">
          <TopBar title={title} onMenuClick={() => setMobileNavOpen(true)} />
          <main className="sonar-grid-bg flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
            <div className="mx-auto w-full max-w-[1600px]">{children}</div>
          </main>
        </div>
      </div>
    </RequireAuth>
  );
}
