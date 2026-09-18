# GhostNet-AI — Survey Map "Plate" reproduction spec

The reference image lives at `app/frontend/public/lab/survey-plate-reference.png`
(1254 x 1254, square). The live reproduction lives at route **`/lab/map`**.

This file is the *measurement*, not an impression. Every number below is either
read off the plate directly or derived from one that was. Positions are given as
**frame fractions** — `fx = x / width`, `fy = y / height`, origin top-left — so
the spec is resolution-independent. Where a pixel figure is quoted it is quoted
at the reference's native 1254 px and tagged `@1254`.

> **Implementation note (18 Sep 2026).** The reproduction is a **real 3D
> scene**, not a drawn one. It reuses `components/three/OceanSurface.tsx` for
> the water, `public/models/vessel.glb` via `ModelSlot` for the hull, and an
> actual `PerspectiveCamera` — so §1's hand-fitted projection is now only of
> historical interest, and the live parameters are
> `app/frontend/src/features/maplab/plate.ts`. §2's tones survive as the
> daylight values passed into `OceanSurface`. The coverage is rendered as
> **mitred angular slabs** (§13.1), which is the reference's own form.

Read §1–§2 to understand the photograph. Read §3–§9 to build the overlay; that
is the part GhostNet actually ships. §10 is the whole parameter block in one
copyable place. §11 is how the same visual language survives the move onto a
real Leaflet basemap and into the three.js 3D view.

---

## 0. What it is, in one paragraph

A high-oblique aerial photograph of a research vessel under way, with a
**synthetic geospatial overlay composited onto the sea surface in the
photograph's own perspective**. The overlay has exactly four elements and no
more: (a) a translucent cyan **coverage swath** — a continuous ribbon of flat
quads lying on the water, textured with a fine survey grid; (b) a white
**dashed route line** running the swath's centreline; (c) white **waypoint
nodes** on that line; (d) a single **target marker** at the far end. The route
is a classic **boustrophedon (lawnmower) survey pattern** — parallel traverses
joined by 180° turns at alternating ends. The swath is anchored to the vessel:
its nearest, widest segment begins *at the stern*, in the wake, and the pattern
recedes toward the horizon, narrowing purely by perspective. Nothing glows in a
neon way; the line is near-white with a tight cyan bloom, and the swath reads as
tinted glass over water, never as a solid fill.

The single idea to preserve if everything else is dropped: **the overlay is on
the water, not on the screen.** It obeys the photograph's vanishing point,
occludes nothing, and is transparent enough that the sea's own texture — chop,
sun glitter, reef colour — reads straight through it.

---

## 1. Frame, camera, horizon

| Property | Value | Note |
|---|---|---|
| Aspect | 1:1 | square crop; the reproduction must letterbox, not stretch |
| Horizon line | `fy = 0.076` | @1254 → y ≈ 95 px |
| Sky band | `fy` 0.000 → 0.076 | 7.6% of frame height; tiny but load-bearing |
| Vanishing point | `fx ≈ 0.52`, `fy = 0.076` | slightly right of centre |
| Camera pitch | ≈ **-38°** from horizontal | derived: see below |
| Camera height | ≈ 190–230 m above sea level | derived from vessel scale |
| Effective FOV (vertical) | ≈ 52° | |

**How pitch was derived.** The vessel is ~62 m long (a coastal research vessel
with a helideck-free aft A-frame) and subtends `fy` 0.605 → 0.755 at
`fx ≈ 0.46`. A 62 m object filling 15% of a 52° vertical frame puts the camera
at roughly 210 m slant range on a down-angle that places the horizon at 7.6%
from the top. Any reproduction that keeps **horizon at 0.076 and the vessel
occupying 0.15 of frame height** will match, regardless of how it gets there.

**Ground-plane compression.** This is the number the overlay lives or dies by.
Distance along the sea surface does not map linearly to `fy`. The implementation
uses a **true pinhole ground projection** — screen offset from the horizon goes
as `1/depth` on *both* axes:

```
depth = v + d0
fy    = horizonY + A / depth
fx    = vanishX  + q * u * (fy - horizonY)
```

