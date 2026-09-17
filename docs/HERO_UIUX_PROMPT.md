# GhostNet-AI — UI/UX brief for a specialist design AI

**What this file is.** A single, self-contained prompt to hand to a specialist
UI/UX or creative-development AI so it can design the full GhostNet-AI public
site around the cinematic 3D hero we have already prototyped.

**How to use it.** Paste everything below the rule. It assumes no prior
context. Attach the four reference assets named in §2 if the tool accepts
images — the brief still works without them, because §2 describes what they
contain.

**Provenance of the numbers.** Every measurement in §5–§7 is read out of the
working prototype (`ghostnet-landing-atlantic-fullbleed.html`), not estimated.
Treat them as constraints that are known to work, not suggestions.

---

## 0. Your role

You are designing the public marketing site and console shell for
**GhostNet-AI**, a side-scan-sonar system that finds abandoned fishing gear
("ghost gear") on the seabed. A scroll-driven 3D hero already exists and works;
your job is to design the *rest of the experience around it* and to specify the
visual and interaction detail at a level a front-end engineer can build from.

Deliver design, not code, unless asked otherwise. Where you make a judgement
call, state the reasoning in one line so it can be argued with.

This is a hackathon deliverable with a hard public deadline of **18 September
2026**. Favour decisions that can be built and polished in days, not weeks.
Ambition in the hero; restraint everywhere else.

---

## 1. What the product actually is (do not embellish this)

GhostNet-AI reads **side-scan sonar waterfall imagery** and flags abandoned
fishing gear. Three things make it different, and the whole site should argue
these three points and no others:

1. **Polygons, not pins.** It predicts the *extent* of the gear, not just its
   presence. Across 73 image chips the model claims **7.0%** of the frame where
   a naive bounding box claims **56.5%**. That is the difference between giving
   a boat crew a search area and giving them a shrug.
2. **Calibrated confidence, not a raw score.** A raw softmax number is not a
   probability. Scores are calibrated so 0.9 means roughly nine times in ten.
   The application and the model deliberately speak two different score scales
   so neither can silently drift into the other.
3. **`review_only` by default.** Nothing is presented as a confirmed find.
   Every detection carries an honest position error and stays flagged for human
   sign-off. A false positive costs a vessel a day; a false negative costs the
   seabed a decade.

**Real figures you may use.** Do not invent others, and do not round these into
something more flattering:

| Figure | Meaning |
| --- | --- |
| `0.91` | calibrated confidence on the showcase detection — not a raw score |
| `± 24 m` | median position error |
| `± 31 m` | position error on the showcase detection |
| `7.0 %` | median frame area claimed per chip (vs 56.5% for a naive box) |
| `425` | polygons in the D2 dataset |
| `73` | annotated chips in D2 |
| `0.000 → 0.525` | net recall, posed as detection vs posed as segmentation |
| `62` | the total number of *real* net images that exist in our data |
| `5 / 5` | problem-statement classes covered by the taxonomy |
| `2.0 m/s` | survey speed (~4 knots) |
| `0 – 120 m` | across-track range of the sonar swath |

**Honesty is a design feature here, not a disclaimer.** The `62 images` figure
is a real ceiling and we publish it deliberately — synthetic volume was tested
and disproved. Give it the same typographic weight as the good numbers. A site
that hides its limitation reads as marketing; one that states it reads as
instrumentation.

**One sentence about prior art, to be reproduced exactly in wording:**

> We independently reproduced the central finding of the current state of the
> art — the Microsoft AI for Good Lab and WWF Germany work of September 2025 —
> on different water, and we are in active correspondence with its authors.

Never phrase this as "in collaboration with Microsoft", "partnered with WWF",
or anything implying endorsement. It is interest and a meeting request.

---

## 2. Reference language

Four references define the target. Match their *feeling*, not their content.

**A. Underwater light plate** (sunlit shallow sea, seen from below).
Take from it: **god rays** falling from the surface in soft converging shafts,
brightest just under the waterline and absorbed to nothing with depth; a
**sharp cellular caustic web** on the sand — crisp and net-like, never soft
blobs; **bubble columns** rising in a few thin streams; **out-of-focus
particulate**; a strong **vignette** with the light column bright in the
centre.

**B & C. Open-sea surface plates** (horizon, choppy water, sun).
Take from them: a **broad path of high-frequency sun glitter** running back
toward the sun with calmer water either side — never a uniform specular sheen,
which is what makes CG water look like plastic; **multi-scale chop** with dark
troughs and bright crests; a **crisp horizon** with atmospheric haze above it.

