# Stitch section prompts

Per-section prompts for generating GhostNet-AI screens through the Stitch MCP
server. One prompt per section of `HERO_UIUX_PROMPT.md` §4.

**Why these are pre-written.** The Stitch free tier gives roughly 400 design
credits a day but only **15 redesigns**. Generation is cheap; iteration is the
scarce resource. It is far cheaper to spend the tokens getting a prompt right
before sending it than to burn revision cycles discovering the brand rules one
at a time.

**Each prompt is self-contained** — Stitch generates one screen at a time with
no memory of the previous prompt, so the brand rules are restated in every one.
That repetition is deliberate; do not factor it out.

**Rules baked into every prompt below** — do not drop them when editing:

- Only four colours: `#0F4B70` atlantic, `#C4F8FF` sky, `#021F94` imperial,
  `#F5F2F3` paper. Everything else alpha-layered from those.
- `imperial` is the accent **on paper only**. Over any dark surface the accent
  role passes to `sky`.
- Display type heavy/condensed/uppercase with leading no tighter than `0.88`.
  Body type light. All numbers and labels in monospace.
- Never invent statistics. Use only the figures given.

**Order to generate in.** §4.2 first as the test. If its output is usable, run
§4.3, §4.4 and §4.7 as a batch — they are the same kind of problem. Leave §4.5
and §4.6 until last; they are application UI rather than marketing sections and
are the two most likely to need a redesign cycle.

---

## §4.2 — "What comes out" (first test generation)

> Design a full-width landing-page section for **GhostNet-AI**, a side-scan
> sonar system that detects abandoned fishing gear on the seabed.
>
> **Section:** a light "paper" section on background `#F5F2F3`, sitting between
> a dark cinematic 3D hero above it and a deep blue section below it.
>
> **Structure, top to bottom:**
> 1. A monospace eyebrow label, uppercase, wide letter-spacing, muted:
>    `01 — WHAT COMES OUT`
> 2. A very large condensed uppercase headline in `#021F94`:
>    `A polygon, a number, and a caveat`
> 3. A single paragraph of light-weight body copy, max ~620px wide:
>    "A pin on a map tells a boat crew nothing about how much water to sweep.
>    Everything GhostNet-AI emits is shaped so the next person in the chain can
>    act on it — or refuse it."
> 4. A row of **three equal cards**, separated by hairline rules rather than
>    gaps or shadows — the cards should read as cells in a technical table, not
>    as floating panels. Each card has a small monospace category label, a
>    condensed uppercase title, and a short paragraph.
>
> **Card 1** — label `GEOMETRY`, title `Polygons, not pins`:
> "D2 predicts the extent of the gear, not just its presence. Across 73 chips
> the model claims 7.0% of the frame instead of the 56.5% a naive box would —
> the difference between a search area and a shrug."
>
> **Card 2** — label `CONFIDENCE`, title `Calibrated, not raw`:
> "A raw softmax score is not a probability. Scores are calibrated so 0.9 means
> roughly nine in ten — and the app and the model deliberately speak two
> different score scales so neither can silently drift into the other."
>
> **Card 3** — label `ACCOUNTABILITY`, title `review_only by default`:
> "Nothing is presented as a confirmed find. Every detection carries an honest
> position error and stays flagged for human sign-off, because a false positive
> costs a vessel a day and a false negative costs the seabed a decade."
>
> **Visual language.** Precise and instrumental, like a survey readout — not a
> friendly SaaS marketing page. No rounded cards, no drop shadows, no
> gradients, no icons, no stock imagery. Hairline rules, hard edges, generous
> white space, a strong typographic hierarchy carrying all the emphasis. A very
> faint grain texture over the whole surface.
>
> **Palette.** Background `#F5F2F3`. Headline and card titles `#021F94`. Body
> copy a muted desaturated blue. Rules and hairlines a low-opacity blue.
> Optional single tint surface in `#C4F8FF`. Use no other colours.
>
> **Type.** Display: a heavy condensed uppercase grotesque (Big Shoulders
> Display). Body: a light geometric sans (Jost). Labels and numbers: IBM Plex
> Mono.
>
> Deliver desktop and a 400px mobile layout.

