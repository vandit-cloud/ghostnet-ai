# GhostNet-AI — UI/UX build prompt (exact)

**What this file is.** The build-side counterpart to `HERO_UIUX_PROMPT.md`.
That file asks a design AI for *pictures*; this one tells an implementer
exactly *what to build and to what numbers*. Every constant below is read out
of the working prototype `~/Desktop/ghostnet-landing-atlantic-fullbleed.html`,
not estimated. Where the two files disagree, this one wins, because it was
transcribed from running code.

**How to use it.** Paste from §0 down. It assumes no prior context.

**Where the work goes.** All landing/hero work lands in the single-file demo
`ghostnet-landing-atlantic-fullbleed.html` on the Desktop. It does **not** go
into `app/frontend/` — that tree is the console application and has its own
lifecycle. (There is currently a stray React/R3F copy of the hero under
`app/frontend/src/components/three/hero/`; it is drifted — see §10 — and is not
the build target.)

**Deadline.** 18 September 2026. Ambition in the hero; restraint everywhere
else. Nothing below should take more than a day to build on its own.

---

## 0. The product, in three claims

GhostNet-AI reads **side-scan sonar waterfall imagery** and flags abandoned
fishing gear ("ghost gear") on the seabed. The entire site argues three points
and no others:

1. **Polygons, not pins.** It predicts the *extent* of the gear. Across 73
   chips the model claims **7.0 %** of the frame where a naive bounding box
   claims **56.5 %** — a search area instead of a shrug.
2. **Calibrated confidence, not a raw score.** 0.9 means roughly nine times in
   ten. The app and the model deliberately speak two different score scales so
   neither can silently drift into the other.
3. **`review_only` by default.** Every detection carries an honest position
   error and waits for human sign-off. A false positive costs a vessel a day; a
   false negative costs the seabed a decade.

**The only figures you may put on screen.** Do not invent others; do not round
these into something more flattering.

| Figure | Meaning |
| --- | --- |
| `0.91` | calibrated confidence on the showcase detection |
| `± 24 m` | median position error |
| `± 31 m` | position error on the showcase detection |
| `7.0 %` | median frame area claimed per chip (vs 56.5 % for a naive box) |
| `425` | polygons in the D2 dataset |
| `73` | annotated chips in D2 |
| `0.000 → 0.525` | net recall, posed as detection vs as segmentation |
| `62` | the total number of *real* net images that exist in our data |
| `5 / 5` | problem-statement classes covered by the taxonomy |
| `2.0 m/s` | survey speed (~4 kn) |
| `0 – 120 m` | across-track range of the swath |

`62` gets the **same typographic weight as the good numbers**. Synthetic volume
was tested and disproved; publishing the ceiling is what makes the rest
credible. Hiding it reads as marketing.

Prior art, reproduced **verbatim**, once, in §6:

> We independently reproduced the central finding of the current state of the
> art — the Microsoft AI for Good Lab and WWF Germany work of September 2025 —
> on different water, and we are in active correspondence with its authors.

Never "in collaboration with Microsoft" or "partnered with WWF". It is interest
and a meeting request.

---

## 1. Tokens — fixed, do not redesign

**Four colours. No fifth hue. Everything else is alpha-layered from these.**

```css
--atlantic:#0F4B70;  /* deep panels, sidebar, sonar water */
--sky:     #C4F8FF;  /* tint on paper; bright ink on blue */
--imperial:#021F94;  /* the one loud accent — ghost_net, primary buttons, active nav */
--paper:   #F5F2F3;  /* canvas, and all text sitting on blue */

--ink:      rgba(2,31,148,.92);
--ink-2:    rgba(15,75,112,.80);
--ink-3:    rgba(15,75,112,.55);
--rule:     rgba(15,75,112,.20);
--onblue:   rgba(245,242,243,.74);
--blue-rule:rgba(196,248,255,.22);
```

**Contrast rule that has already bitten us once:** `imperial` is the accent **on
paper only**. Over water or any dark scrim it reads as a hole punched in the
image — for the duration of any dark treatment the emphasis role passes to
`sky`.

