"use client";

/** Client-only preference keys (Settings page). Each one is read directly by
 * the component it affects so the toggle is a real, wired control rather
 * than a decorative one. */
export const MAP_CLUSTER_DISABLED_KEY = "ghostnet_map_cluster_disabled";

export function getBoolSetting(key: string): boolean {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem(key) === "true";
}

export function setBoolSetting(key: string, value: boolean): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(key, String(value));
}