with `A = 0.781`, `d0 = 1.15`, `q = 0.606`, `v` and `u` in units of one swath
width. `d0` is the camera's own standoff: the vessel sits at `v = 0` and must
not be at infinite screen depth, so the camera is 1.15 swath-widths behind it.
`A/d0 = 0.679` is what puts the stern at `fy = 0.755`.

An earlier draft of this file fitted a `(fy - horizonY)^p` power law to the
reference's measured leg widths and landed on `p = 0.62`. That fit is **wrong**
and is recorded here only so nobody re-derives it: the measured "widths" mixed
two different quantities — the *horizontal* extent of the outbound leg, whose
across-track axis is `u`, and the *vertical* thickness of the traverses, whose
across-track axis is `v`. They do not share an exponent because they are not the
same measurement. The pinhole model handles both correctly and needs no
exponent at all.

Where the legs land under the shipped parameters:

| Leg | `v` (swath widths) | Centreline `fy` |
|---|---|---|
| Outbound (at the stern) | 0.00 | 0.755 |
| L1 | 0.95 | 0.448 |
| L2 | 1.80 | 0.341 |
| L3 | 2.65 | 0.282 |
| L4 | 3.50 | 0.244 |
| L5 | 4.35 | 0.218 |
| L6 | 5.20 | 0.199 |

The reference's own legs sit at `fy` 0.960 / 0.520 / 0.385 / 0.280 / 0.190 /
0.135 — a much wider spread, because its leg spacing is **artistically
exaggerated** and grows with distance. Real evenly-spaced survey lines bunch
toward the horizon the way the table above does. See §13.

---

## 2. The photographic plate (background)

The overlay is the deliverable; the plate is the environment it must sit
convincingly inside. If the product renders over a real basemap (§11) this
section becomes a *tone target* rather than something to draw.

### 2.1 Sky

A 7.6%-tall band, vertically graded, plus a hot patch top-left.

| Stop | `fy` | Hex |
|---|---|---|
| Top of frame | 0.000 | `#2E7BC4` |
| Mid sky | 0.040 | `#5FA3D8` |
| At horizon | 0.076 | `#BBD9EC` |

Top-left corner carries a diffuse **sun bloom** centred off-frame at
`fx ≈ -0.05, fy ≈ 0.02`: a radial white at 0.38 alpha, radius `0.30` of frame
width, `screen` blend. This is the light source for everything else and its
position is not negotiable — the sea glitter, the wake highlights and the
island shading all point away from it.

### 2.2 Sun glitter path on water

A vertical silvered sheet down the **left edge**, the specular reflection of
that same sun. It occupies `fx` 0.00 → 0.16 (widening to 0.22 at `fy = 0.42`)
and `fy` 0.076 → 0.62, fading out below. Rendered as white at 0.10–0.34 alpha,
`screen`, modulated by the same wave noise as the sea so it breaks into
horizontal glint bands roughly 3–6 px tall @1254. It is brightest at
`fy ≈ 0.18` and dies by `fy = 0.66`.

### 2.3 Water

Three depth/distance bands, blended, **not** three hard zones:

| Band | `fy` range | Hex | Role |
|---|---|---|---|
| Distant | 0.076 → 0.22 | `#2C6FA8` | hazed, desaturated by the atmosphere |
| Mid | 0.22 → 0.60 | `#12508C` | the plate's "true" open-ocean blue |
| Near | 0.60 → 1.00 | `#0A3766` | darker, and where surface chop is resolved |

Chop: anisotropic noise, wavelength ~14 px @1254 in the near field scaling down
to ~2 px at the horizon, contrast ±6% luminance, stretched **3.2:1
horizontally**. Below `fy = 0.75` individual wave crests resolve and pick up a
`#8FBEDC` highlight on their sun-facing (left) side.

### 2.4 Islands and reef

Three rocky clusters, all with the same anatomy — dark rock core, bright
turquoise shallow-water shelf, soft transition to open blue.

