"use client";

import { useEffect, useState } from "react";

import { CONTRACT_VERSION } from "@/utils/contract";

/* The nav sits transparent over the hero and turns to solid paper once the
 * hero has scrolled past. It cannot be a pure CSS scroll trigger because the
 * threshold is the HERO'S bottom edge, not a fixed scroll distance -- the hero
 * track is 360vh on a desktop and 100vh under reduced motion. */
export function LandingNav() {
  const [solid, setSolid] = useState(false);

  useEffect(() => {
    const hero = document.getElementById("hero");
    if (!hero) return;
    const update = () => setSolid(hero.getBoundingClientRect().bottom <= 80);
    window.addEventListener("scroll", update, { passive: true });
    update();
    return () => window.removeEventListener("scroll", update);
  }, []);

  return (
    <nav className={solid ? "nav solid" : "nav"} id="nav">
      <div className="logo">
        Ghost<i>Net</i>-AI
      </div>
      <a className="sp" href="#detection">
        Detections
      </a>
      <a href="#outputs">Outputs</a>
      <a href="#method">Method</a>
      <a href="#evidence">Evidence</a>
      <a href="#spec">Spec</a>
      <span className="tag">SIH26057 · contract v{CONTRACT_VERSION}</span>
      <a
        className="btn btn-primary"
        href="/app/dashboard"
        style={{ padding: "11px 20px 9px", fontSize: 15 }}
      >
        <span>Open console</span>
      </a>
    </nav>
  );
}