---

## §4.3 — "How it decides" (the pipeline)

> Design a full-width landing-page section for **GhostNet-AI**, a side-scan
> sonar system that detects abandoned fishing gear on the seabed.
>
> **Section:** a deep blue band on background `#0F4B70`, with a thick `14px`
> top border in `#021F94` acting as a hard rule where the light section above
> it ends. All text on this section is off-white `#F5F2F3` or pale cyan
> `#C4F8FF`. This is the darkest, most technical moment on the page.
>
> **Structure, top to bottom:**
> 1. Monospace eyebrow, uppercase, wide letter-spacing, low-opacity off-white:
>    `02 — HOW IT DECIDES`
> 2. A very large condensed uppercase headline in pale cyan `#C4F8FF`:
>    `Sonar in, geometry out`
> 3. One paragraph of light body copy, max ~620px:
>    "Five stages, each auditable on its own. The transform rule is absolute:
>    anything applied in training is applied at inference, or it is applied in
>    neither."
> 4. A row of **five equal stages**, divided by hairline vertical rules in
>    low-opacity cyan — one continuous instrument strip, not five separate
>    cards. Each stage has a small monospace step number, a condensed uppercase
>    title in pale cyan, and two lines of body copy.
>
> `STAGE 01` / **Ingest** — "Raw side-scan waterfall, despeckled and reduced to
> 8-bit, across-track 0–120 m."
>
> `STAGE 02` / **Chip** — "The track is cut into overlapping chips so gear
> straddling a boundary is never lost to it."
>
> `STAGE 03` / **Segment** — "The D2 model returns per-pixel extent, taking net
> recall from 0.000 to 0.525 as polygons."
>
> `STAGE 04` / **Calibrate** — "Scores are mapped to real probabilities and a
> position error is attached to each."
>
> `STAGE 05` / **Review** — "Everything lands in the console as review_only
> until a human signs it off."
>
> **Make the sequence readable as a flow** using only rules, numbering and
> alignment — no arrows, no chevrons, no connector graphics, no icons.
>
> **Visual language.** Instrumental and technical, like a control panel legend.
> No rounded corners, no drop shadows, no gradients, no illustrations. Hairline
> rules and hard edges. A faint grain texture over the surface.
>
> **Palette.** Background `#0F4B70`, top border `#021F94`, headings and stage
> titles `#C4F8FF`, body copy off-white at ~74% opacity, rules pale cyan at
> ~22% opacity. Use no other colours. Do not use `#021F94` for any text on this
> section — it is unreadable against the blue background.
>
> **Type.** Display: a heavy condensed uppercase grotesque (Big Shoulders
> Display), leading no tighter than 0.9. Body: a light geometric sans (Jost).
> Step labels: IBM Plex Mono, uppercase, wide letter-spacing.
>
> Deliver desktop and a 400px mobile layout. On mobile the five stages stack
> vertically, still divided by hairline rules.

---

## §4.4 — "Where it stands" (evidence)