| # | Centre (`fx`, `fy`) | Rock extent | Shelf halo |
|---|---|---|---|
| A (upper-left) | 0.285, 0.170 | 0.075 x 0.028 | +0.030 |
| B (mid-left) | 0.295, 0.335 | 0.070 x 0.035 | +0.035 |
| C (right, largest) | 0.865, 0.352 | 0.150 x 0.090 | +0.075, strongly asymmetric south-west |

Rock: `#4A4335` in sun, `#221F1A` in shade, with `#6E6650` on the sunlit
(left/upper-left) faces and a white surf collar 2–3 px @1254 on the exposed
south-west edges.
Shelf: `#3FBFC4` at its brightest immediately off the rock, falling through
`#2E8FAE` to the open-ocean blue over the halo distance given above. Island C's
reef extends far south — a broad `#2E9AAE` plume from `fy` 0.36 down to 0.42
between `fx` 0.78 and 0.98.

Islands are **scenery**: the overlay passes over them without interacting, and
no route node ever lands on one.

### 2.5 Vessel

A white-superstructure, blue-hull survey vessel, bow-up (heading directly away
from camera), at `fx = 0.460, fy = 0.680` (waterline centre).

| Part | `fy` span | Colour |
|---|---|---|
| Mast / radar | 0.598–0.620 | `#E8EDF0` |
| Two radomes (spheres) | 0.618–0.640 | `#F2F4F6` |
| Bridge / superstructure | 0.640–0.700 | `#F5F7F8`, window band `#243A4C` |
| Hull, port/starboard | 0.700–0.760 | `#1D4F86` |
| Aft deck plant | 0.700–0.735 | `#D8A32B` (the only warm hue in the frame) |
| Deck rails / handling frame | 0.705–0.745 | `#C9CFD3` |

That single yellow deck crane at 0.5% of frame area is the plate's only warm
accent and it is what makes the vessel read as *working* rather than parked.
Keep it.

### 2.6 Wake

Three components, all white foam at varying alpha:

1. **Propeller wash** — a straight column directly astern, `fx` 0.425 → 0.480,
   from `fy = 0.760` to the bottom edge. Densest foam, alpha 0.85 → 0.30.
2. **Divergent Kelvin arms** — two trails leaving the stern at **±19.5°** from
   the heading (the Kelvin half-angle; do not invent a different one), reaching
   `fx = 0.29` and `fx = 0.62` at the bottom edge. Alpha 0.70 at the stern
   decaying to 0.25, width growing 6 px → 34 px @1254.
3. **Turbulent inner field** — between the arms, broken foam cells 8–20 px
   @1254 at alpha 0.15–0.45, scrolling toward the camera.

The wake is what sells motion. The nearest swath segment is deliberately drawn
*over* the wake, which is the visual claim that the sonar is scanning **now**.

---

## 3. The overlay — coordinate model

Build the overlay in **survey space**, then project. Do not author it in screen
pixels; every attempt to do that has produced turns that bend the wrong way
under perspective.

Survey space is a right-handed plane: `u` across-track (metres, +right), `v`
along-track (metres, +away from camera), origin at the vessel's stern on the
waterline. One "swath width" `W` is the unit of interest.

The shipped survey layout, in swath widths:

```
swathW      = 1.0      (1400 m -- 700 m per side, a plausible deep-tow SSS range)
legSpacing  = 0.85     -> 15% overlap between adjacent swaths
sternTrail  = 1.10     how far BEHIND the vessel the swath starts
outboundV   = 0.95     how far it runs out before the first turn
legHalfLen  = 1.50     half a traverse
legTaper    = 0.96     each leg out is 4% shorter
legDrift    = 0.05     each leg's centre walks +u by this much
turnRadius  = 0.62     MUST exceed 0.5 -- see below
turnOvershoot = 0.10
```

`legSpacing` is deliberately **smaller than `swathW`** — 0.85 against 1.0, a
15% overlap. That overlap is why the ribbon reads as one continuous sheet with
no gaps between legs, and it is also correct survey practice: you plan overlap
so each pass's nadir gap is covered by its neighbour. Set it to 1.0 and the
pattern looks striped and wrong.

