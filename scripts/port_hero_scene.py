# -*- coding: utf-8 -*-
"""Port the landing hero from the standalone demo into the Next.js app.

WHY THIS IS A SCRIPT AND NOT A REWRITE
--------------------------------------
The hero is ~600 lines of hand-tuned three.js: a water shader lifted from the
sea lab, rig geometry, deploy timing, damped hull dynamics and a god-ray origin
that each took a measurement to get right and each have a comment saying what
went wrong before. Retyping that into React is how the tuning gets lost -- a
single transposed constant is invisible in review and obvious on screen.

So the scene is moved VERBATIM. This script reads the built demo, lifts the
module script out of it and applies a small, closed set of mechanical edits, so
the port can be re-run whenever the demo is re-tuned instead of drifting.

WHAT IT CHANGES, AND NOTHING ELSE
---------------------------------
1. Import specifiers: the demo resolves `three/addons/` through an importmap to
   a CDN. The app resolves `three` from npm, where the same files live under
   `three/examples/jsm/`.
2. Asset URLs: the demo inlines the GLBs as base64 because a file:// page
   cannot fetch its siblings. Next serves /public, so they become real URLs --
   and the Draco decoder is self-hosted rather than fetched from jsdelivr.
3. Lifecycle: the demo is a top-level script that runs once and never stops.
   The app mounts and unmounts it (twice in a row under React strict mode in
   dev), so the body is wrapped in initHero() and every listener, animation
   frame and GPU resource it takes is handed back in a dispose function.

Everything else -- every constant, every comment, the whole shader -- is copied
through untouched.

Run:  python scripts/port_hero_scene.py
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEMO = r"C:\Users\vandi\OneDrive\Desktop\ghostnet-demo\demo.html"
OUT = os.path.join(ROOT, "app", "frontend", "src", "features", "landing", "hero", "scene.ts")

if not os.path.exists(DEMO):
    sys.exit("demo.html not found at %s -- build it with build_demo.py first" % DEMO)

html = io.open(DEMO, encoding="utf-8").read()

# ---- lift the module script -------------------------------------------------
start = html.index('<script type="module">') + len('<script type="module">')
end = html.index("</script>", start)
body = html[start:end]

# ---- 1. import specifiers ---------------------------------------------------
body = body.replace("from 'three/addons/", "from 'three/examples/jsm/")

# ---- 2. asset URLs ----------------------------------------------------------
# The demo reads two globals set by an earlier inline script holding ~750 KB of
# base64. Under Next these are ordinary static files.
body = body.replace("window.VESSEL_GLB", "VESSEL_URL")
body = body.replace("window.TOWFISH_GLB", "TOWFISH_URL")
# Pin the decoder to the copy in /public, which is the decoder that ships with
# the exact three version in package.json. The CDN path in the demo is pinned to
# 0.161 and the app is on a later three; a decoder/loader mismatch fails at
# parse time with a message that points nowhere useful.
body = re.sub(
    r'draco\.setDecoderPath\("[^"]*"\);',
    'draco.setDecoderPath("/draco/gltf/");',
    body,
)

# ---- 3. lifecycle -----------------------------------------------------------
# A GLB is fetched and Draco-decoded asynchronously. If the component unmounts
# while that is in flight -- a route change, or the reduced-motion toggle -- the
# callback still fires and adds a fresh scene graph into one that has already
# been traversed and disposed, along with its textures and materials. Nothing
# throws; the resources are simply never freed. Guard both loads with the same
# `disposed` flag the dispose function sets.
for _var, _grp, _mat in (("VESSEL_URL", "vesselGroup", "MAT.vessel"),
                         ("TOWFISH_URL", "fishScale", "MAT.towfish")):
    _old = "gltf.load(%s,(r)=>{%s.add(r.scene);collect(r.scene,%s,%s);});" % (
        _var, _grp, "false" if _var == "VESSEL_URL" else "true", _mat)
    assert _old in body, "GLTF load call shape changed for %s" % _var
    _new = (
        "gltf.load(%s,(r)=>{ if (disposed) { "
        "r.scene.traverse(o=>{o.geometry?.dispose?.(); const m=o.material; "
        "Array.isArray(m)?m.forEach(x=>x?.dispose?.()):m?.dispose?.();}); return; } "
        "%s.add(r.scene);collect(r.scene,%s,%s);});"
    ) % (_var, _grp, "false" if _var == "VESSEL_URL" else "true", _mat)
    body = body.replace(_old, _new)

# The render loop re-arms itself; capture the handle so it can be cancelled.
assert body.count("requestAnimationFrame(frame);") == 1, "render loop shape changed"
body = body.replace("requestAnimationFrame(frame);", "rafId = requestAnimationFrame(frame);")

# Window listeners are implicit on the demo's global scope. Make them explicit
# so the same references can be removed again.
assert body.count('addEventListener("resize",resize); resize();') == 1, "resize hookup changed"
body = body.replace(
    'addEventListener("resize",resize); resize();',
    'window.addEventListener("resize", resize); resize();',
)

# Split the imports off the top: an ES import cannot live inside a function.
imports = []
rest = []
for line in body.split("\n"):
    (imports if line.startswith("import ") else rest).append(line)
body = "\n".join(rest)

HEADER = '''/* eslint-disable */
// @ts-nocheck
/* =============================================================================
 * GENERATED FILE -- DO NOT EDIT BY HAND.
 *
 * Ported verbatim from the standalone landing demo by
 * `scripts/port_hero_scene.py`. Tune the hero in
 * `ghostnet-demo/demo.src.html`, rebuild it with `build_demo.py`, then re-run
 * the port. Editing this file directly means the next port silently reverts it.
 *
 * ts-nocheck is deliberate and is the price of a verbatim port: the source is
 * plain JavaScript written against the DOM and three's untyped uniform objects,
 * and annotating it would mean rewriting it, which is the one thing this file
 * exists to avoid. The wrapper below is typed, and it is the only surface the
 * rest of the app touches.
 * ========================================================================== */
%s

const VESSEL_URL = "/models/vessel.glb";
const TOWFISH_URL = "/models/towfish.glb";

/**
 * Build the hero scene against the elements the landing page has already
 * rendered, and start it. Returns a dispose function; call it on unmount.
 *
 * The scene reads the DOM by id, exactly as it does in the demo -- #gl, #hero,
 * #heroCopy and the instrument readouts. HeroCanvas renders those same ids, so
 * the two halves stay in step without a prop surface between them.
 */
export function initHero(): () => void {
  if (typeof window === "undefined") return () => {};
  if (!document.getElementById("gl") || !document.getElementById("hero")) {
    // Nothing to attach to. Returning a no-op is the right failure here: a
    // landing page without its background is degraded, not broken.
    return () => {};
  }

  let rafId = 0;
  let disposed = false;
''' % "\n".join(imports)

FOOTER = '''
  return () => {
    if (disposed) return;
    disposed = true;
    cancelAnimationFrame(rafId);
    window.removeEventListener("resize", resize);
    delete (window as any).__heroProgress;
    // Order matters: drop the scene graph's GPU handles before the context
    // that owns them. A WebGL context is not garbage collected on its own, and
    // React strict mode mounts this twice in development -- leak it and the
    // second mount runs on a browser that has already hit its context limit.
    renderer.setAnimationLoop(null);
    for (const s of [scene, waterScene]) {
      s.traverse((o: any) => {
        o.geometry?.dispose?.();
        const m = o.material;
        if (Array.isArray(m)) m.forEach((x: any) => x?.dispose?.());
        else m?.dispose?.();
      });
    }
    ENV_AIR?.dispose?.();
    ENV_WATER?.dispose?.();
    pmrem?.dispose?.();
    // DRACOLoader spins up WASM decoder workers -- two per mount, since both
    // GLBs are Draco-compressed -- and they outlive the page unless told to
    // stop. Measured before this line existed: {made: 2, killed: 0}.
    draco.dispose();
    renderer.dispose();
    renderer.forceContextLoss?.();
  };
}
'''

# Indent the ported body by one level so it reads as the function it now is.
indented = "\n".join(("  " + l if l.strip() else l) for l in body.split("\n"))

os.makedirs(os.path.dirname(OUT), exist_ok=True)
io.open(OUT, "w", encoding="utf-8", newline="\n").write(HEADER + indented + FOOTER)
print("wrote %s  (%d lines)" % (OUT, (HEADER + indented + FOOTER).count("\n") + 1))