> Design a full-width landing-page section for **GhostNet-AI**, a side-scan
> sonar system that detects abandoned fishing gear on the seabed. This section
> presents evidence and is the most serious moment on the page — it must read
> like a results table, not a testimonial block.
>
> **Section:** light, on background `#F5F2F3`.
>
> **Structure, top to bottom:**
> 1. Monospace eyebrow: `03 — WHERE IT STANDS`
> 2. Very large condensed uppercase headline in `#021F94`:
>    `Measured against the state of the art`
> 3. A **pull quote**, set off by a thick 3px left rule in `#021F94`, max ~760px
>    wide, in a larger light weight — not italic, not in quotation marks:
>    "We independently reproduced the central finding of the current state of
>    the art — the Microsoft AI for Good Lab and WWF Germany work of September
>    2025 — on different water, and we are in active correspondence with its
>    authors."
>    Beneath it, a small monospace attribution line:
>    `EVIDENCE: DOCS/D2_SEGMENTATION_SUMMARY.MD`
> 4. A row of **three equal cards** divided by hairline rules. Each card leads
>    with a large figure as its heading rather than a phrase.
>
> **Card 1** — label `SEGMENTATION`, figure `0.525`:
> "Net recall as polygons, up from 0.000 when the same data was posed as a
> detection problem. The task framing was the finding, not the model size."
>
> **Card 2** — label `HONESTY`, figure `62 images`:
> "The real-data ceiling we actually have. Synthetic volume was tested and
> disproved; we report the constraint rather than hiding it behind a synthetic
> score."
>
> **Card 3** — label `COVERAGE`, figure `5 / 5`:
> "All five problem-statement classes are covered by the taxonomy, with
> ghost_net the one that carries a segmentation head and a review gate."
>
> **Critical.** The middle card states a limitation, not an achievement. Give
> it exactly the same visual weight as the other two — do not de-emphasise it,
> do not tint it differently, do not mark it as a caveat. The point of the
> section is that the limitation is published as plainly as the result.
>
> **Visual language.** A results table, not marketing. No logos, no badges, no
> award ribbons, no icons, no portraits, no rounded cards, no shadows. Hairline
> rules and hard edges.
>
> **Palette.** Background `#F5F2F3`, headline and figures `#021F94`, body copy
> a muted desaturated blue, rules low-opacity blue. Use no other colours.
>
> **Type.** Display: heavy condensed uppercase grotesque (Big Shoulders
> Display). The three figures are display type, large. Body: light geometric
> sans (Jost). Labels: IBM Plex Mono.
>
> Deliver desktop and a 400px mobile layout.

---

## §4.5 — Console shell (application UI)

> Design the main screen of a **working web application** called GhostNet-AI —
> a survey console for finding abandoned fishing gear ("ghost gear") on the
> seabed from side-scan sonar. This is an operator tool used on a vessel or in
> an operations room, not a marketing page. It should look like instrumentation
> that someone trusts with a day of ship time.
>
> **Layout: a fixed two-column application shell.**
>
> **Left sidebar**, ~264px, deep blue `#0F4B70`, full height:
> - The wordmark `GhostNet-AI` at the top in heavy condensed uppercase,
>   off-white, with `NET` drawn as an outline rather than a solid.
> - Navigation grouped under small monospace section labels. Group `SURVEY`:
>   Surveys, Tracks, Imports. Group `FINDINGS`: Detections (badge `425`),
>   Review queue (badge `38`), Exports.
> - Each nav row is a plain text label with a small square outline glyph and an
>   optional right-aligned monospace count. The active row is marked by a solid
>   3px left border in pale cyan `#C4F8FF` and a darker `#021F94` background
>   fill — not a pill, not a rounded highlight.
> - A footer block pinned to the bottom with a monospace build string:
>   `CONTRACT v1.2.0 · ALL DETECTIONS REVIEW_ONLY`
>
> **Main area**, light `#F5F2F3`, separated from the sidebar by a thick 14px
> vertical rule in `#021F94`:
> - A top bar with the survey name `GN-0412`, a monospace status strip
>   (`2.0 M/S · 0–120 M ACROSS-TRACK · 18 402 PINGS`), and two buttons: a solid
>   `#021F94` primary `Run detection` and an outline secondary `Export GeoJSON`.
> - Below it, a **split working area**: a large map panel on the left (~62%)
>   and a detections list on the right (~38%), divided by a hairline rule.
> - **Map panel:** a dark `#0F4B70` chart surface showing a survey track line as
>   a dashed pale cyan path, with a handful of irregular detection **polygons**
>   outlined in pale cyan and filled with a fine cross-hatch pattern. Polygons,
>   never pins or map markers — this is the product's whole argument. A small
>   scale bar and a north arrow in monospace.
> - **Detections list:** a dense table, one row per detection, hairline rules
>   between rows, no zebra striping. Columns: ID, class, calibrated score,
>   position error, status. Example rows:
>   `GN-0412-018 · ghost_net · 0.91 · ± 31 m · REVIEW_ONLY`
>   `GN-0412-021 · ghost_net · 0.74 · ± 44 m · REVIEW_ONLY`
>   `GN-0412-009 · trap · 0.68 · ± 52 m · REVIEW_ONLY`
>   `GN-0412-004 · debris · 0.55 · ± 61 m · REJECTED`
>   The `REVIEW_ONLY` status is set in monospace in `#021F94`; `REJECTED` is
>   muted. Scores are monospace and right-aligned so decimal points line up.
>
> **Visual language.** Dense, flat, technical. No rounded corners, no drop
> shadows, no gradients, no coloured status pills, no icon set, no avatars, no
> illustrations. Hairline rules do all the dividing. Whitespace is tight —
> this is a screen for reading many rows, not a landing page.
>
> **Palette.** Sidebar and map `#0F4B70`; main background `#F5F2F3`; primary
> action and active state `#021F94`; highlights and data on blue `#C4F8FF`;
> text on blue off-white `#F5F2F3`. Use no other colours — in particular do not
> introduce red/amber/green status colours; status is carried by the word and
> by monospace weight alone.
>
> **Type.** Display: heavy condensed uppercase grotesque (Big Shoulders
> Display) for the wordmark and panel headings. UI: light geometric sans
> (Jost). All data, IDs, scores, counts and labels: IBM Plex Mono.
>
> Deliver desktop at 1600px. Also deliver a 400px mobile layout in which the
> sidebar collapses to a top bar and the map and list stack vertically.