`sternTrail` is the small detail that fixes the near field. Start the route at
the vessel and the swath ends in a hard straight line under the hull; start it
1.1 swath-widths *behind*, and the ribbon runs off the bottom edge and the
vessel reads as sitting inside water it has already scanned — which is both
what the reference shows and the true statement about a towed sonar.

**`turnRadius` must exceed half the swath width.** Below 0.5 the ribbon's inner
offset edge has a smaller radius than the offset itself, so it folds back
through itself, and the fold lands as a bright chevron in the middle of the
ribbon at every turn. The *fill* does not care — it composites as a union and
the fold is invisible — but any stroked edge draws it. See §8.2.

Projection, survey space → frame fractions:

```
fy = horizonY + k / (v/W + d0)            // §1, k = 0.1655, d0 = 0.155
scale(fy) = (fy - horizonY) ^ 0.86 * S    // S calibrated so leg L1 spans 0.560
fx = vanishX + (u / W) * scale(fy)
```

---

## 4. Route geometry

Six traverses, alternating direction, joined by five 180° turns. In the plate
the vessel is mid-pattern: it has *completed* nothing — leg L1 is being cut
right now — and the target marker sits at the far end of L6.

Turn shape is the detail people get wrong. The turns are **not** square corners
and **not** semicircles. They are **teardrop / racetrack turns**: the route
overshoots past the end of the leg by `0.22 * Lx`, curves through 180° with a
radius of `0.55 * dv`, and rejoins the next leg tangentially. In the plate this
reads as a soft, slightly asymmetric hook at each end — flatter on the outbound
side, tighter on the return.

Leg endpoints, as measured (`fx` of the two ends, and the centreline `fy`):

| Leg | Direction | Left end `fx` | Right end `fx` | `fy` |
|---|---|---|---|---|
| L1 | away from camera | 0.16 | 0.72 | 0.960 |
| L2 | right → left | 0.13 | 0.89 | 0.520 |
| L3 | left → right | 0.17 | 0.92 | 0.385 |
| L4 | right → left | 0.25 | 0.82 | 0.280 |
| L5 | left → right | 0.29 | 0.79 | 0.190 |
| L6 | right → left | 0.40 | 0.75 | 0.135 |

Note the legs are **not** all the same survey-space length — L4–L6 are shorter.
The pattern narrows as it goes out, which is what an operator actually plans
when the area of interest is a wedge. Reproduce the taper; a perfect rectangle
of legs looks synthetic.

The route enters the frame at the **stern of the vessel** (`fx 0.46, fy 0.755`)
and the first thing it does is fan outward through the wake — the near segment
of L1 is the single widest element in the frame, spanning `fx` 0.16 → 0.72 at
the bottom edge.

---

## 5. The route line

| Property | Value |
|---|---|
| Colour | `#EAF9FF` (near-white, a half-step cool) |
| Core width | `2.6 px` @1254 at L1, `1.1 px` at L6 — scales with `scale(fy)`, clamped to `[1.0, 3.0]` |
| Dash pattern | `10 / 8` @1254 at L1 (dash / gap), scaled by `scale(fy)`, **minimum gap 2.5 px** |
| Cap | butt — not round; round caps at small scale merge the dashes into a solid line |
| Bloom | two passes: `blur 3 px` at alpha 0.55 in `#7FD4FF`, then `blur 9 px` at alpha 0.22 in `#3FA6E8`, both under the core |
| Opacity | 1.0 near, 0.82 at L6 (atmospheric fade) |

The dash is what makes it read as a *plan* rather than a *path travelled*.
Keep the dash phase continuous along the whole polyline — restarting the
pattern at each vertex produces visible stutter at the turns, which is the most
common tell of a naive implementation.

---

## 6. Waypoint nodes

Filled white discs on the centreline. Two sizes, and the distinction is
semantic, not decorative:

