"use client";

import { useEffect, useState } from "react";

export const REDUCED_MOTION_OVERRIDE_KEY = "ghostnet_reduced_motion_override";

/** OS-level `prefers-reduced-motion` OR'd with the manual override set from
 * Settings > Application, so the in-app toggle actually controls the 3D/2D
 * animation systems rather than being decorative. */
export function useReducedMotion(): boolean {
  const [systemReduced, setSystemReduced] = useState(false);
  const [manualOverride, setManualOverride] = useState(false);

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    setSystemReduced(query.matches);
    const handler = (e: MediaQueryListEvent) => setSystemReduced(e.matches);
    query.addEventListener("change", handler);

    setManualOverride(window.localStorage.getItem(REDUCED_MOTION_OVERRIDE_KEY) === "true");
    const onStorage = (e: StorageEvent) => {
      if (e.key === REDUCED_MOTION_OVERRIDE_KEY) setManualOverride(e.newValue === "true");
    };
    window.addEventListener("storage", onStorage);

    return () => {
      query.removeEventListener("change", handler);
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  return systemReduced || manualOverride;
}
