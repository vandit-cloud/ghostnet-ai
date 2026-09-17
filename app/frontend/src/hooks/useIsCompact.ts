"use client";

import { useEffect, useState } from "react";

/** True on phone-width viewports and on coarse-pointer devices.
 *
 * Both conditions matter and they are not the same test: a narrow desktop
 * window can take the 3D scene fine, while a wide tablet cannot take the
 * scroll choreography because touch-scroll momentum makes a scrubbed timeline
 * feel broken. */
export function useIsCompact(breakpoint = 820): boolean {
  const [compact, setCompact] = useState(false);

  useEffect(() => {
    const query = window.matchMedia(`(max-width: ${breakpoint}px), (pointer: coarse)`);
    setCompact(query.matches);
    const handler = (e: MediaQueryListEvent) => setCompact(e.matches);
    query.addEventListener("change", handler);
    return () => query.removeEventListener("change", handler);
  }, [breakpoint]);

  return compact;
}