| Kind | Where | Radius @1254 (L1 / L6) | Fill | Halo |
|---|---|---|---|---|
| **Turn node** | at each of the 5 turn apexes, and at both ends of every leg | 8.0 / 3.6 px | `#FFFFFF` | radial `#8FDCFF` 0.45 → 0, r x 3.2 |
| **Tick node** | at regular intervals mid-leg, ~2 per leg | 5.5 / 2.4 px | `#F2FBFF` | radial `#8FDCFF` 0.30 → 0, r x 2.6 |

Count in the plate: **24 nodes** total. Nodes never carry labels in this
composition — the moment a node gets a text label the image stops reading as a
sea surface and starts reading as a diagram.

---

## 7. The target marker

At the far end of L6, `fx = 0.706, fy = 0.098`. Three stacked parts, all white:

1. **Pennant triangle** — an equilateral-ish triangle, apex up, 11 px tall
   @1254, sitting 9 px above the ring, `#FFFFFF`, no stroke.
2. **Ring** — circle, radius 6 px, stroke 1.6 px, `#FFFFFF` at 0.95, fill none.
3. **Core dot** — radius 2.2 px, `#FFFFFF`, centred in the ring.

Plus a **short lead-out**: the dashed route continues 0.055 of frame width past
the ring to `fx = 0.755`, ending in a plain terminal node. That small overshoot
is what makes the marker read as "next waypoint, survey continues" rather than
"end of data".

The whole marker gets a slightly stronger bloom than the line: `blur 6 px`,
`#9FE2FF`, alpha 0.5. It is the only element permitted to be the brightest
thing in the overlay.

---

## 8. The coverage swath

The largest element by area and the one that carries the "this is instrumented
water" idea.

### 8.1 Geometry

For each leg, a ribbon built as a triangle strip from the centreline: at every
sample point along the leg, two vertices at `u ± W/2`, projected through §3.
Sample at least every `0.02 * Lx` so the turns stay smooth. The ribbon is
**continuous through the turns** — it does not break and restart per leg, which
is what produces the plate's single folded sheet.

Where two legs overlap (the 18% from §3), the fills **must not** simply
alpha-composite to a brighter band — the plate shows no such seam. Render the
entire swath to an offscreen buffer at full alpha, then composite that buffer
once at the target opacity. This is the single most important implementation
note in this section.

### 8.2 Fill

| Layer | Value |
|---|---|
| Base fill | `#2E9BE0` at **0.26** alpha |
| Depth modulation | multiply by `0.74 + 0.26 * (fy - horizonY)/(1 - horizonY)` — far segments read thinner, as haze demands |
| Blend | `screen` over the water, **not** `normal` — normal blending greys the sea underneath and kills the chop showing through |
| Leading edge (bow-side of each ribbon) | a 3 px @1254 band of `#9FE2FF` at 0.40, falling to 0 over 14 px inward |
| Outer edges (port/starboard) | 1.4 px `#7FD4FF` at 0.55, constant along the ribbon |

### 8.3 The grid texture

The fine cross-hatch inside the swath. It is what makes the ribbon read as
*survey data* and not as a coloured highlighter stroke.

| Property | Value |
|---|---|
| Along-track lines (parallel to centreline) | every `W/16` in `u` → 17 lines across the ribbon |
| Across-track lines (ping lines) | every `Lx/64` in `v` |
| Colour | `#C4F8FF` at **0.085** alpha |
| Width | 0.7 px @1254, **never scaled below 0.5 px** — below that, switch to reducing alpha instead, or the grid aliases into moiré |
| Fade | grid alpha falls to 0 over the outer 8% of the ribbon width, so the grid never touches the bright outer edge |

The grid must be generated **in survey space and projected**, so it converges
with the ribbon. A screen-space grid clipped to the ribbon shape is the wrong
answer and is immediately obvious at the turns.

### 8.4 The stern anchor

The near end of the swath does not have a straight edge. It fans from the
vessel's stern: the ribbon's two outer edges converge to a point at
`fx 0.460, fy 0.755` (the stern), producing the wedge that occupies the bottom
sixth of the frame. Over the wake, the swath's alpha is raised to **0.34** and
the grid to **0.12** — the brightest part of the whole overlay, because it is
the part being acquired right now.