**Type.** Display **Monigue** (fallbacks Glinken, Big Shoulders Display,
Oswald) — heavy, condensed, uppercase. UI **Epoch** (fallbacks Jost, Archivo),
light weights. Data **IBM Plex Mono** — every number, readout, label, eyebrow.

**Display leading must be `0.88`–`0.92`.** Below ~0.88 the lines physically
collide in these faces. `0.8` looks right in a specimen and breaks in a
browser; verify in a real render.

**Texture.** A fine SVG-turbulence grain multiplies over every surface at
opacity ~0.14. It is the only thing stopping the flat colour fields reading as
a template. Keep it.

---

## 2. Page skeleton

```
nav            transparent over the hero, solid paper after it
hero-track     270vh, containing a 100vh sticky pane      → §3–§5
#what          paper band  — the three claims as a card row
#method        atlantic band — Ingest → Chip → Segment → Calibrate → Review
#evidence      paper band  — prior art, 0.525, 62 images, 5/5
#console       the application: survey map, detections list, review queue
#detection     one contact in full: chip, polygon, score, error, review gate
footer         three links: live demo, public repository, technical PDF
```

Plus three things that run *across* sections and carry the feeling:

- **Persistent instrument chrome** — a corner readout that never leaves, so the
  page reads as a vehicle rather than a document. Over the hero it reads live
  telemetry (§5); past the hero it reads section state.
- **A section progress rail** down one side, marked as a **depth descent**.
- **The nav transition** from transparent-over-water to solid-on-paper, driven
  by the same scroll listener as the hero — not a second observer.

---

## 3. The hero — geometry and scale

**What physically happens, in one paragraph.** A survey vessel is under way on
the open sea. As the visitor scrolls, a winch on the stern A-frame lowers a
side-scan sonar towfish on a tow cable. The fish descends and trails further
astern as it goes, the camera following it down through the water column and
under the surface. At working depth it levels out, its sonar comes alive, and a
twin swath opens beneath it and paints the seabed. The scroll ends held on a
contact: a ghost net on the bottom, lit by the swath, tagged `review_only`.

That descent is the spine of the piece. The water, the type and the chrome all
exist to make those 34 metres legible.

**Container.** `.hero-track{height:270vh}` with `.hero-pane{position:sticky;
top:0;height:100vh;overflow:hidden}`. The sequence therefore consumes 170vh of
scrolling and ends at ~47 % of the document: hero in the first half, argument
in the second.

**One number drives everything.** Scroll progress `p ∈ [0,1]`. Every position,
attitude, opacity and intensity is a **pure function of `p`** (plus `elapsed`
for idle wander only). This is what makes it scrub backwards correctly and
survive a pause — see rule 10 in §7.

**The scene is in metres.**

```js
const TOW_DEPTH = 34;                 // working depth of the fish
const SEABED_Y  = -52;                // seabed plane; the fish must visibly fly above it
const SURVEY_SPEED = 2.0;             // m/s, ~4 kn
const TOWFISH_DISPLAY_SCALE = 2.6;    // declared legibility exaggeration
const TOW_POINT = new THREE.Vector3(0, 2.6, 13.2);  // A-frame over the transom, deck height
```

Vessel 28 m bow to transom, waterline at `y = 0`, spanning `z = -14` (bow) to
`z = +14` (transom). Towfish 1.3 m, drawn at ×2.6 — at true scale a 1.3 m body
beside a 28 m hull is ~40 px of a 1000 px frame: honest and completely
illegible as the subject. Set the scale to 1 to see the truthful version. Both
are real modelled assets (`vessel.glb`, `towfish.glb`), not primitives, and the
bow and the fish's nose point the **same way** so the rig reads as one machine.

---

## 4. The hero — choreography table