---

## §4.6 — Detection detail (the review gate)

> Design a detail screen in a web application called **GhostNet-AI**, a survey
> console that finds abandoned fishing gear on the seabed from side-scan sonar.
> This screen shows one detection and is where a human accepts or rejects it.
> It is the most consequential screen in the product: accepting a false
> positive costs a vessel a day at sea.
>
> **Layout: a two-column detail view** on a light `#F5F2F3` background, inside
> the same application shell as the console (deep blue `#0F4B70` sidebar to the
> left, thick 14px `#021F94` divider).
>
> **Header strip**, full width above both columns:
> - Detection ID in heavy condensed uppercase: `GN-0412-018`
> - A monospace metadata line:
>   `SURVEY GN-0412 · PING 18 402 · CAPTURED 2026-09-11 04:18 UTC`
> - On the right, a prominent status marker reading `REVIEW_ONLY` set in
>   monospace, uppercase, in `#021F94`, inside a hairline-ruled box. Not a
>   rounded pill, not a coloured badge.
>
> **Left column (~58%) — the evidence:**
> - A large **side-scan sonar waterfall chip**: a tall, narrow, grainy
>   greyscale-into-blue image with strong horizontal streaking along the track,
>   a darker vertical band down the centre (the nadir gap directly beneath the
>   sonar), and one bright irregular object left of centre casting a long dark
>   **acoustic shadow** away from the centre line.
> - Overlaid on it, the model's predicted **polygon**: an irregular closed
>   outline in pale cyan `#C4F8FF`, 2px, tightly following the bright object,
>   with a fine cross-hatch fill at low opacity. Beside the polygon a small
>   monospace callout: `ghost_net · 0.91 · ± 31 m`.
> - Below the image, a monospace caption:
>   `DESPECKLED · 8-BIT · ACROSS-TRACK 0–120 M`
> - A small row of two toggles, plain text with hairline underline on the
>   active one: `RAW` / `DESPECKLED`, and `POLYGON ON` / `POLYGON OFF`.
>
> **Right column (~42%) — the assessment:**
> - A **definition list** of measurements, each a hairline-ruled row with a
>   monospace label on the left and a monospace value right-aligned:
>   `CLASS  ghost_net` · `CALIBRATED SCORE  0.91` · `POSITION ERROR  ± 31 m` ·
>   `AREA CLAIMED  7.0 %` · `ALTITUDE  20 m` · `MODEL  D2 · seg-v7`
> - Beneath it, a short block headed `WHAT THIS SCORE MEANS` in light body
>   copy: "0.91 is calibrated, not raw — roughly nine such calls in ten are
>   correct. It is not a probability that this specific object is a net."
> - At the bottom, the **review gate**: three actions in a row —
>   a solid `#021F94` `Accept` button, an outline `Reject` button, and a plain
>   text `Escalate` link. Above them one line of light body copy:
>   "Nothing leaves this queue until a human signs it off."
>
> **Critical.** The accept action must not feel casual or celebratory. No
> success-green, no checkmark icon, no confetti, no toast. The weight of the
> decision is carried by the plainness of the controls and by the sentence
> above them.
>
> **Visual language.** Forensic and plain, like a lab report. No rounded
> corners, no drop shadows, no gradients, no coloured status colours, no icon
> set, no illustrations. Hairline rules separate everything.
>
> **Palette.** Background `#F5F2F3`; sidebar and the sonar image `#0F4B70`;
> primary action, status text and headings `#021F94`; polygon outline and data
> highlights `#C4F8FF`. Use no other colours — in particular no red for
> Reject and no green for Accept.
>
> **Type.** Display: heavy condensed uppercase grotesque (Big Shoulders
> Display) for the detection ID and section headings. Body: light geometric
> sans (Jost). All measurements, labels and IDs: IBM Plex Mono.
>
> Deliver desktop at 1600px and a 400px mobile layout in which the two columns
> stack, evidence first and the review gate pinned to the bottom of the screen.