---

## 9. Animation (for the live version; the plate is one frame of it)

| Element | Motion | Period |
|---|---|---|
| Route dash | phase offset marching **toward the target** | 2.4 s per dash cycle |
| Stern wedge | alpha breathing 0.30 ↔ 0.38 | 3.2 s, ease-in-out |
| Across-track grid lines | scroll away from the vessel at leg speed | matches vessel speed |
| Target marker | ring scale 1.00 ↔ 1.12, alpha 0.95 ↔ 0.70 | 2.0 s |
| Turn nodes | none | — |
| Wake foam | scroll toward camera | 1.6 s |

Everything above must be gated on `prefers-reduced-motion` — the repo already
has `useReducedMotion` for exactly this. Under reduced motion, hold the dash
static and drop the breathing; keep the target ring, at a slower 4 s.

---

## 10. The parameter block

The live block is `app/frontend/src/features/maplab/plate.ts` — that file is the
single source of truth and this is a copy of it. Tuning means editing PARAMS,
never the renderer.

```js
// ---- camera (true pinhole ground projection) ------------------------------
horizonY: 0.076   vanishX: 0.52   A: 0.781   d0: 1.15   q: 0.606

// ---- survey space (units of one swath width) ------------------------------
legs: 6            legSpacing: 0.85   sternTrail: 1.10   outboundV: 0.95
legHalfLen: 1.50   legTaper: 0.96     legDrift: 0.05
turnRadius: 0.62   turnOvershoot: 0.10   swathWidthM: 1400

// ---- route line -----------------------------------------------------------
lineColor: "#EAF9FF"   width: 2.0   widthMin: 1.0   widthMax: 2.8
dash: 14   gap: 9   gapMin: 2.5   farOpacity: 0.82
bloomNear: { blur: 3, color: "#7FD4FF", alpha: 0.42 }
bloomFar:  { blur: 9, color: "#3FA6E8", alpha: 0.16 }

// ---- nodes ----------------------------------------------------------------
turnRadius: 8.0   tickRadius: 5.5   radiusMin: 2.2   ticksPerLeg: 2
fill: "#FFFFFF"   halo: "#8FDCFF"   haloAlphaTurn: 0.45  haloAlphaTick: 0.30
haloScale: 3.2

// ---- target ---------------------------------------------------------------
pennantH: 11   pennantGap: 9   ringRadius: 6   ringWidth: 1.6   coreRadius: 2.2
leadOut: 0.22  bloom: { blur: 6, color: "#9FE2FF", alpha: 0.5 }  pulsePeriod: 2.0

// ---- swath ----------------------------------------------------------------
fill: "#2E9BE0"   alpha: 0.22   alphaStern: 0.30   depthMod: [0.74, 1.00]
edgeOuter: { color: "#7FD4FF", alpha: 0.55, width: 1.4 }
edgeLead:  { color: "#9FE2FF", alpha: 0.40, width: 3, falloff: 14 }
sternBreathPeriod: 3.2

// ---- grid -----------------------------------------------------------------
color: "#C4F8FF"  alpha: 0.085  alphaStern: 0.12  across: 16  along: 64
width: 0.7   widthMin: 0.5   edgeFade: 0.08

// ---- plate ----------------------------------------------------------------
skyTop: "#2E7BC4"   skyMid: "#5FA3D8"   skyHorizon: "#BBD9EC"
seaFar: "#2C6FA8"   seaMid: "#12508C"   seaNear: "#0A3766"
sunAt: [-0.05, 0.02]   sunRadius: 0.30   sunAlpha: 0.38   glitterTo: 0.66
reefBright: "#3FBFC4"  reefMid: "#2E8FAE"  rock: "#4A4335"  rockLit: "#6E6650"
islands: [ {0.255, 0.165}, {0.155, 0.315}, {0.905, 0.245} ]   // moved off the
                                    // reference's spots so they FRAME the
                                    // pattern instead of sitting under it

// ---- vessel and wake ------------------------------------------------------
fx: 0.46   fy: 0.755   lengthFy: 0.105   hull: "#1D4F86"
superstructure: "#F5F7F8"   deckPlant: "#D8A32B"
kelvinDeg: 19.5   wakeAlpha: [0.25, 0.85]   wakeScrollPeriod: 1.6

// ---- animation ------------------------------------------------------------
dashPeriod: 2.4
```

