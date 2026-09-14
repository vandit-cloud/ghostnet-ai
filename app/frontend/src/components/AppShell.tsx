"use client";

import { useState, type ReactNode } from "react";

import { MobileNav } from "@/components/MobileNav";
import { RequireAuth } from "@/components/RequireAuth";
import { Sidebar } from "@/components/Sidebar";
import { TopBar } from "@/components/TopBar";

/* The console frame.
 *
 * Atlantic inverts what this used to be. The page was an abyss-dark canvas with
 * cyan bloom in the corners and a sonar grid behind the scroll area; it is now
 * paper, with the blue confined to the left rail and to the panels that
 * genuinely show water -- sonar, the map, the 3D replay.
 *
 * The 14px imperial band along the top is the mockup's device for separating
 * the console from whatever is above it. It is the same band the landing page
 * uses over its blue sections, and it is the only ornament in the frame. */
export function AppShell({ title, children }: { title: string; children: ReactNode }) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  return (
    <RequireAuth>
      <div className="flex h-screen flex-col overflow-hidden bg-paper text-ink">
        <div className="h-[14px] shrink-0 bg-imperial" />
        <div className="flex min-h-0 flex-1">
          <Sidebar />
          <MobileNav open={mobileNavOpen} onClose={() => setMobileNavOpen(false)} />
          <div className="relative flex min-w-0 flex-1 flex-col">
            <TopBar title={title} onMenuClick={() => setMobileNavOpen(true)} />
            <main className="console-canvas grain grain-lite flex-1 overflow-y-auto p-5 sm:p-6 lg:p-8">
              <div className="relative z-[9] mx-auto w-full max-w-[1600px]">{children}</div>
            </main>
          </div>
        </div>
      </div>
    </RequireAuth>
  );
}