---

## §4.7 — Footer

> Design the footer of a landing page for **GhostNet-AI**, a side-scan sonar
> system that detects abandoned fishing gear on the seabed. It is the final
> block of the page and its job is to hand over three deliverable links.
>
> **Section:** a solid deep blue block on `#021F94`, the most saturated surface
> on the whole page. All text is off-white `#F5F2F3` or pale cyan `#C4F8FF`.
>
> **Structure, top to bottom:**
> 1. A monospace eyebrow in low-opacity off-white:
>    `SMART INDIA HACKATHON · 18 SEPTEMBER 2026`
> 2. A very large condensed uppercase headline in off-white: `Open the console`
> 3. A row of three buttons, hard-edged, no rounding:
>    - `Live demo` — solid pale cyan `#C4F8FF` with `#021F94` text
>    - `Public repository` — transparent with a hairline off-white border
>    - `Technical PDF` — transparent with a hairline off-white border
> 4. A generous gap, then a small monospace legal/status line in low-opacity
>    off-white:
>    `GHOSTNET-AI · SIH26057 · CONTRACT v1.2.0 · ALL DETECTIONS REVIEW_ONLY`
>
> **Visual language.** Confident and bare. No social icons, no newsletter
> signup, no sitemap column list, no logo grid, no illustration. The three
> links are the entire content.
>
> **Palette.** Background `#021F94`, primary button `#C4F8FF`, text `#F5F2F3`.
> Use no other colours.
>
> **Type.** Display: heavy condensed uppercase grotesque (Big Shoulders
> Display). Buttons in the same display face, uppercase. Status line: IBM Plex
> Mono.
>
> Deliver desktop and a 400px mobile layout in which the three buttons stack
> full-width.

---

## Do not send the hero to Stitch

§4.1 is a bespoke three.js scene — a scroll-driven vessel deploying a side-scan
towfish, with custom GLSL for god rays, caustics, a banded water column and a
bowtie sonar swath. Stitch returns flat screens. Pointed at the hero it will
not refine that scene, it will replace it with a static mockup of it, and every
hard-won rule in `HERO_UIUX_PROMPT.md` §7 goes with it.

The working scene lives in
`C:\Users\vandi\OneDrive\Desktop\ghostnet-landing-atlantic-fullbleed.html`.
Capture stills from it with `dev-browser run scripts/shoot_hero.js`.