---

## 11. How this becomes the product map

The plate is a hero composition. The product needs the same *visual language* in
three places, and the language survives the move because it was authored in
survey space (§3), not in screen pixels.

### 11.1 The 2D Leaflet map (`MapView.tsx`)

Straight substitution — §3's projection is replaced by Leaflet's, everything
else holds:

- **Swath** → the existing `buildCorridor()` polygon, restyled per §8.2/§8.3.
  Note `buildCorridor` already derives half-width from each track point's real
  `range`, which is the honest version of §3's fixed `W`. Keep it honest — the
  spec's constant `W` is a reference-image convenience only.
- **Route line** → the existing track `Polyline`, restyled per §5 with the
  dash pattern and a second, wider, low-alpha `Polyline` underneath for the
  bloom (SVG filters on Leaflet paths are unreliable across browsers; a
  stacked polyline is the robust bloom).
- **Nodes** → `L.circleMarker` at turn points, detected by heading change
  exceeding 90° between consecutive track points.
- **Target** → a `divIcon` carrying the §7 SVG.
- **Basemap** → the plate's sea palette (§2.3) is the tone target for the
  `marine` basemap treatment; the existing OSM layer needs a filter to reach it.

In plan view there is no perspective, so `scale(fy)` collapses to a constant
and all the width/dash figures take their **L1** values, scaled by zoom.

### 11.2 The 3D survey view (`Scene3D` / `CoverageSwath.tsx`)

Closest to the plate, since it has a real camera. `CoverageSwath` already
builds the correct triangle strip; what it lacks is §8.2's edge treatment,
§8.3's grid, and the §8.1 single-composite rule. Its current
`opacity: 0.07` is far below the plate's 0.26 — the plate's swath is assertive
and the current one is nearly invisible.

### 11.3 The landing hero

The plate *is* a landing composition. If it goes there, the photograph is
replaced by the existing water shader (`docs/WATER_PROMPT.md`) and the overlay
is drawn into the same scene, sharing its camera. The two specs agree on colour
already: the plate's `seaMid #12508C` and the shader's Atlantic band `#0F4B70`
are the same family, and the overlay's `#C4F8FF` grid is the brand `--sky`
exactly.

### 11.4 Palette conformance

The overlay is **already inside the Atlantic palette** and must stay there:

| Spec token | Value | Brand |
|---|---|---|
| `gridColor` | `#C4F8FF` | `--sky`, exact |
| `swathFill` | `#2E9BE0` | `--sky` lifted toward `--atlantic`; the one derived hue |
| `lineColor` | `#EAF9FF` | `--paper` cooled; reads as paper on blue |
| `nodeFill` | `#FFFFFF` | pure white, permitted for point marks only |
| `seaMid` | `#12508C` | `--atlantic` `#0F4B70` brightened for daylight |

Nothing in this spec introduces a fifth hue. The warm `#D8A32B` deck crane is
photographic content, not UI, and does not enter the token set.

---

## 12. Acceptance checks

Run these against any implementation before calling it a match:

1. **Horizon at `fy = 0.076`.** Everything else is built off it.
2. **Six legs, alternating, tapering.** Not five, not uniform.
3. **No seam where legs overlap.** If a brighter band appears between adjacent
   ribbons, §8.1's single-composite rule was not followed.
4. **Grid converges with the ribbon at the turns.** If it stays axis-aligned,
   it was drawn in screen space.
5. **Dash phase continuous through turns.** No stutter at vertices.
6. **The stern wedge is the brightest part of the swath** and overlaps the wake.
7. **Chop reads through the swath.** If the water under the ribbon looks flat,
   the blend is `normal` where it should be `screen`.
8. **Nothing is labelled.** No text anywhere in the overlay.

---

