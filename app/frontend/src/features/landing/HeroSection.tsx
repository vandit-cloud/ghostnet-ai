"use client";

import { useEffect, useRef, useState } from "react";

import { useReducedMotion } from "@/hooks/useReducedMotion";

/* =============================================================================
 * The scroll-driven hero.
 *
 * The scene itself lives in ./hero/scene.ts, ported verbatim from the demo. It
 * reads this markup BY ID rather than through props -- #gl, #heroCopy, #stats,
 * #instruments and the readouts -- which is how it worked in the demo and is
 * why the port could stay byte-faithful. The contract between the two halves is
 * therefore the set of ids below: rename one here and the scene stops driving
 * it silently, so they are all listed in the scene's header comment too.
 *
 * The scroll does two things at once. The camera dives from +6.75 m through the
 * waterline to -16 m, and the towfish deploys. The dive deliberately LEADS
 * (0.14-0.52 against 0.18-0.62) so you are already under before the winch
 * starts and can watch the fish go down rather than arriving after it has.
 * ========================================================================== */

export function HeroSection() {
  const reducedMotion = useReducedMotion();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (reducedMotion) return;
    let dispose: (() => void) | undefined;
    let cancelled = false;

    // three plus the scene is ~600 KB and nothing above the fold needs it to
    // paint, so it is imported at mount rather than bundled into first load.
    import("./hero/scene")
      .then(({ initHero }) => {
        if (cancelled) return;
        dispose = initHero();
        setReady(true);
      })
      .catch((err) => {
        // A hero that fails to start is a degraded page, not a broken one: the
        // copy, the CTAs and every section below it still work. Say so in the
        // console and leave the static plate up.
        console.error("[GhostNet] hero scene failed to start", err);
      });

    return () => {
      cancelled = true;
      dispose?.();
      /* Put the static plate back. Without this, flipping reduced-motion after
         the scene has painted leaves `ready` true while the canvas has already
         lost its context: the hero becomes a near-white ground with the
         paper-coloured headline and lede on top of it, i.e. invisible. */
      setReady(false);
    };
  }, [reducedMotion]);

  /* With the scene off, the 360vh scroll track is 260vh of nothing: the pane is
     sticky and there is no animation for the extra height to drive. Collapse it
     so the page reads as an ordinary one. */
  const trackStyle = reducedMotion ? { height: "100vh" } : undefined;

  return (
    <section className="hero-track" id="hero" style={trackStyle}>
      <div className="hero-pane grain">
        <canvas id="gl" />
        {/* Until the scene has painted a frame, the canvas is a transparent
            hole over the pane's flat #0a2a44. This is the same water read as a
            gradient, so the first paint is a sea rather than a blank slab. */}
        <div
          aria-hidden="true"
          className="hero-plate"
          style={{ opacity: ready ? 0 : 1 }}
        />
        <div className="scrim" />

        <div className="hero-copy" id="heroCopy">
          <div className="eyebrow">
            <u /> Side-scan sonar · ghost gear detection <u />
          </div>
          <h1 className="hero-t">
            Find the nets
            <br />
            the ocean <em>kept</em>
            <br />
            <span className="out">hidden.</span>
          </h1>
        </div>

        <div className="hero-foot" id="heroFoot">
          <p className="hero-p">
            GhostNet-AI reads side-scan waterfall imagery and flags abandoned fishing gear as{" "}
            <b>polygons, not pins</b> — each carrying a calibrated confidence, an honest position
            error, and a <b>review_only</b> flag until a human signs it off.
          </p>
          <div className="cta">
            <a className="btn btn-primary" href="/app/surveys/new">
              <span>Run a survey</span>
            </a>
            <a className="btn btn-sky" href="#detection">
              <span>See a detection</span>
            </a>
            <a className="btn btn-line" href="#method">
              <span>How it decides →</span>
            </a>
          </div>
        </div>

        <div className="cue" id="cue">
          <u /> Scroll to dive
        </div>

        <div id="instruments">
          <div className="marq">
            GN-0412 · ping <em id="ping">18 402</em> &nbsp;·&nbsp; ghost_net 0.91 &nbsp;·&nbsp; ± 31 m
            &nbsp;·&nbsp; review_only
          </div>
          <div className="rdo">
            depth <em id="rdoDepth">0.0 m</em>
            <br />
            layback <em id="rdoLay">0.0 m</em>
            <br />
            altitude <em id="rdoAlt">— m</em>
            <br />
            speed <em>2.0 m/s</em>
          </div>
          <div className="hud">
            <div className="swap" id="swap">
              <b className="on">
                Under
                <br />
                way
              </b>
              <b>
                Paying
                <br />
                out
              </b>
              <b>
                Ensoni-
                <br />
                fying
              </b>
              <b>Contact</b>
            </div>
            {/* The scene rewrites this with innerHTML as the stage changes. */}
            <p id="hudSub">
              28 m survey vessel
              <br />
              towfish stowed in the A-frame
            </p>
          </div>
        </div>

        <div className="stats" id="stats">
          <div className="stat">
            <b>0.91</b>
            <span>calibrated · not raw</span>
          </div>
          <div className="stat">
            <b>
              ±24<s> m</s>
            </b>
            <span>median position error</span>
          </div>
          <div className="stat">
            <b>
              7.0<s> %</s>
            </b>
            <span>median area claimed</span>
          </div>
          <div className="stat">
            <b>425</b>
            <span>polygons in D2</span>
          </div>
        </div>
      </div>
    </section>
  );
}