```js
const STAGE_IDLE_END   = 0.16;
const STAGE_DEPLOY_END = 0.50;
const STAGE_SEARCH_END = 0.76;

const span     = (p,a,b) => clamp01((p - a) / (b - a));
const easeInOut= (t) => t < 0.5 ? 2*t*t : 1 - Math.pow(-2*t + 2, 2)/2;

const deploy = easeInOut(span(p, STAGE_IDLE_END, STAGE_DEPLOY_END));
const ping   = span(p, STAGE_DEPLOY_END - 0.06, STAGE_SEARCH_END - 0.1);
const paint  = span(p, STAGE_DEPLOY_END, 1);
const lock   = span(p, STAGE_SEARCH_END, 1);

const depth   = -TOW_DEPTH * deploy;
const layback = TOW_POINT.z + deploy * 46;
const wander  = deploy * Math.sin(elapsed * 0.7) * 1.4;
fish.set(wander, TOW_POINT.y + depth, layback);
```

`easeInOut` is doing real work: it is the motion of a winch paying out cable
under load, not a free fall.

| `p` | Stage | Label | Sub-caption |
| --- | --- | --- | --- |
| `0 – 0.16` | idle | **UNDER WAY** | 28 m survey vessel · towfish stowed in the A-frame |
| `0.16 – 0.50` | deploy | **PAYING OUT** | winch paying out · fish trimming nose-down |
| `0.50 – 0.76` | search | **ENSONIFYING** | swath open · 120 m across-track · waterfall painting |
| `0.76 – 1.0` | contact | **CONTACT** | ghost_net · 0.91 calibrated · review_only — awaiting sign-off |

The descent takes the largest share (34 % of the scroll) deliberately. A winch
under load is slow; rushing it is the tell.

**The three details that make the descent believable.** Worth more than any
amount of shader polish, because anyone who has run a survey notices their
absence:

- **Depth and layback are coupled, never independent** — the cable is a fixed
  length paying out, so the deeper the fish goes the further astern it trails.
  At full deployment: 34 m down, ~46 m behind the tow point. A fish sinking
  straight down below the transom is wrong.
- **The cable is a catenary whose sag changes** — loose and deeply curved early
  when there is slack in the water, pulled near-straight once the fish is
  flying at depth and speed. A straight line between two moving points reads as
  a rigid rod and kills the illusion instantly.
- **The fish flies nose-down while descending and levels out at depth** —
  trimmed bow-down by its own weight against the cable, then level and heaving
  gently once it is down. A body that stays level all the way down is an object
  falling, not a towed instrument.

```js
/* Peaks mid-descent, zero at both ends — which is what sin(pi*deploy) gives
   without differentiating the eased curve. The model's nose is at -Z and a
   positive X rotation lifts a -Z point, so nose-DOWN is negative. */
const descentPitch = (deploy) => -Math.sin(Math.PI * deploy) * 0.26;
```

**The swath is a bowtie, not a cone.** Side-scan is narrow along-track and wide
across it, with a **dead gap directly beneath the fish** (the nadir) because
the transducers fire out of the flanks, not downward. Two fans, left and right,
nothing between them. Energy is brightest at the transducer and falls away hard
with range. A single cone pointing at the seabed is the most common way this
gets drawn and it is immediately wrong to anyone in the field.

```js
const RETURN_LENGTH = 220;   // along-track extent of the painted strip
const RETURN_WIDTH  = 110;   // ≈ 2·tan(66°)·altitude — the real ensonified strip
const ACOUSTIC_TARGETS = [
  { u: 0.31, v: 0.58, size: 0.055, kind: 'net'  },
  { u: 0.71, v: 0.64, size: 0.040, kind: 'trap' },
];
```

**Camera.** It anchors to the **subject**, never to hand-typed world points.
While paying out, the anchor is the **midpoint of the cable**, so ship, cable
and fish stay in one frame — a descending fish with the ship cropped away is
just an object falling. Once the fish is down, the anchor slides onto the fish,
biased downward by half its altitude so the frame straddles fish and seabed.
Perspective camera, fov 42, near 0.5, far 1400.

**Composition — the part to hold onto.** Two copy blocks pinned to opposite
ends of the frame, horizon and ship in the gap between them: eyebrow and
headline above; paragraph, CTAs and stat rule below. As the winch starts, the
two blocks clear **in opposite directions** — headline up, foot down — so the
frame *opens* rather than merely dimming, and the instrument overlay takes the
space they vacate. Stacking all copy from the top instead puts the paragraph
across the superstructure; that was tried and it fails.

