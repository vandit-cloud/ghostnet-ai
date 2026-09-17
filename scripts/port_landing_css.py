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
        # A STATEMENT at-rule (@import, @charset) ends at its semicolon and has
        # no block. Left alone it would be absorbed into the NEXT rule's
        # selector, that rule would be treated as an at-rule, and its
        # declarations would be dropped without a word.
        if sel.startswith("@") and ";" in sel:
            i += sel.rindex(";") + 1
            continue
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


def split_top_level(sel):
    """Split a selector list on commas that are NOT inside () or [].

    A bare `sel.split(",")` breaks the moment the demo grows a `:not(.btn, .tag)`
    or an `[data-x="a,b"]`: it would emit two malformed selectors and the rule
    would silently stop applying. Nothing in the demo needs this today; it is
    here so the next edit to the demo cannot quietly unstyle the page.
    """
    out, depth, buf = [], 0, ""
    for ch in sel:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(buf)
            buf = ""
        else:
            buf += ch
    out.append(buf)
    return out


def is_dropped(sel):
    """True if globals.css already owns this rule.

    Matches the whole first COMPOUND selector rather than a prefix: keyed on a
    prefix, `.grain` would also swallow `.grain .child`.
    """
    head = sel.split()[0] if sel.split() else ""
    return any(sel.strip() == d or head == d for d in DROP_PREFIXES)


def prefix(sel):
    """Scope one selector list under .landing."""
    parts = []
    for s in split_top_level(sel):
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
                # The drop list has to apply inside @media too; a `body{}` or
                # `:root{}` nested in a breakpoint was not being checked at all
                # and would have become `.landing body{}`.
                if split_comments(s2)[1] and not is_dropped(split_comments(s2)[1])
            )
            chunks.append("%s{\n%s\n}" % (sel, inner))
        continue
    if is_dropped(sel):
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
  /* The demo inherits `line-height: normal`; Tailwind's preflight sets
     `html { line-height: 1.5 }`, so every element without an explicit value
     inflates. Individually invisible, collectively not -- the nav grew 4.5px,
     the tag pill 3px, each mono data row 3px, the page 54px overall. Scoped to
     the landing so the console keeps Tailwind's default. */
  line-height: normal;
}

/* -----------------------------------------------------------------------------
 * ADDITIONS THE APP NEEDS AND THE DEMO DID NOT.
 * Kept here, above the copied rules, so the boundary between "ported" and
 * "written for the app" is a line in the file rather than a memory.
 * -------------------------------------------------------------------------- */

/* A CSS Grid blowout that the demo does not have and the port does.
   `1fr` is `minmax(auto, 1fr)`, and that `auto` floor is the track's min-content
   width -- which for a replaced element is its intrinsic width. The demo's chip
   is an <img> with no width/height attributes, so the browser gives it a zero
   min-content contribution and the column collapses happily on a phone. The
   port adds width={740} height={496} so the space is reserved before the image
   decodes (no layout shift on a 740x496 chip), and that is exactly what gives
   the element an intrinsic size the track then refuses to shrink below: 740px
   of column inside a 375px viewport, and the whole page scrolls sideways.
   Keeping the attributes and letting the track shrink is the better trade. */
.landing .detect-grid > * {
  min-width: 0;
}

.landing .chipwrap img {
  max-width: 100%;
}

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

FOOTER = """

/* =============================================================================
 * CONTRAST CORRECTIONS.
 *
 * These come LAST on purpose. They are single-class overrides of rules copied
 * verbatim above, at identical specificity, so order is the only thing that
 * decides them -- written into the header instead, the demo's own declarations
 * won and none of this applied.
 *
 * They are deliberate, flagged deviations from a finalised design. Each one is
 * a place where a colour measures below WCAG AA, which is a defect in any
 * palette, and each moves only far enough to be readable while keeping its role
 * and its position in the hierarchy. Measured ratios are quoted so the next
 * person can check rather than trust.
 * ========================================================================== */

/* ink-4 is 1.74:1 on paper -- the worst text contrast in the product. The demo
   spends it on the card eyebrow ("Geometry", "Confidence", "Accountability")
   and on both halves of the card foot, which are real content rather than the
   faint marks ink-4 is for. */
.landing .card .n,
.landing .cardfoot k,
.landing .cardfoot v s {
  color: var(--ink-3);
}

/* The same problem on blue: onblue-2 (paper at 42%) measures 2.79:1 on the
   atlantic band, 3.06:1 on the imperial one and 3.52:1 over the hero. It
   carries the nav's contract tag, the hero stat captions, the instrument
   readout, the stage numbers and every blue-band kicker -- i.e. most of the
   small type on the page. */
.landing .tag,
.landing .stat span,
.landing .stat b s,
.landing .rdo,
.landing .band.blue .kicker,
.landing .cta-band .kicker,
.landing .step span {
  color: rgba(245, 242, 243, 0.72);
}

/* The footer sits on #01113F, where the column headings, the legal row and the
   disclaimer all measured 3.68:1 or below. */
.landing .foot h4,
.landing .foot-base,
.landing .foot-base a {
  color: rgba(245, 242, 243, 0.78);
}

.landing .disclaimer {
  color: rgba(245, 242, 243, 0.74);
}
"""

os.makedirs(os.path.dirname(OUT), exist_ok=True)
io.open(OUT, "w", encoding="utf-8", newline="\n").write(HEADER + out + FOOTER)
print("wrote %s  (%d rules)" % (OUT, len(chunks)))