**D. Blue Marine Foundation, "Journey to a Healthy Ocean"** (screen capture of
a scroll-driven site). This is the genre target: *immersive 3D web experience /
cinematic 3D hero animation*. Take from it:

- **Type that lives inside the scene**, occluded by geometry as the camera
  moves past, rather than a flat overlay pinned on top.
- **Persistent instrument chrome** in a corner — it uses a location + depth +
  temperature readout that never leaves. It makes the whole page feel like a
  vehicle rather than a document.
- A **progress rail** down one side marking sections as a descent.
- **Slow, confident pacing.** Nothing hurries. Long holds on single images.
- **Deep, desaturated blue** throughout with heavy volumetric fog.
- An **audio toggle** treated as a first-class control.

**What NOT to take from D:** its editorial, charity-campaign voice. GhostNet-AI
is an instrument, not a campaign. Where Blue Marine is lyrical, we are precise.

---

## 3. Brand system — fixed, do not redesign

This is settled. Work within it.

**Four colours. Everything else must be alpha-layered from these — no fifth
hue may be introduced.**

| Token | Hex | Role |
| --- | --- | --- |
| `atlantic` | `#0F4B70` | deep panels, sidebar, sonar water |
| `sky` | `#C4F8FF` | tint surfaces on paper; bright ink on blue |
| `imperial` | `#021F94` | the one loud accent — `ghost_net`, primary buttons, active nav |
| `paper` | `#F5F2F3` | canvas, and all text sitting on blue |

Useful derived values already in use: `ink rgba(2,31,148,.92)`,
`ink-2 rgba(15,75,112,.80)`, `ink-3 rgba(15,75,112,.55)`,
`rule rgba(15,75,112,.20)`, `onblue rgba(245,242,243,.74)`,
`blue-rule rgba(196,248,255,.22)`.

**Critical contrast rule.** `imperial` is the accent **on paper only**. Over
water or any dark scrim it reads as a hole punched in the image — the emphasis
role must pass to `sky` for the duration of the dark treatment. This has
already bitten us once.

**Type.**
- Display: **Monigue** (fallbacks: Glinken, Big Shoulders Display, Oswald) —
  heavy, condensed, uppercase, very tight leading.
- UI: **Epoch** (fallbacks: Jost, Archivo) — light weights for body copy.
- Data: **IBM Plex Mono** — all numbers, readouts, labels, eyebrows.

**Typographic warning from the build:** display leading below about `0.88`
makes the lines physically collide in these faces. `0.8` looks right in a
specimen and breaks in a browser. Set it at `0.88`–`0.92` and verify in a real
render, not a mockup.

**Texture.** A fine SVG-turbulence grain multiplies over every surface at low
opacity (~0.14). It is what stops the flat colour fields looking like a
template. Keep it.

---

## 4. Site structure to design

The hero exists. Design everything else, and design how each piece hands over
to the next.

1. **Hero** — the 3D sequence (§5). Spec the type, chrome and overlay only.
2. **What comes out** — the three arguments from §1 as a card row on paper.
3. **How it decides** — a five-stage pipeline: Ingest → Chip → Segment →
   Calibrate → Review. Deep `atlantic` band. Each stage auditable on its own.
4. **Where it stands** — the evidence section: the prior-art sentence, the
   `0.525` recall result, the `62 images` honesty figure, the `5/5` coverage.
5. **Console shell** — the working application: a survey map, a detections
   list, and a review queue. Design the frame and one representative screen.
6. **Detection detail** — one ghost-gear contact: the sonar waterfall chip, the
   predicted polygon overlaid, the calibrated score, the position error, and the
   `review_only` gate with accept / reject / escalate.
7. **Footer** — three deliverable links: live demo, public repository,
   technical PDF.

**Also design, because they carry the Blue Marine feeling:**
- The **persistent instrument chrome** (§2D) and what it reads on each section.
- The **section progress rail** as a depth descent.
- The **nav's transition** from transparent-over-water to solid-on-paper.
- A **reduced-motion and mobile fallback** for the hero (§8).

---

## 5. The hero sequence — existing, working, do not redesign the mechanics

**What physically happens, in one paragraph.** A survey vessel sits on the open
sea, under way. As the visitor scrolls, a winch on its stern A-frame **lowers a
side-scan sonar towfish on a tow cable**. The fish descends and trails further
and further astern as it goes, the camera following it down through the water
column and under the surface. At working depth the fish levels out, its sonar
comes alive, and a twin swath opens beneath it and begins painting the seabed.
The scroll ends held on a contact: a ghost net lying on the bottom, lit by the
swath, tagged `review_only`.

