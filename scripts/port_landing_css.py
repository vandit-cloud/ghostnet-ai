# -*- coding: utf-8 -*-
"""Port the landing page's stylesheet from the demo into the Next.js app.

Companion to port_hero_scene.py, and there for the same reason: the demo's CSS
is a finished, hand-set piece of typography -- clamp() scales, a three-line
headline, a five-column footer -- and translating ~200 rules into Tailwind
utilities is an invitation to drift. It is copied instead.

Three things change:

1. SCOPE. Every rule is prefixed with `.landing`, because these are generic
   class names (`.nav`, `.card`, `.btn`, `.stat`) living in an app that also
   has a console. Unscoped, `.card` would reach into screens it was never
   designed for. The at-rules (@media, @keyframes) keep their own structure and
   only their inner selectors are prefixed.

2. WHAT GLOBALS.CSS ALREADY OWNS is dropped: the `:root` custom properties, the
   reset, `body`, and `.grain`. Keeping duplicates would mean two places to
   change the palette, and the copy that loaded last would win silently.

3. THE FONT STACKS point at the next/font CSS variables, so the landing uses
   the same self-hosted faces as the console instead of a second, render-
   blocking request to fonts.googleapis.com.

Run:  python scripts/port_landing_css.py
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = r"C:\Users\vandi\OneDrive\Desktop\ghostnet-demo\demo.src.html"
OUT = os.path.join(ROOT, "app", "frontend", "src", "features", "landing", "landing.css")

if not os.path.exists(SRC):
    sys.exit("demo.src.html not found at %s" % SRC)

html = io.open(SRC, encoding="utf-8").read()
css = html[html.index("<style>") + len("<style>"):html.index("</style>")]

# --- 2. drop what globals.css owns -------------------------------------------
DROP_PREFIXES = (":root", "*", "body", ".grain::after", ".grain")


def split_rules(text):
    """Yield (selector_or_atrule, block, is_at_rule) walking one brace level."""
    out, i, n = [], 0, len(text)
    while i < n:
        j = text.find("{", i)
        if j < 0:
            break
        sel = text[i:j].strip()
        depth, k = 1, j + 1
        while k < n and depth:
            if text[k] == "{":
                depth += 1
            elif text[k] == "}":
                depth -= 1
            k += 1
        out.append((sel, text[j + 1:k - 1], sel.startswith("@")))
        i = k
    return out


COMMENT = re.compile(r"/\*.*?\*/", re.S)


def split_comments(sel):
    """Separate a /* section heading */ from the selector that follows it.

    Left in place a comment still parses -- `.landing /*x*/ .nav` is only a
    descendant combinator -- but it reads as though the comment were part of the
    selector, which is the kind of thing someone later "tidies" into a bug by
    deleting the comment and the scope with it. Hoist them onto their own line.
    """
    notes = COMMENT.findall(sel)
    return notes, COMMENT.sub(" ", sel).strip()


def prefix(sel):
    """Scope one selector list under .landing."""
    parts = []
    for s in sel.split(","):
        s = s.strip()
        if not s:
            continue
        # A rule that targets the wrapper itself must not become `.landing .landing`.
        parts.append(s if s.startswith(".landing") else ".landing %s" % s)
    return ",\n".join(parts)


chunks = []
for sel, block, is_at in split_rules(css):
    notes, sel = split_comments(sel)
    chunks.extend(notes)
    if not sel:
        continue
    if is_at:
        if sel.startswith("@keyframes"):
            # Keyframe selectors are percentages, not elements. Leave them be.
            chunks.append("%s{%s}" % (sel, block))
        else:
            inner = "\n".join(
                "%s{%s}" % (prefix(split_comments(s2)[1]), b2)
                for s2, b2, _ in split_rules(block)
                if split_comments(s2)[1]
            )
            chunks.append("%s{\n%s\n}" % (sel, inner))
        continue
    head = sel.split()[0] if sel.split() else ""
    if any(sel.strip() == d or head == d for d in DROP_PREFIXES):
        continue
    chunks.append("%s{%s}" % (prefix(sel), block))

out = "\n".join(chunks)

# --- 3. font stacks -> the next/font variables --------------------------------
out = re.sub(r"font-family:var\(--display\)", "font-family:var(--font-display),var(--display)", out)
out = re.sub(r"font-family:var\(--ui\)", "font-family:var(--font-ui),var(--ui)", out)
out = re.sub(r"font-family:var\(--mono\)", "font-family:var(--font-mono),var(--mono)", out)

HEADER = """/* =============================================================================
 * GENERATED FILE -- DO NOT EDIT BY HAND.
 *
 * Ported from the standalone landing demo by `scripts/port_landing_css.py`.
 * Edit `ghostnet-demo/demo.src.html` and re-run the port; editing here means
 * the next port silently reverts it.
 *
 * Every rule is scoped under `.landing` so these generic names -- .nav, .card,
 * .btn, .stat -- cannot reach the console, which shares the app but not the
 * design. The palette variables, the reset and .grain live in globals.css and
 * are deliberately absent here.
 * ========================================================================== */
.landing {
  /* The display face is set at very large sizes with a tight line-height, and
     the demo relies on the three stacks being available on the element itself
     rather than inherited from <body>. */
  /* Height of the fixed nav. The hero copy and the instrument marquee are both
     positioned off it, so it has to travel with this stylesheet rather than
     sitting in globals.css where only the landing would ever read it. */
  --nav: 66px;
  --display: 'Monigue', 'Glinken', 'Big Shoulders Display', 'Oswald', sans-serif;
  --ui: 'Epoch', 'Jost', 'Archivo', system-ui, sans-serif;
  --mono: 'IBM Plex Mono', ui-monospace, monospace;
  font-family: var(--font-ui), var(--ui);
  color: var(--ink);
  background: var(--paper);
}

/* -----------------------------------------------------------------------------
 * ADDITIONS THE APP NEEDS AND THE DEMO DID NOT.
 * Kept here, above the copied rules, so the boundary between "ported" and
 * "written for the app" is a line in the file rather than a memory.
 * -------------------------------------------------------------------------- */

/* The demo shipped three.js and a 1.4 MB scene inline, so its first paint and
   its first rendered frame were the same moment. Next code-splits the scene and
   fetches it after mount, which leaves a window -- longer on a cold cache or a
   slow device -- where #gl is an empty transparent canvas over the pane's flat
   fill. This is that same water read as a static gradient: sky at the top, the
   waterline, then depth. It cross-fades out on the scene's first frame, and it
   is also what a reduced-motion visitor sees for good. */
.landing .hero-plate {
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  transition: opacity .6s ease;
  background:
    linear-gradient(180deg,
      #7fb4d8 0%,
      #a9d4ea 11%,
      #5e9dc4 12.5%,
      #12547e 26%,
      #0f4b70 52%,
      #0a3552 78%,
      #072639 100%);
}

"""

os.makedirs(os.path.dirname(OUT), exist_ok=True)
io.open(OUT, "w", encoding="utf-8", newline="\n").write(HEADER + out + "\n")
print("wrote %s  (%d rules)" % (OUT, len(chunks)))