**HUD.** Top marquee `GN-0412 · ping 18 402 · ghost_net 0.91 · ± 31 m ·
review_only`; right-hand readout (depth / layback / speed, live from the same
`fish` vector, not a second animation); bottom-left stage label and
sub-caption, swapped on the boundaries in §4. The ping counter increments
**only while ensonifying**.

---

## 5. Water and light

A four-band column, sunlit to near-black, sampled as one ramp:

```js
const WATER_BANDS = [
  { to:  -14, col: [0.380, 0.600, 0.712] },  // sunlit: sky over atlantic
  { to:  -30, col: [0.059, 0.294, 0.439] },  // atlantic, the working band
  { to:  -44, col: [0.027, 0.166, 0.408] },  // atlantic into imperial
  { to: -999, col: [0.004, 0.054, 0.261] },  // imperial, dark
];
const BAND_BLEND = 13.0;   // metres of blend — they OVERLAP, deliberately
```

**13 m is the single most important number in the water.** The dome is a sphere
centred on the camera, so a constant depth is a horizontal plane: any tight
blend draws a hard rule straight across the frame and the four bands read as
flat-shaded slabs — a low-poly render, not water. At 13 m the blends overlap,
no boundary is ever visible alone, and the four colours act as stops on one
continuous ramp. This was the most-reported problem during the build.

**The atmospheric haze must be sampled from this same ramp at the camera's own
depth, every frame.** Computed separately, the haze and the water drift apart
and the scene reads as two unrelated blues.

**Effects, in priority order** — build top-down and stop when the budget runs
out:

1. **God rays** — soft converging shafts from just under the surface, reaching
   ~96 m down, brightest at the top, fully absorbed by working depth. Fade
   their horizontal extent or their own edges show as a straight cut.
2. **Caustics** across the *entire* seabed, not a patch. Cellular and crisp,
   net-like — never soft blobs.
3. **Sun glitter** on the surface from above, as a **path** running back toward
   the sun with calmer water either side, fading to nothing as the camera
   submerges. A uniform specular sheen is what makes CG water look like plastic.
4. **Marine snow** — suspended particulate drifting astern at survey speed.
5. **Bubble columns** — three thin streams, slow.
6. **Vignette** — dark edges, bright light column in the centre.
7. **A hard horizon** where sea meets sky, dissolving the instant the camera
   goes under.

**Seabed.** `PlaneGeometry(1500, 1500, 150, 150)` centred at `z = 40`,
displaced by value noise into gentle relief — never a flat plane. Scattered
debris: a **ghost net** as a wireframe mesh draped over a low mound with floats
still attached, a lost trap, boulders, a drum, a tyre. The net is the payload of
the whole sequence — give it the light.

---

## 6. Sections below the hero

- **`#what`** — paper. The three claims of §0 as a card row. Lead each card
  with its number in IBM Plex Mono at display size; the prose is support.
- **`#method`** — deep `atlantic` band. Ingest → Chip → Segment → Calibrate →
  Review, each stage auditable on its own, each stating what it consumes and
  what it emits. `sky` carries emphasis here, not `imperial` (§1).
- **`#evidence`** — paper. The prior-art sentence verbatim, `0.000 → 0.525`,
  the `62 images` ceiling, `5 / 5` coverage. This section is where honesty is
  the design.
- **`#console`** — the working application: survey map, detections list, review
  queue. Build the frame and one representative screen.
- **`#detection`** — one ghost-gear contact in full: the sonar waterfall chip,
  the predicted polygon overlaid, the calibrated score, the position error, and
  the `review_only` gate with accept / reject / escalate.
- **`footer`** — live demo, public repository, technical PDF.

---

## 7. Hard-won rules — every one shipped as a visible defect first

Treat this as the most valuable section. None of it is theory.

1. **Paint the swath directly beneath the towfish.** It was once drawn 30 m to
   one side. The single relationship the piece exists to show was broken and
   nobody could say why the scene felt wrong.
2. **Declare each contact once.** The bright sonar return and the physical
   object on the seabed must come from the same coordinate, or you get a sonar
   contact with nothing underneath it.