That descent is the spine of the whole piece. Everything else — the water, the
type, the chrome — exists to make those 34 metres legible.

Scroll-driven, fully scrubbable in both directions. Everything in the scene is
a pure function of one number: scroll progress `p`, 0 to 1.

**Container.** A `270vh` track with a `100vh` sticky pane inside it, so the
sequence consumes `170vh` of scrolling and finishes at roughly **47% of the
document** — the hero occupies the first half, the argument the second.

**Four stages.** Progress boundaries and their on-screen labels:

| `p` | Stage | Label | Sub-caption |
| --- | --- | --- | --- |
| `0 – 0.16` | idle | **UNDER WAY** | 28 m survey vessel · towfish stowed in the A-frame |
| `0.16 – 0.50` | deploy | **PAYING OUT** | winch paying out · fish trimming nose-down |
| `0.50 – 0.76` | search | **ENSONIFYING** | swath open · 120 m across-track · waterfall painting |
| `0.76 – 1.0` | contact | **CONTACT** | ghost_net · 0.91 calibrated · review_only — awaiting sign-off |

The descent gets the largest share deliberately: a winch under load is slow,
and rushing it is the tell.

**The scene is in metres.** Vessel 28 m; towfish 1.3 m drawn at ×2.6 (a
declared legibility exaggeration — at true scale it is illegible next to the
ship); working depth 34 m; seabed at −52 m; survey speed 2.0 m/s. Both are real
modelled assets, not primitives, and the bow and the fish's nose both point the
same way so the rig reads as one machine.

**The three details that make the descent believable.** These are worth more
than any amount of shader polish, because anyone who has run a survey will
notice their absence:

- **Depth and layback are coupled, never independent.** The cable is a fixed
  length paying out, so the deeper the fish goes the further astern it trails.
  A fish that sinks straight down below the transom is wrong. At full deployment
  it sits 34 m down and 46 m behind the tow point.
- **The cable is a catenary, and its sag changes.** Loose and deeply curved
  early in the deployment when there is slack in the water; pulled near-straight
  once the fish is flying at depth and speed. A straight line between two moving
  points reads as a rigid rod and kills the illusion instantly.
- **The fish flies nose-down while descending and levels out at depth.** It is
  trimmed bow-down by its own weight against the cable through the descent, then
  flies level once it is down, heaving gently. A body that stays level all the
  way down is an object falling, not a towed instrument.

**The swath is a bowtie, not a cone.** Side-scan sonar is narrow along-track and
wide across it, and there is a **dead gap directly beneath the fish** — the
nadir — because the transducers fire out of the flanks, not downward. Two fans,
left and right, with nothing between them. A single cone pointing at the seabed
is the most common way this gets drawn and it is immediately wrong to anyone in
the field. Energy is brightest at the transducer and falls away hard with range.

**Composition — this is the part to hold onto.** Two copy blocks pinned to
opposite ends of the frame with the horizon and the ship in the gap between
them. Headline and eyebrow above; paragraph, CTAs and stat rule below. As the
winch starts, the two blocks clear out **in opposite directions** — headline
up, foot down — so the frame *opens* rather than merely dimming, and the
instrument overlay takes the space they vacate.

Stacking all copy from the top instead puts the paragraph across the
superstructure. That was tried and it fails.

**Camera.** It anchors to the *subject*, never to hand-typed world points:
while paying out, the anchor is the **midpoint of the cable**, so ship, cable
and fish stay in one frame — a descending fish with the ship cropped away is
just an object falling. Once the fish is down, the anchor slides onto it,
biased down by half its altitude so the frame straddles fish and seabed.

**HUD.** A top marquee (`GN-0412 · ping 18 402 · ghost_net 0.91 · ± 31 m ·
review_only`), a right-hand readout (depth / layback / speed, live), and the
bottom-left stage label. The ping counter increments only while ensonifying.

---

## 6. Water and light — the specification to design against

A four-band water column, light at the surface to near-black in the deep:

| Depth | Colour | Character |
| --- | --- | --- |
| `0 to −14 m` | `rgb(0.380, 0.600, 0.712)` | sunlit; sky over atlantic |
| `−14 to −30 m` | `rgb(0.059, 0.294, 0.439)` | atlantic; the working band |
| `−30 to −44 m` | `rgb(0.027, 0.166, 0.408)` | atlantic into imperial |
| `below −44 m` | `rgb(0.004, 0.054, 0.261)` | imperial, dark |

**The bands must overlap heavily — about 13 m of blend each.** They are stops
on one continuous ramp, not four layers. Anything tighter and they render as
flat-shaded slabs with visible seams, which reads as a low-poly render rather
than water. This was the single most-reported problem during the build.