## 13. Where the reproduction knowingly diverges from the reference

Run the lab's wipe (`R`) and these are what you see. Each is a decision, not a
miss, and each is reversible if the call goes the other way.

### 13.1 Smooth swept ribbon vs. angular slabs

The reference's coverage is a set of **flat, hard-edged trapezoids** with
mitred corners — planar patches laid along the route, not a swept corridor.
The reproduction sweeps a true ribbon: offset the centreline by ±half a swath
at every sample and triangulate. The ribbon is what a real sonar footprint is,
and it is what `CoverageSwath.tsx` and `buildCorridor()` already produce, so it
transplants into the product unchanged. The reference's slabs look sharper and
more graphic, and they read better at small sizes.

**This is the one decision worth taking deliberately**, because it changes the
character of every map in the product, not just the hero.

### 13.2 Even leg spacing vs. the reference's exaggerated spread

The reference's legs sit at `fy` 0.960 → 0.135; the reproduction's at
0.755 → 0.199. The reference widens its line spacing with distance, which no
even-spaced survey does — it is an artistic choice that fills the frame. The
reproduction keeps spacing even, so the legs bunch toward the horizon the way
real survey lines do, and no gaps ever open between adjacent swaths.

Variable line spacing *is* a real planning technique (wider spacing over
low-priority ground), so this could be adopted honestly — but only with the
overlap rule enforced per-pair, or the far legs stop overlapping and the sheet
breaks into stripes.

### 13.3 Turn shape

The reference's turns are tight and read as almost angular. The reproduction's
`turnRadius` is floored at 0.62 because anything under 0.5 folds the ribbon's
inner edge through itself (§3). Sharper turns are only available with the slab
rendering of §13.1, which has no offset edge to fold.

### 13.4 Node count

The reference carries ~24 nodes. The reproduction generates 4 per leg (2 turn,
2 tick) plus the turn apexes — the same order, but distributed more evenly.

### 13.5 The photographic plate is drawn, not photographed

Sky, sea, sun glitter, islands, hull and wake are procedural, so the lab runs
with no asset and so the tone target is expressed as code. They are all
authored in **frame fractions**, which is why they fade out as the camera
flattens (tilt → 0): they are a picture from one camera and survey space knows
nothing about them. Only the overlay is projection-independent — and that is
precisely the property that lets it move onto a real Leaflet basemap.


---

## 14. The reference is not a single constant-width swath

This came out of trying to match the composition in 3D and it is the most
important geometric fact in the file, so it is recorded rather than worked
around.

In the reference, measure the angle below the horizon of the vessel and of the
farthest leg:

```
vessel   at fy 0.755 -> (0.755 - 0.076) * 42° = 28.5° below horizon
far leg  at fy 0.135 -> (0.135 - 0.076) * 42° =  2.5° below horizon
distance ratio = tan(28.5°) / tan(2.5°) = 12.4
```

So the far leg is **12.4x further from the camera than the vessel**. A swath of
constant width would therefore appear 12.4x narrower out there. The far legs
measure about 0.35 of frame width, so the near coverage should measure
0.35 x 12.4 = **4.2 frame widths**. It measures **0.56**.

The near wedge and the distant coverage are off by a factor of about seven.
They cannot be the same constant-width swath, which means the reference shows
**two different elements**:

- the **near wedge** is the vessel's live sonar fan — narrow, anchored to the
  hull, and the thing that says "acquiring now";
- the **distant polygons** are planned or completed coverage at the survey's
  real line spacing, which is much wider.

Reading them as one element is what forces the impossible trade the 3D build
kept running into: set the swath wide enough for the far legs to read and the
near wedge floods the frame; set it narrow enough for the near wedge and the
far legs vanish into the horizon. The current build resolves it by choosing one
constant width (150 m) that keeps the whole pattern legible, which is
self-consistent but does not reproduce the reference's framing.

The alternative — modelling the fan and the coverage as two elements with
their own widths — matches the reference and is arguably the more honest
product model as well, since a live sonar fan and a coverage plan really are
different things with different meanings. It is a product decision, not a
rendering one.