3. **Forward motion is sold by near-field parallax, never by a fast seabed.**
   At an honest 2 m/s nothing in the far field visibly moves — 2 m/s across a
   400 m plane takes over three minutes. Speeding the seabed up to compensate is
   exactly what reads as a treadmill: the eye compares near and far motion and
   knows they disagree. Particles near the lens do the work, as in real ROV
   footage.
4. **A ship on water with no horizon reads as sunk, not floating.** Never tilt
   the camera down far enough to lose the horizon in order to make room for
   copy. Solve that in the layout.
5. **Lighting must never end on a straight line.** Any light that stops at the
   edge of the surface carrying it destroys the illusion instantly. Feather
   every boundary.
6. **Everything distant must haze, including the effects.** Light added after
   the fog is applied comes back at full strength 700 m away and draws a hard
   line across the frame.
7. **Sharper is not more contrast.** Pushing the caustic falloff too far erases
   the web entirely and flattens the floor.
8. **Detail size is relative to the camera, not the world.** Sun-glitter cells
   of 0.6 m project to ~13 px blocks and read as confetti; ~11 cm reads as
   grain; smaller goes sub-pixel and aliases into shimmer.
9. **Physically defensible transparency can still be perceptually wrong.** A
   surface transparent enough to read the keel through makes the ship look
   parked on glass.
10. **Attitude and position are functions of scroll, not of the clock.**
    Otherwise the scene stops scrubbing backwards and desynchronises on pause.
    The only legitimate use of `elapsed` is idle wander and heave.

---

## 8. Constraints

**Responsive.** Below ~1000 px the scene becomes a dimmed **full-bleed
backdrop** behind the copy rather than a column, with a scrim heavy enough to
carry paper text. Instrument chrome hides. No horizontal overflow at 400 px.
Build this state explicitly — it is not "it scales".

**Reduced motion and low power.** A poster frame at roughly the contact stage,
with the HUD rendered as static text. Never a blank hero.

**Performance.** 60 fps on integrated graphics. Prefer one billboarded volume
over many meshes; prefer a CSS gradient over a post-processing pass when the
result is identical.

**Accessibility.** The scroll sequence is never the only route to any
information — everything the hero says also appears in the sections below.
Check paper-on-water contrast in both the light and dark bands, and keep focus
states visible against the scene.

---

## 9. Definition of done

- [ ] Scrubs correctly in **both** directions and survives a mid-scroll pause.
- [ ] Ship, cable and fish share the frame for the whole of `0.16 – 0.50`.
- [ ] The swath is a bowtie with a visible nadir gap, beneath the fish.
- [ ] Sonar return and seabed object share one coordinate.
- [ ] No visible horizontal seam anywhere in the water column.
- [ ] Horizon present until the camera submerges, then gone.
- [ ] `62` set at the same weight as `7.0 %`.
- [ ] Prior-art sentence present once, verbatim, unembellished.
- [ ] 400 px wide: no horizontal scroll, copy legible over the scrim.
- [ ] `prefers-reduced-motion`: poster frame, not a blank pane.

---

## 10. Known drift to resolve before building

`app/frontend/src/components/three/hero/stages.ts` is a React/R3F port of this
hero that has drifted from the demo: it uses `STAGE_IDLE_END = 0.22` and
`STAGE_SEARCH_END = 0.78` against the demo's `0.16` and `0.76`, which is a
visibly different idle hold and contact hold. The demo is the source of truth
(§0). Either re-sync that file from the table in §4 or delete it; do not tune
against it.

<!-- TODO(rudra): the one choreography decision still open.
     Between p = 0.50 and p = 0.56 the camera anchor moves from the cable
     midpoint to the fish. Pick how:
       (a) hard switch at 0.50      - simplest, but the frame jumps
       (b) linear lerp over 0.06    - safe, reads slightly mechanical
       (c) easeInOut lerp over 0.06 - matches the winch easing, costs nothing
     Trade-off: a longer blend keeps the ship in frame later (good for scale,
     bad because the fish is then small and off-centre exactly when the sonar
     lights up). Write the chosen anchor() here as 5-10 lines. -->