The atmospheric haze the camera sits in must be sampled from this same ramp at
the camera's own depth, every frame. If the haze and the water are computed
separately they drift apart and the scene reads as two unrelated blues.

**Effects, in priority order:**

1. **God rays** — soft converging shafts from just under the surface, reaching
   ~96 m down, brightest at the top, fully absorbed by working depth. Fade
   their horizontal extent or their own edges show as a straight cut.
2. **Caustics** across the *entire* seabed, not a patch. Cellular and crisp.
3. **Sun glitter** on the surface from above, as a path, fading to nothing as
   the camera submerges — there is nothing to reflect from underneath.
4. **Marine snow** — suspended particulate drifting astern at survey speed.
5. **Bubble columns** — three thin streams, slow.
6. **Vignette** — dark at the edges, bright in the light column.
7. **A hard horizon** where sea meets sky, dissolving the instant the camera
   goes under.

**Seabed.** Gentle relief, never a flat plane. Scattered debris: a **ghost net**
as a wireframe mesh draped over a low mound with floats still attached, a lost
trap, boulders, a drum, a tyre. The net is the payload of the whole sequence —
give it the light.

---

## 7. Hard-won rules — every one of these failed in the build first

Treat this section as the most valuable part of the brief. These are not
theory; each one shipped as a visible defect before it was fixed.

1. **The sonar swath must be painted directly beneath the towfish.** It was
   once drawn 30 m to one side. The single relationship the whole piece exists
   to show was broken and nobody could say why the scene felt wrong.
2. **Declare each contact once.** The bright sonar return and the physical
   object on the seabed must come from the same coordinate, or you get a sonar
   contact with nothing underneath it.
3. **Forward motion is sold by near-field parallax, never by a fast seabed.**
   At an honest 2 m/s nothing in the far field visibly moves. Speeding the
   seabed up to compensate is exactly what reads as a treadmill — the eye
   compares near and far motion and knows they disagree. Particles close to the
   lens do the work, as in real ROV footage.
4. **A ship on water with no horizon reads as sunk, not floating.** Do not tilt
   the camera down far enough to lose the horizon in order to make room for
   copy. Solve that in the layout instead.
5. **Lighting must never end on a straight line.** Any light that stops at the
   edge of the surface carrying it destroys the illusion instantly. Feather
   every boundary.
6. **Everything distant must haze, including the effects.** Light added after
   the fog is applied comes back at full strength 700 m away and draws a hard
   line across the frame.
7. **Sharper is not the same as more contrast.** Pushing the caustic falloff
   too far erases the web entirely and flattens the floor.
8. **Detail size is relative to the camera, not the world.** Sun-glitter cells
   of 0.6 m project to ~13 px blocks and read as confetti; ~11 cm reads as
   grain; smaller still goes sub-pixel and aliases into shimmer.
9. **Transparency that is physically defensible can still be perceptually
   wrong.** A surface transparent enough to read the ship's keel through makes
   it look parked on glass.
10. **Attitude and position should be functions of scroll, not of the clock**,
    or the scene stops scrubbing backwards correctly and desynchronises on
    pause.

---

## 8. Constraints

**Responsive.** Below ~1000 px the scene becomes a dimmed full-bleed backdrop
behind the copy rather than a column, with a scrim heavy enough to carry paper
text. Instrument chrome hides. No horizontal overflow at 400 px. Design this
state explicitly — do not leave it as "it scales".

**Reduced motion and low-power.** Specify a poster-frame fallback — a still at
roughly the contact stage. Never a blank hero.

**Performance.** Target 60 fps on integrated graphics. Prefer one billboarded
volume over many meshes; prefer a CSS gradient over a post-processing pass when
the result is identical.

**Accessibility.** The scroll sequence must not be the only route to any
information: everything the hero says must also appear in the sections below.
Check contrast for paper-on-water in both the light and dark bands, and keep
focus states visible against the scene.

---

## 9. What to deliver

1. A full-page design for each section in §4, desktop and mobile.
2. The hero's four stages as key frames, with the type and chrome positioned
   over real scene imagery — not over a flat colour placeholder.
3. A spec for the persistent instrument chrome and the section progress rail.
4. A short motion document: what moves, over what scroll range, with what
   easing, and what it hands over to.
5. The colour and type tokens applied as a usable system, including the
   paper-versus-over-water accent switch in §3.
6. A list of anything in §7 you think is wrong, with your reasoning. These rules
   were learned from one project; they are not laws.
