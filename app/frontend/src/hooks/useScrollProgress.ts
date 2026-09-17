"use client";

import { useEffect, useRef, useState } from "react";

/** Scroll progress of a container, 0 at the moment its top reaches the top of
 * the viewport and 1 when its bottom has passed the bottom.
 *
 * Deliberately NOT drei's ScrollControls: that takes ownership of scrolling and
 * puts the DOM inside the Canvas, which is fine for a pure 3D showreel but
 * fights a real landing page with headings, links and native scrollbars. This
 * keeps the page a normal document and only *reads* the scroll position, so
 * keyboard scrolling, anchor links and browser find-in-page all still work.
 *
 * Reads are throttled to the rAF that the r3f loop is already running, so this
 * adds no extra layout passes beyond one getBoundingClientRect per frame. */
export function useScrollProgress(ref: React.RefObject<HTMLElement>) {
  const progress = useRef(0);
  const [settled, setSettled] = useState(0);

  useEffect(() => {
    let frame = 0;
    const read = () => {
      const el = ref.current;
      if (el) {
        const rect = el.getBoundingClientRect();
        const scrollable = rect.height - window.innerHeight;
        const raw = scrollable > 0 ? -rect.top / scrollable : 0;
        const next = Math.min(1, Math.max(0, raw));
        progress.current = next;
        // React state is for DOM consumers (the stage caption) only, and it is
        // quantised to 1% so we re-render ~100 times over the whole scroll
        // instead of once per frame. The 3D scene never reads this - it reads
        // `progress.current` inside useFrame, outside React entirely.
        setSettled((prev) => (Math.abs(prev - next) >= 0.01 ? next : prev));
      }
      frame = window.requestAnimationFrame(read);
    };
    frame = window.requestAnimationFrame(read);
    return () => window.cancelAnimationFrame(frame);
  }, [ref]);

  return { progress, settled };
}
