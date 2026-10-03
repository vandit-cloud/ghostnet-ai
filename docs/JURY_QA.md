# GhostNet-AI — Jury Q&A Brief

**SIH26057 · Model `gv5-yolo11s` · Compiled 19 September 2026 from the repository's own evidence documents.**

Every figure below is traced to a source file in this repo. Where two documents disagree, both are shown and the conflict is named rather than resolved — the project's own rule (`TEAM_DOC_1_PROJECT.md`, hard rule 6).

**How to use this.** Sections A–C are the questions you *want*. Sections D–G decide the round. Section H is what to do when the demo misbehaves. Section K is the one-page cheat sheet to hold in your hand.

---

## 0 · Rules of engagement (read before the round)

From `TEAM_DOC_1_PROJECT.md` §7. These are worth more than any single answer:

1. **Never quote an accuracy without its sample size.** `mAP50 0.314 (n=567)`. A bare number is a defect, and a judge who knows the field will ask "out of how many?"
2. **Never round in your favour.** 0.869 is not "about 0.9".
3. **Never call a crab pot a ghost net.** Say *derelict crab pot*, or *ghost gear*.
4. **Never say "verified-empty seabed".** Say *"tiles carrying no annotation"*.
5. **Never quote the `plane` class.** Nine test boxes. Omit it entirely.
6. **Never state a threshold without naming its scale** — "raw score 0.10" or "calibrated confidence 0.20". They are different scales, and mixing them up is how the team's own false-alarm figure stayed confused for two weeks.
7. **Never say "99% accurate", "real-time AI", or "fully automated".**
8. **Lead with the honesty — not as an apology, as the differentiator.**

> **The sentence to open and close on:** *"Plenty of teams can show you a demo that works. We can show you exactly where and why ours doesn't — measured, reproducible, and written down before you asked."*

---

## A · The problem and the pitch

**A1 · What is this project, in one sentence?**
An AI system that finds man-made debris on the seabed in side-scan sonar imagery, tells you how confident it actually is, and puts it on a map with an honest error radius instead of a fake-precise pin.

**A2 · What is a ghost net, and why does it matter?**
A fishing net lost or dumped at sea that keeps catching and killing marine life for decades with nobody hauling it in. Derelict traps are the same problem in a different shape. The economic stake is documented: Scheld, Bilkovic & Havens (2016, *Scientific Reports*) found that removing even 10% of derelict pots and traps from major crustacean fisheries could raise landings by **293,929 metric tons, worth $831 million annually**; removing 34,408 pots from Chesapeake Bay added 13,504 MT of harvest worth **$21.3 million — a 27% increase**.

**A3 · Why sonar? Why not cameras?**
Below a few metres there is no light. Optical imaging is useless at survey scale. Sound is the only sensor that images the seabed across a wide swath, which is why every serious marine survey is acoustic.

**A4 · Explain side-scan sonar in one paragraph.**
A torpedo-shaped **towfish** is dragged behind a boat. It fires sound sideways in a fan and listens for echoes; each firing — a **ping** — produces one line of pixels. Stack the lines as the boat moves forward and you get a **waterfall** image. Bright means a strong echo. Dark means either soft sediment or an **acoustic shadow** behind an object that blocked the sound. Shadows are the single most useful cue in sonar.

**A5 · Why is this hard?**
Four physical facts. (1) Sonar images are grey, grainy and full of **speckle** — multiplicative noise that looks exactly like texture. (2) A rock and a piece of wreckage can look nearly identical. (3) A net *lies flat*, so it barely shows up at all — this one fact drives our biggest failure. (4) The image is geometrically stretched; one pixel across is not the same distance as one pixel down. And one data fact shapes everything downstream: **almost no public sonar imagery of fishing nets exists.**

**A6 · Does this actually meet the problem statement?**
SIH26057 asks for detection of underwater marine debris from side-scan sonar, separating natural seafloor topology from artificial anomalies, with confidence scoring, noise handling and geotagged reporting. Against its five illustrative categories:

| PS category | Our class | Test boxes | mAP50 | Status |
|---|---|---|---|---|
| ghost nets / entangled debris | `ghost_net` | 36 | 0.009 | **Does not work** |
| (same category, partial cover) | `ghost_pot` | 567 | 0.314 | Works — real derelict gear |
| shipwrecks | `wreck` | 836 | 0.279 | Works |
| pipes | `debris` | 615 of 629 | 0.869 | Strongest class |
| cylinders | — | — | — | A pipe *is* a cylinder; no dedicated class |
| other man-made debris | `debris` | 629 | 0.869 | Works |

Four of five categories covered, three working. The PS wording is *"man-made classes **supported by the actual training data**, such as..."* — "such as" is illustrative, and that qualifier explicitly licenses covering what the data supports.

**A7 · Requirement-by-requirement, how is each met?**

| PS requirement | How |
|---|---|
| Detection from side-scan imagery | YOLO11-S detector, 5 classes, trained on real survey data |
| Separating natural from artificial | Measured false-alarm rate on unannotated seabed — not a second classifier |
| Confidence scoring | Temperature-scaled calibrated confidence; ECE 0.218 → 0.089 |
| Noise handling | Speckle characterised and stress-tested; tile-edge false detections suppressed by shape |
| Geotagged reporting | Coordinates from ping headers with slant-range correction, reported with an error radius; CSV and GeoJSON output |

**A8 · Who would actually use this?**
A survey operations team — anyone who already tows a side-scan fish and today has a human scrub the waterfall by eye. The system does not replace that person; it triages for them and keeps an audit trail of what they decided.
*Honesty caveat: we have no signed pilot partner and no deployment agreement. Do not imply one.*

**A9 · What makes you different from every other detection project here?**
Three things that are hard to fake: a **calibrated** confidence (our 0.7 means roughly 70% correct), a **published false-alarm rate** instead of a hidden one, and a **negative result we ran, wrote up, and declined to ship**. The accuracy numbers are modest and with this much public sonar data they always will be. The discipline is the contribution.

---

## B · The demo — what they are looking at

**B1 · Walk us through the system.**
Seven screens in story order: **Dashboard** (mission summary) → **Surveys** (create, upload `.xtf`, press Process) → **Processing** (live WebSocket progress, one event per stage, per frame, per detection) → **GIS Map** (vessel track from ping headers, detections as error circles, 2D/3D toggle, time replay) → **Detections / Sonar Investigation** (the real 640×640 sonar tile with the box drawn on it) → **Review Queue** (accept as artificial / reject as natural, audited) → **Reports** (CSV or JSON, stamped with `model_version`).

**B2 · What am I looking at in that sonar tile?**
A 640×640 crop of the waterfall — the exact unit the detector sees, not a visualisation. The green box is the model's output at its stored pixel coordinates. That viewer is the single render site used by the detections, review, sonar and map screens, so what you see is what the database holds.

**B3 · Why are the detections not on the vessel track?**
Because they shouldn't be. The sonar looks *sideways*; an object is not where the boat was. If the markers sat on the track line, our geometry would be wrong.

**B4 · Why circles and not pins?**
The circle is the geolocation uncertainty — **4.3 to 4.5 m on the demo survey** — derived from GPS scatter, heading error and altitude uncertainty. A pin would claim a precision we cannot support. A missing pin is recoverable; a confidently wrong pin is not.

**B5 · That was too fast. Is the model really running?**
Yes. A 640×640 tile is ~58 ms on the RTX 3050 — **17.3 frames per second**. Forty frames is ~2.3 seconds of actual inference. The ~14 seconds you see is XTF parsing (6,039 pings), waterfall assembly, tiling, database writes and WebSocket broadcast — **plus about 3.2 s of deliberate delay we insert so the stage stepper is readable.** The app is slowed down on purpose; the model is not the slow part.

Four independent proofs, if pressed:

1. **No shortcut in the code path** — processing calls `adapter.analyze_frame()` → `ghostnet.detect()` per frame. No lookup table, no cached result, no fixture branch.
2. **Standalone inference reproduces the stored output exactly** — running `detect_survey()` outside the app on the demo file returns 2 detections at boxes `[0,151,129,62]` and `[285,63,141,47]`, raw 0.112 / 0.197 — identical, box for box, to the rows in the database.
3. **Different files give different answers** — the four demo fixtures produce 6, 7, 4 and 13 detections. Canned data does not vary by input.
4. **Timestamps show a live loop** — detection rows are written seconds apart, ascending, clustered around each run, not bulk-inserted with one timestamp.

**One-sentence version:** *"Upload any of these four files yourself and watch the count change — nothing is cached. The whole survey is 2.3 seconds of real inference; the rest of the wait is us drawing a progress bar slowly enough to read."*

**B6 · Is the demo data pre-seeded?**
The **surveys** can be seeded by `scripts/showcase_seed.py` — it creates surveys and uploads files. It **cannot insert a detection**; it drives the app's own public API and then presses Process. Every box you see was produced by the model at processing time. Say this before they ask.

**B7 · Where does the demo data come from?**
`demo/NBP0505_line01B_demo.xtf` is real 2005 side-scan data from the RV *Nathaniel B. Palmer* research cruise, Golfo de Penas, Chile — 40 frames, 2 detections. Four per-class fixture files (wrecks, aircraft, debris, ghost gear) are built from curated real frames with a **synthetic navigation track**, which is documented as such — say so if the coordinates are questioned.

**B8 · Can I upload my own file right now?**
Yes — and that is the strongest thing you can offer. Any `.xtf` side-scan file. Plain images work too, but they can never be geolocated (no ping headers, no geometry) and the system will say so rather than estimate.

**B9 · Why does pressing Process twice give an error?**
`409 ALREADY_PROCESSED`, deliberately. A second run would append a duplicate copy of every detection and discard existing review decisions. `force_restart: true` overrides it intentionally.

**B10 · Who is recorded as the reviewer?**
Identity is read from the JWT access token, never from the request body. A review decision cannot be attributed to someone who did not make it.

**B11 · What happens in 3D if the map looks empty?**
Press **"Fit Survey"**. The default camera does not frame the survey on entry. Known, minor, and worth rehearsing so you never fumble it live.

---

## C · The AI, when it is going well

**C1 · What model, and why that one?**
**YOLO11-S** via Ultralytics, transfer-learned from COCO-pretrained weights, 640×640 tiles, five classes. "S" is not a preference — it is a **4 GB VRAM ceiling** on an RTX 3050 Laptop GPU, which also fixes batch size at 4. Data was the limiting factor, not model capacity, so a bigger backbone would have bought nothing.

**C2 · How much data, from where?**
**18,310 images from 8 public sources**, no proprietary data: AI4Shipwrecks (6,976 — Lake Huron wrecks), GhostVision (6,655 — Delaware Bay crab pots), China-Offshore-SSS-AI (2,072 — hard negatives, and the origin of our 73 net chips), SubPipe (2,049 — pipeline survey), SCTD (327), Marine PULSE (88, background only), sonar_detect (70), plus two sets we annotated ourselves: GHOSTNET-HAND (73 images, 298 boxes) and PLANE-HAND (60, pinned train-only).

**C3 · How do you know you aren't leaking test data into training?**
Splits are by **group, never by file**. Exact duplicates dropped; near-duplicates and all tiles from one waterfall kept together — otherwise a tile in training and its neighbour in test would leak the answer. The test split is held **byte-identical from gv5 onward** so successive runs compare directly. We also caught a real instance: all 60 PLANE-HAND images turned out to be a subset of an unused Roboflow set that splits them across train/valid/test — verified by perceptual hash. Importing it naively would have raised the plane score for the wrong reason.

**C4 · What does the model actually score?**
On 4,346 held-out frames:

| Class | Test boxes | Precision | Recall | mAP50 |
|---|---|---|---|---|
| `debris` | 629 | 0.798 | 0.855 | **0.869** |
| `ghost_pot` | 567 | 0.377 | 0.295 | 0.314 |
| `wreck` | 836 | 0.423 | 0.315 | 0.279 |
| `ghost_net` | 36 | 1.000 | **0.000** | 0.009 |
| overall | | 0.580 | 0.361 | 0.352 |

(`plane`, n=9, omitted on purpose.)

**C5 · Is it improving, or did you get lucky once?**
Trajectory on the same frozen split:

| run | mAP50 | precision | recall |
|---|---|---|---|
| gv | 0.160 | 0.140 | 0.285 |
| gv2 | 0.132 | 0.451 | 0.178 |
| gv4 | 0.247 | 0.191 | 0.362 |
| **gv5** | **0.352** | **0.580** | 0.361 |

Six full training generations. Every run writes `test_metrics.json`; gv5's is in `ai/experiments/gv5-yolo11s/`.

**C6 · What is calibrated confidence, and why does it matter?**
A raw detector score is not a probability; YOLO scores are systematically overconfident. We fit **temperature scaling** (T = 2.722031) on the validation split over 1,604 predictions. **Expected calibration error fell from 0.2178 to 0.0891.** When the model says 0.7, it is right about 70% of the time. Raw scores are never shown to a user — they exist in the contract as a diagnostic only.

**C7 · What is your false-alarm rate?**
**7.82%** — on 2,930 held-out tiles *carrying no annotation*, at the deployed raw gate of 0.10. Always say it with the caveat: *"roughly half those tiles come from survey lines the source dataset left entirely unannotated, so it is an upper bound."* The negatives are deliberately hard — 2,072 China-Offshore frames of gully fields, riprap, scour patches and sand waves, the natural features most easily mistaken for man-made objects.

**C8 · Can you trade recall against false alarms?**
Yes, and the curve is published (`derive_review_floor.py`), measured on the **calibrated** scale:

| calibrated floor | recall | recall retained | false alarms |
|---|---|---|---|
| 0.20 (config floor, inert) | 0.670 | 98.9% | 16.48% |
| 0.25 | 0.606 | 89.4% | 11.81% |
| 0.30 | 0.534 | 78.8% | 8.29% |
| *0.308 (deployed: raw gate 0.10)* | | | *7.82%* |
| 0.35 | 0.464 | 68.4% | 5.15% |
| 0.40 | 0.408 | 60.3% | 2.94% |

**Do not mix these rows with 7.82%.** That figure is on the raw scale; this sweep was run with the detector deliberately opened to raw 0.02 so the calibrated curve would not be truncated. Different gate, different number, both correct. See D8 for the full explanation.

**C9 · How does it handle noise?**
Measured on the full 4,346-frame test split, with the clean row reproducing the recorded result exactly (`ai/experiments/robustness/REPORT.md`). Speckle degrades it gracefully: mAP50 0.352 → 0.263 at sigma 0.35 and 0.221 at 0.50. Low contrast and blur hurt more: 0.085 at 0.25× contrast, 0.206 at a 9-pixel blur. The finding worth saying out loud is the *direction*: under speckle, contrast loss and heavy blur, the model goes **quiet** (false alarms fall with recall), so a bad survey looks like an empty one. With 10% of pings dropped it goes **loud**: false alarms on empty seabed rise from 7.8% to 26.4%. "We don't only test whether it works; we test how it fails." Despeckling at inference was also tried and cost 13% mAP50, because gv5 learned raw speckled frames.

**C10 · Does it reject non-sonar input?**
Partly, and we publish where it fails. Flat grey, gradients, random noise and a simulated desk photo → 0 detections, correctly rejected. **A text-document screenshot produced 2 boxes at 0.45 and a synthetic nautical chart produced 3 at 0.46 — it fails.** We added a check that flags a frame when more than 35% of it is near-pure white, which catches the screenshot and fires on nothing across 400 real sonar tiles. It **warns rather than blocks**, because one statistic does not solve non-sonar rejection.

**C11 · How fast is it? Could it run on a vessel?**
17.3 fps — a 1,000-frame survey is about a minute, 10,000 about ten. A towfish pings 5–20 times a second and a frame is 640 pings, so the pipeline runs roughly **a thousand times faster than the data can be collected**. Speed is not a constraint on this problem. Inference falls back to CPU when no GPU is present.

**C12 · What is the "review floor", and why are the two floors different?**
Asymmetric on purpose. Artificial classes clear a low bar (calibrated 0.20) because a missed ghost net keeps fishing for years. `natural` clears a higher one (0.45), because a low-confidence "that's a rock" is neither actionable nor evidential. `natural` is **reported, not discarded** — it is the evidence that artificial-vs-natural separation works, which is the headline metric.

**C13 · Is there a second classifier for natural vs artificial?**
No. There is deliberately **no `natural` class in training** — nobody draws boxes around rocks. The separation is measured as the false-alarm rate on unannotated seabed, which is the honest formulation and matches the PS's own wording.

**C14 · What evidence does a detection carry?**
`evidence_summary` with three parts: `artificial_verification`, `shadow_context` (whether the flank away from nadir is darker than the near flank) and free-text notes. Shadow is **reported as evidence, never acted on** — the measured signal is modest (flank asymmetry 0.384 against 0.255 for a random pair) and the physics is respected: wrecks show it (+0.263), pipelines and nets do not (+0.014, +0.023). So "no shadow" is not doubt for a flat target.

**C15 · What happens to a detection sitting over a data dropout?**
Rows carrying no acoustic return are found, and any detection more than 25% on top of them has its **uncertainty widened** rather than being silently reported as normal.

---

## D · The hard questions — accuracy and honesty

These decide the round. Rehearse every one of them out loud.

**D1 · Your project is called GhostNet-AI and it cannot detect ghost nets. Explain.**
Correct, and we say it first rather than waiting to be caught. `ghost_net` scores mAP50 0.009 with **recall 0.000** on 36 held-out boxes — the shipped model finds none of them. The precision reading of 1.000 is degenerate, not good: the model made almost no net predictions at all and one happened to be right.

**What we may claim:** *"We produced the first annotated ghost-net dataset from public side-scan sonar — 298 boxes over 73 chips, with a documented labelling convention. At 215 training boxes, the detector does not yet learn the class."*
**What we may not claim:** that it detects ghost nets.

**D2 · So why isn't it just a data problem? Did you even try to fix it?**
We ran a controlled experiment to find out — **gv6**. A compositor placed *real* net acoustic returns onto *real* train-split seabed: 1,364 frames, 2,031 boxes, taking `ghost_net` training data from 215 to **2,246 boxes**. Ground truth was perfect by construction, since the compositor chose each position. Test split held byte-identical. One variable changed.

**`ghost_net` recall stayed at exactly 0.000.** We did not promote gv6.

This rules out the two explanations that look most likely from outside: **not annotation quality** (2,031 boxes with perfect ground truth), and **not sample size** (10× the data moved recall by 0.000).

**D3 · Then why does it fail?**
Acoustic physics, not effort. A **crab pot** is rigid and stands proud of the seabed: it returns a compact bright blob *and* casts a clean shadow — two strong independent cues. A **net lies flat**. It blocks almost nothing, so it casts barely any shadow, and returns a faint low-contrast curvilinear texture — one weak cue. Synthesis multiplied the number of *examples* tenfold; it cannot manufacture a *cue the sonar physics does not put in the image*. That is also why `ghost_pot` sits roughly 14× above `ghost_net` — same category of object, different acoustics.

**D4 · Is there any path forward, or is the class dead?**
There is a measured path, and it is our best research result. Reformulating the class as **instance segmentation** instead of box detection — same 73 images, same split, same sensor, only label geometry and task head changed, 425 hand-drawn polygons — moved it:

| metric | box model | YOLO-seg (gv7d3) | U-Net (gvU1n) |
|---|---|---|---|
| Box recall | **0.000** | 0.492 ± 0.074 | 0.565 ± 0.043 (at IoU 0.5) |
| Box mAP50 | 0.009 | 0.528 ± 0.018 | — |
| Mask mAP50 / Dice | — | 0.227 ± 0.012 / Dice 0.525 ± 0.013 | Dice **0.600 ± 0.011** |
| Centroid detection rate | **0.000** | 0.607 ± 0.031 | **0.807 ± 0.042** |
| Fires on empty seabed chips | — | 42% | **1.3%** |

Three seeds each, reported as mean ± sd. The U-Net was trained with empty-seabed chips as negatives; that is what took the false alarms from 42% to 1.3%. Against gv7d3 the centroid gain is +0.200, paired chip bootstrap 95% CI [+0.105, +0.325], better on 9 of 11 test chips and worse on none (`ai/experiments/unet-scoring/RESULTS.md`).

**The mechanism:** median frame area claimed as `ghost_net` fell from **56.5% under hand-drawn boxes to 7.0% under polygons** — an eightfold reduction in seabed labelled as net. A net's axis-aligned bounding box is mostly water, so most pixels the model was shown as "ghost_net" *were* empty seabed, which is also the dominant background. The class was being taught to predict nothing, and it learned that correctly.

This independently reproduces a finding from **GhostNetZero** (Microsoft AI for Good Lab / WWF Germany / Accenture, Sept 2025), which reports ~90% centroid detection from 412 real annotated segments.

**D5 · Is the segmentation model in your demo, and what does it claim?**
It is: the U-Net (`gvU1n`, seed 1) outlines every `ghost_net` in the app. It claims nothing on its own. Every net it finds is **review-only**: it goes to a human, never onto a "confirmed" list. The reason is that **11 test chips from 2 sites cannot support a performance claim**, and three seeds do not change that. Seeds agreeing with each other says the *training procedure* is stable; it says nothing about whether the result transfers. With two sites on one coastline (10 of the 11 test chips are Quanzhou), "the model learned nets" and "the model learned Chinese coastal seabed" predict identical numbers on our test split, and nothing we can run distinguishes them. The 1.3% empty-chip rate is measured on China-Offshore seabed only. GhostNetZero's own Baltic-trained model scored 0.607 on Puget Sound — cross-region transfer is weak, which is a caution we apply to our own data too.

We have a written promotion rule: **≥300 real net instances from ≥3 sites, recall ≥0.30, three seeds with spread below the effect size, and a non-overlapping bootstrap CI**, under both mAP50 and centroid detection rate. Three of five conditions are met. The outstanding one is the first, and **no training run can clear it** — it is a data requirement. That is why we have opened a data-sharing conversation with the GhostNetZero authors.

**D6 · Your best class is 0.869. Isn't that the number you should lead with?**
Only with its caveat, or it is misleading. **615 of those 629 test boxes come from a held-out stretch of the same SubPipe survey as the training boxes** — same AUV, same sonar, same pipeline, separated only by a 156-second gap in the timestamps. It measures whether the model can follow a pipeline through seabed it has not seen. It does **not** measure generalisation to debris elsewhere. The only independent debris is **14 boxes** from sonar_detect.[^sonardetect] Quote both numbers, or say "one held-out survey track".

One further honesty point: a live pipeline is infrastructure, not litter. Do not imply every hit is waste.

**D7 · Your wreck score is 0.279. That's poor for a well-studied class.**
That number is two populations averaged together. Split by how much of the frame the object occupies:

| object size | found | total | recall |
|---|---|---|---|
| <0.2% of frame | 16 | 143 | 0.112 |
| 0.2–0.5% | 11 | 184 | 0.060 |
| 0.5–2% | 13 | 174 | 0.075 |
| **>2%** | **176** | **335** | **0.525** |

**On wrecks large enough to identify, recall is 0.525.** 501 of 836 test boxes are under 2% of frame and the model finds roughly 8% of those, which drags the average down.

Two follow-ups we pre-empted:
- **"Sloppy annotation?"** No. AI4Shipwrecks ships pixel-wise masks; our boxes are derived from them, so they are tight by construction and were never hand-drawn.
- **"Tiling fragments?"** No — and this was our own first explanation, which did not survive the test. A fragment cut by the tile grid must touch the boundary that cut it, so splitting recall by edge contact separates the two. Edge position makes no difference (>2%: 0.522 at edge vs 0.533 interior), and **279 of 327 small test boxes are interior** — 85% were never cut by anything.

So it is a genuine **small-object detection gap**. At 0.5% of a 640×640 tile, an object is about 45×45 px. **The fix is a modelling one, not a data one**: higher input resolution, or a P2 (stride-4) detection head. Both are directly testable and target a measured cause.

**How to quote it:** *"Recall 0.525 on wrecks larger than 2% of frame; 0.26 averaged over a test set in which 60% of wreck boxes are sub-2%."* Quoting 0.525 alone would be selecting a favourable subset after the fact; quoting 0.26 alone reports the tiling grid as if it were the detector.

**D8 · I've seen two different false-alarm rates in your material. Which is it?**
**7.82% is the deployed number**, and the discrepancy is a scale confusion we investigated and settled on 5 September 2026.

The pipeline has two gates: a **raw** detector gate at 0.10, and a review floor at 0.20 **calibrated**. At the shipped temperature of 2.722, `calibrate(0.02) = 0.193` and `calibrate(0.10) = 0.309`. So the 0.20 calibrated floor corresponds to a raw score of about 0.02 — well below the 0.10 raw gate. **The raw gate binds first; the review floor rejects nothing that survived it.** The floor is *inert* in the shipped configuration, so the deployed rate is the row measured at raw 0.10: 229 / 2,930 tiles = **7.82%**.

The 16.48% figure was measured with the detector deliberately opened to raw 0.02 so the calibrated sweep would not be truncated. That is correct methodology for *deriving* a floor and the wrong number to quote as deployed.

Worth volunteering: we corrected two source files as part of this, because their old note described the tiles as *"verified to contain no object"* — factually wrong and the exact phrasing we ban.

**D9 · Your overall mAP is 0.352. Isn't that just a weak model?**
It is a weak *aggregate*, and the aggregate is the wrong summary. mAP is an **unweighted** mean over five classes, so `plane` with 9 test boxes counts exactly as much as `ghost_pot` with 567. Adding a thin fifth class mechanically drags the average down. The per-class table is the honest summary; 0.352 is not, and we do not lead with it.

**D10 · Have you tested it on data unlike your training set?**
Yes, and the result is not flattering. On 24 KLSG frames from a survey nothing in training resembles: **9 of 16 shipwreck frames produced detections — all labelled `debris`, none `wreck`**; 0 of 8 aircraft frames produced anything. The aircraft result is expected at 39 training boxes. **The wreck-as-debris confusion on a new source is not, and is the most substantive open question about the model.**

**D11 · So how well does this generalise?**
Say it before being asked: held-out test frames come from the **same surveys** as training — same sonar, same water, same gear. That is genuine generalisation, but within one domain. **Expect a large drop on a different sonar.** We have not measured that drop, because we have no cross-sonar labelled data to measure it against. Marine PULSE (88 images, five different sonars) was the cheap instrument-diversity check available to us, and it is background-only.

**D12 · Has anyone independent validated this?**
No. Every number here is self-measured on public data and reproducible from the repo, with the commands published alongside. We are not claiming third-party validation and you should not infer it. The nearest thing is that our segmentation result independently reproduces a published finding from GhostNetZero, which is corroboration of the *mechanism*, not of our numbers.

**D13 · Would you deploy this today?**
Not unsupervised, and the system is built on that assumption. Every output goes to a human review queue; `ghost_net` ships under a **review-only contract** where a net prediction never asserts a detection and is rendered differently from a confirmed hit. The honest framing is that this is a **triage tool that makes a human reviewer faster**, not an autonomous detector.

**D14 · What is the weakest part of the project?**
Two candidates, and we would name both. The headline class does not work, for a reason we can prove. And our evaluation, however careful, sits on a single acoustic domain — so the numbers tell you the model works on data like our data, and nothing more.

**D15 · Isn't reporting your failures just a way of lowering the bar?**
The failures are measured, attributed and reproducible; that costs more work, not less. gv6 was 60 epochs at ~860 s each on a 4 GB GPU to establish a negative. The alternative — quietly dropping the class, or mapping `ghost_pot` to `ghost_net` so the headline metric appears to measure the PS's exact words — would have been faster and would have been inventing ground truth.

---

## E · Questions about the data

**E1 · Is any of your training data proprietary or scraped illegally?**
All 8 training sources are public research datasets. Two carry explicit permissive licences (**SubPipe and sonar_detect, CC BY 4.0**). **GhostVision is CC-BY-SA 4.0 — share-alike**, which we honour. AI4Shipwrecks, SCTD, Marine PULSE and China-Offshore carry **no formal licence file**; KLSG and SCTD state academic use. Our position is to record provenance and cite every source — that is what `ai/data/provenance/` exists for, and it is the one directory under `ai/data/` that git tracks.

**E2 · Where did your 73 ghost-net chips come from?**
This is an **open provenance question and we state it plainly.** They are third-party side-scan imagery whose origin we have not been able to document; they pre-date our provenance discipline and the raw source directory was pruned in an early commit. In practice: **the chips themselves are not published in this repository** (gitignored, local disk only). What *is* published is our own work over them — 425 polygon annotations, the labelling convention, and the build and training scripts. Annotations are separable from the imagery they describe, the same split COCO and Open Images use. **We make no ownership claim over the underlying imagery and will remove it on request from a rights holder.** Until origin is established, the chips are not offered for redistribution to third parties.

**E3 · Isn't training on freshwater lake wrecks a problem for an Indian coastal use case?**
Yes, and we flag it in our own data document. AI4Shipwrecks was collected in Thunder Bay, Lake Huron — a **freshwater lake floor**. Sediment and clutter differ from Indian coastal seabed. It is good data; it is **not in-domain**. Same caveat applies to GhostVision (Delaware Bay) and China-Offshore (Chinese offshore). We have no Indian coastal side-scan data, and we do not pretend the domain gap away.

**E4 · Why not use the existing marine-debris sonar datasets?**
We evaluated MDT and UATD — the only real marine-*debris* sonar sets we found (tyres, cans, bottles, chains, hooks). Both are **forward-looking sonar, not side-scan**, and MDT was captured in a watertank. That is a genuine modality mismatch, not a technicality: FLS and SSS differ in viewing geometry and in how acoustic shadow forms at all. Training a side-scan model on watertank FLS imagery and reporting the result as side-scan performance is exactly the quiet dishonesty this project's rules exist to prevent.

**E5 · You claim no public ghost-net sonar dataset exists. Is that verified?**
Independently. An October 2025 survey of sonar image datasets (arXiv 2510.03353) finds **no public SSS dataset containing fishing nets or ghost nets** and names it as an open gap in the field. This is why our headline metric is framed as binary artificial-vs-natural: a ghost-net F1 target cannot be honestly measured against real data that does not exist.

**E6 · Some of your data sources didn't contain what they advertised. How did you catch that?**
We verify claims against disk rather than trusting descriptions. `dataset_candidates.csv` records what sources *claim*; `data_inventory.csv` records what we *have*; they are separate files on purpose, and the inventory flags any dataset where the two disagree. Two concrete catches: the KLSG-II repository advertises 578 seafloor negatives and **contains exactly one 45 KB sample JPEG**; the Zenodo sediments set advertises 434,164 images but is a single 52.3 GB split archive with no way to extract a slice.

**E7 · Did you generate training data with AI?**
We composited synthetic ghost-net frames for gv6 — *real* net returns placed on *real* seabed, only the arrangement synthetic — and they were **train-only**, never in test, because scoring a net class on generated nets would be self-congratulation. They did not work (see D2). No diffusion-generated data was used; it was scoped out as a research project in itself.

**E8 · Do you have any Indian data?**
No. Stating it plainly is better than an evasion. The closest honest framing is that the pipeline reads standard XTF and derives its own geometry from ping headers, so it ingests an Indian survey the day one is available — but the *model* would need retraining or at minimum revalidation on that domain, and we would expect a drop.

---

## F · Sonar physics and geolocation

**F1 · How do you turn a pixel into a latitude and longitude?**
From the sonar's own navigation data in the ping headers: the towfish position, heading, **altitude above the seabed**, the nadir column and the range resolution in metres per pixel. Across-track distance is a **slant range** — the distance along the sound path — which must be corrected to ground range using altitude. The result is projected on the WGS84 ellipsoid via `pyproj`, not flat trigonometry.

**F2 · What if the navigation data is incomplete?**
**All-or-nothing, by design.** With all four geometry fields plus a position fix you get coordinates and metric dimensions; with any one missing you get **neither**, and the reason lands in the `warnings` channel on screen. We never emit a partial or guessed position.

**F3 · Couldn't you just substitute a nearby field to fill the gap?**
This is the trap we most deliberately refuse. `depth` is **water depth**, not altitude above the seabed; `range` is **swath width in metres**, not metres-per-pixel — they differ by roughly the image width. Substituting either does not *degrade* a position, it **corrupts** it: you get a map that looks right and is wrong by a variable amount, worst near nadir. The adapter refuses the substitution and reports no position.

**F4 · How is the error radius calculated, and is it honest?**
It combines GPS scatter, heading error and altitude uncertainty — 4.3–4.5 m on the demo survey. It is an estimate of geolocation uncertainty and is presented as one. It is not a claim about detection correctness; those are separate numbers.

**F5 · Why can't uploaded images be geolocated?**
No ping headers means no geometry — no nadir column, no range resolution, no altitude. The system says so rather than estimating, because an invented position looks identical to a measured one on a map.

**F6 · You mentioned a real geometry bug. What was it?**
The **starboard channel was mirrored on every frame** — a genuine geometry error that put detections on the wrong side of the track. Fixed by detecting sample order per channel rather than assuming it. We list it in our own bug log rather than quietly patching it, because it is the class of bug that produces a confident, wrong map.

**F7 · Why are rotation and vertical flip disabled in augmentation?**
Because in side-scan, across-track is **range**. A rotated or vertically flipped tile is not an image the sonar can physically produce — the acoustic shadow would fall on the wrong side of the object, teaching the model a false cue. Horizontal flip is kept because it corresponds to a real configuration: a port/starboard mirror, or the vessel running the reciprocal track.

**F8 · Can the same object be reported twice?**
Yes, if it sits on a tile seam. Duplicate suppression across seams needs matching in survey coordinates and was scoped out. We list it as a known limitation rather than hiding it.

---

## G · Engineering, architecture and production readiness

**G1 · Describe the architecture.**
Three layers. **AI** — a Python package (`ai/ghostnet`, 13 modules) that parses XTF, tiles, detects, calibrates, geolocates and exports. **Backend** — FastAPI + SQLAlchemy 2.0 on PostgreSQL/PostGIS, JWT auth, RBAC, WebSocket job events, Alembic migrations. **Frontend** — Next.js 14 App Router, React Query for server state, Leaflet for 2D maps and three.js for 3D.

**G2 · Is the AI a separate microservice?**
No, deliberately. The backend does `pip install -e ai/` and calls `detect()` **in-process**. The final demo runs on one machine, so an HTTP hop would add failure modes and latency for no benefit.

**G3 · Then how did two people build in parallel without breaking each other?**
A **frozen, machine-checked contract**. The JSON schemas in `contracts/` are *generated* from `ai/ghostnet/contract.py` by a script; hand-editing is forbidden and CI fails if they drift. The backend checks the AI package's contract **major version at startup and refuses to boot on a mismatch**, rather than silently misreading a payload.

**G4 · What happens when the AI fails?**
`detect()` is contracted to **never raise**. A missing model, missing metadata, an unreadable image or an absent GPU all come back as a valid response with `warnings` explaining what happened. Errors are reserved for four real cases: `bad_request`, `unreadable_image`, `internal_error`, `out_of_memory`. Degraded conditions are **not** errors — they are valid output with warnings.

**G5 · What is the security posture?**
JWT with refresh tokens and bcrypt hashing; **RBAC** across admin / operator / reviewer / viewer; rate limiting at 60 requests/min general and 5/min on login, with a lockout after **five failed logins for one username in 15 minutes**, derived from the audit log. Errors are uniform and do not leak existence — a file in *another* survey returns the same `FILE_NOT_FOUND` 404 as one that does not exist.

**G6 · Is there an audit trail?**
Append-only `audit_logs` and `detection_reviews`. One detail worth volunteering: **audit rows are written after the act, not before** — writing first would record deletions that were then refused, producing a trail that lies in exactly the case it exists to explain.

**G7 · What about data integrity when something is deleted?**
`ondelete="CASCADE"` throughout, so deleting a survey removes files → frames → detections → reviews in one statement. Deletion is **refused with 409 while a job is running**, because the cascade would pull rows out from under a task still writing them. Survey deletion is behind a typed-name confirmation.

**G8 · How is this tested?**
74 backend tests (pytest + httpx), a Vitest suite on the frontend, and a test suite on the AI package. Tests require their own database (`TEST_DATABASE_URL`, defaulting to `ghostnet_test`).
*Note a conflict in our own docs: `TECHNICAL_REFERENCE.md` (19 Sep) says 74 backend tests; `TEAM_DOC_1_PROJECT.md` (5 Sep) says 246 AI tests and 61 backend. Quote "74 backend tests plus an AI suite and a frontend suite" and do not invent a total.*

**G9 · Could this scale to a fleet of vessels?**
Not as configured, and we would rather say so than bluff. It runs **one uvicorn worker, always** — running jobs live in a process-local dict and the rate limiter is in-memory, so a second worker silently breaks job cancellation and halves the rate limits. Scaling out means moving job state and rate limiting to shared storage (Redis or the database) and adding a task queue. That is understood work, not research, but it is not done.

**G10 · You have Docker. Why not demo from it?**
Because the Docker image deliberately **does not run real detections** — torch and ultralytics would add a ~2.6 GB layer, so it falls back to a mock adapter stamped `mock-ghostnet-dev-v0`. Only XTF frame-splitting is real in Docker. Our own docs say "never demo from Docker" for exactly this reason. **If a judge asks to see Docker, say this before they see mock output and draw their own conclusion.**

**G11 · Why PostGIS for one column?**
Honest answer: **PostGIS is used for exactly one nullable geometry column** (`detections.location`, SRID 4326, with a GIST index). It is the whole spatial dependency. It buys correct spatial indexing and a straight path to spatial queries later, and it is in migration 0001, so SQLite is not a drop-in substitute.

**G12 · What is still broken?**
Four open items we track rather than hide: a "selected detection" report actually contains the whole survey (needs a `reports.detection_id` migration); filtered-detection reports come back unfiltered because the page never sends the filter; a bbox filter does not constrain the map's zoom bounds; and `POST /reports` returns a bare 500 on an unknown survey id instead of a proper 4xx. None block the demo path.

**G13 · Any bug you're actually proud of finding?**
Two. A **storage-key vs filesystem-path confusion** meant an uploaded PNG could *never* produce a detection — `cv2.imread` returned `None`, `detect()` logged "image not found" as a *warning*, and the job completed successfully with zero detections. It looked exactly like a model finding nothing. And **priority was keyed off thresholds tuned against the mock adapter's 0.45–0.98 score range**, while real calibrated scores have median 0.42 and max 0.728 — so CRITICAL and HIGH were unreachable and the queue had silently stopped triaging.

**G14 · Anything in the codebase that doesn't do what its name says?**
Yes, and we documented it: `preprocess()` is **defined but never called at inference**. It is harmless today because the default is `"none"`, but setting it to a filter would leave inference byte-identical while provenance claimed a filter that never ran. It is written down precisely so nobody trips over it later.

**G15 · Why does the frontend run a production build instead of dev mode?**
Dev mode wedged repeatedly under concurrent `.next` writes and served pages in seconds rather than milliseconds. Running `next dev` against the same directory as the production server destroys its build output. Production build only, always.

---

## H · If the demo misbehaves

**H0 · Pre-flight, do this before you present.**
As of 19 September 2026 the running stack is healthy — frontend, backend and Postgres all up, all 13 routes responding, login working — but **the database has zero surveys, zero detections and zero reports.** A survey wipe was run and never re-seeded, while `app/backend/uploads/` still holds 218 MB of orphaned files. **Re-seed with `scripts/demo_seed.py` before the round**, then open the dashboard and confirm you see a non-zero count. An empty dashboard in front of a jury reads as a broken system.

**H1 · "The dashboard is empty."**
Data was not seeded, or you are looking at a different survey. The dashboard is scoped to the survey it names.

**H2 · "Processing finished but I see nothing."**
Check that the job reached DONE and open the survey's detection list directly. A finished job vanishing from the UI was a real bug (fixed via a `jobs/latest` endpoint); if it recurs, navigate rather than wait.

**H3 · "The map is blank."**
In 3D, press **Fit Survey** — the default camera does not frame the survey. In 2D, confirm the survey actually has geolocated detections; an image-only survey has none by design, and that is a feature worth explaining rather than a failure to apologise for.

**H4 · "It found nothing in my file."**
A legitimate outcome, not a crash. Say what the system says: check the warnings channel. Common honest causes are a non-sonar image, missing geometry, or genuinely empty seabed. Offer one of the four fixtures as a known-good comparison.

**H5 · "The page is hanging / clicks aren't registering."**
The landing water shader is a full-screen raymarch and can saturate integrated graphics; a saturated GPU stalls the compositor, which presents as dropped clicks rather than slow water. Its loop stops off-screen, on a hidden tab and under reduced motion. Skip the landing page and go straight to `/auth/login` if the demo machine is weak.

**H6 · Something is genuinely broken on stage.**
Say what broke, in one sentence, and move to the next screen. This project's entire pitch is that it reports failures accurately. Improvising a cover story is the one thing that contradicts the thesis.

---

## I · Impact, roadmap and the "so what" questions

> **Warning:** the repository contains no cost model, no deployment plan and no India-specific pilot data. Answer these from principle and say when a number does not exist. Inventing one here would break rule 1 and is the easiest way to lose a round you were winning.

**I1 · What is the real-world impact?**
The documented economic case is in A2. Our own contribution is narrower and we should state it narrowly: a triage tool that lets one reviewer cover more survey line, plus an open annotated ghost-net dataset and a reproduced finding about *how* the task should be formulated.

**I2 · What would a deployment cost?**
We have not modelled it. What we can say: training ran on a **single 4 GB consumer laptop GPU**, inference runs at 17.3 fps and falls back to CPU, and the entire stack is open-source with no paid services. The binding cost in this problem is **collecting the sonar** — ship time — and nothing we built changes that.

**I3 · What is the next milestone?**
Three, in priority order, all with measured causes. (1) **Get real ghost-net data** — ≥300 instances from ≥3 sites, which is the only thing that can clear the promotion rule; the GhostNetZero conversation exists for this. (2) **Close the small-object gap** on wrecks — higher input resolution or a P2 stride-4 head, targeting a measured 0.525 → 0.26 spread. (3) **Train on despeckled data** rather than despeckling at inference, which measured −13% mAP50 because it puts a cleaned frame out of distribution.

**I4 · What did you deliberately not build, and why?**
Segmentation masks for any class but `ghost_net` (boxes fit compact objects; masks earn their cost only on thin, fragmented targets like nets, which do get a U-Net). TensorRT export (4 GB VRAM, and inference is already ~1,000× faster than data collection). A bigger model (data-limited, not capacity-limited). JSF file reading (no JSF sample existed to test against). Cross-seam duplicate suppression (needs survey-coordinate matching). Being able to explain *why not* is worth as much as a feature.

**I5 · Is there a business model?**
Not one we have built or validated. Do not improvise one under questioning — "we haven't modelled commercialisation; the work so far is the detection and evaluation problem" is a stronger answer than an invented TAM.

**I6 · How is this different from GhostNetZero, which already exists?**
We are not competing with it — we reproduced its central finding independently on different data and said so in writing. The differences are that our system is a **full operational pipeline** (raw XTF in, reviewed geotagged report out, with auth, audit and review workflow) rather than a detection result, and that we publish our failure surface. We have offered them our 425 polygon annotations, the labelling convention, our centroid-metric implementation including the clustering rule and an aspect-ratio correction, and our small-n evaluation discipline.

**I7 · What did you learn that would generalise to other projects?**
The most transferable finding is about **early stopping on small datasets**. Replicating across three seeds produced not an error bar but a bug: one seed stopped at 131 epochs against the others' 608 and 558, and looked like catastrophic seed variance. On 51 training images the model sits near zero mask mAP50 for roughly the first 200 epochs *in every seed* — early stopping asks "has it improved lately?" inside a region where the metric moves only in the fourth decimal, so the decision is made on noise. With it disabled, seed spread fell **0.101 → 0.012** and the "catastrophic" seed came back best of three. A single-run number can hide a training failure that looks exactly like a modelling result.

---

## J · Process, originality and team

**J1 · Who built what?**
Two-person core build. Member 1: dataset, sonar preprocessing, ML, verification, confidence, geotagging, the AI output contract. Member 2: FastAPI, database, GIS, frontend. Members 3–4: presentation and written content. Two machines, GitHub as source of truth, the halves meeting at the frozen contract.

**J2 · Did you use AI assistance to build this?**
Answer honestly and specifically for your team. The defensible framing is that assistance does not change what is verifiable: the numbers are reproducible with published commands, the negative results are written up against a byte-identical test split, and the failure modes are documented. Point at `testbench.html`, which holds 5 hits, 3 misses, 3 correct rejections and 3 false positives with a live confidence slider — a highlight reel would not include the misses.

**J3 · How much of this is off-the-shelf?**
The detector is Ultralytics YOLO11-S, transfer-learned — we did not invent an architecture and do not claim to. What is ours: the dataset assembly and leakage-safe splitting, the ghost-net annotation set and convention, the calibration and decision policy, the XTF parsing and slant-range geolocation, the contract, the full application, and the experimental work including both negative results.

**J4 · What would you do differently?**
Establish provenance discipline before the first download, not after (see E2). And treat early-stopping patience as a parameter to justify rather than inherit (see I7).

**J5 · Can we see the code?**
Yes. Weights are tracked in the repository (19 MB), so a clone gets real weights rather than the mock adapter. Every metric in this brief has a reproduction command beside it in `docs/MODEL_CAPABILITY_EVIDENCE.md`.

---

## K · One-page cheat sheet

**The numbers, with their sample sizes**

| Fact | Value |
|---|---|
| Test split | 4,346 held-out frames |
| `debris` mAP50 | 0.869 (n=629; **615 from one SubPipe track**) |
| `ghost_pot` mAP50 | 0.314 (n=567) |
| `wreck` mAP50 | 0.279 (n=836); recall **0.525 on >2%-of-frame objects** |
| `ghost_net` mAP50 | 0.009, **recall 0.000** (n=36) |
| `plane` | **do not quote** (n=9) |
| Overall | mAP50 0.352 · P 0.580 · R 0.361 — *the aggregate misleads, use per-class* |
| Calibration | T = 2.722 · **ECE 0.218 → 0.089** |
| Calibrated score range | median 0.422 · p90 0.664 · **max 0.728** |
| False alarms | **7.82%** on 2,930 tiles *carrying no annotation*, raw gate 0.10 — an upper bound |
| Segmentation (net), shipped U-Net | Dice **0.600 ± 0.011**, centroid rate **0.807 ± 0.042**, **1.3%** on empty chips — *11 chips, 2 sites, review-only, not a claim* |
| Label area, box → polygon | **56.5% → 7.0%** of frame |
| Speed | 17.3 fps · 58 ms/tile · ~1,000× faster than collection |
| Training | 18,310 images · 8 public sources · 60 epochs · batch 4 · RTX 3050 4 GB |

**Six answers you must be able to give in one breath**

1. *"It cannot detect ghost nets — recall 0.000 on 36 boxes. We ran a controlled experiment to find out why, and the answer is acoustic physics: a net lies flat and gives one weak cue where a pot gives two strong ones."*
2. *"0.869 on debris, but 615 of 629 of those boxes are one held-out stretch of the same pipeline survey — it measures tracking a pipeline, not generalisation."*
3. *"0.279 on wrecks is two populations averaged: 0.525 on wrecks over 2% of frame, about 8% on the small ones. It's a small-object gap, and the fix is resolution, not data."*
4. *"7.82% false alarms on tiles carrying no annotation — an upper bound, because some of those survey lines were never annotated at all."*
5. *"Our confidence is calibrated: ECE 0.089, down from 0.218. When it says 0.7 it's right about 70% of the time — and the maximum it can ever produce is 0.728, so don't set a threshold at 0.8."*
6. *"It degrades rather than fails. No navigation data means no coordinate — never an invented one. A missing pin is recoverable; a confidently wrong pin is not."*

**Three traps to never walk into**

- Calling `ghost_pot` results a ghost-net result.
- Quoting a threshold without saying raw or calibrated.
- Demoing from Docker, where the adapter is mocked.

---

*Sources: `docs/MODEL_CAPABILITY_EVIDENCE.md`, `docs/D2_SEGMENTATION_SUMMARY.md`, `docs/EXPERIMENT_GV6.md`, `docs/TECHNICAL_REFERENCE.md`, `docs/TEAM_DOC_1_PROJECT.md`, `docs/DATA.md`, `docs/KNOWN_ISSUES.md`, `PROJECT_OVERVIEW.md`, plus a live check of the running stack on 19 September 2026.*

[^sonardetect]: Reviewed frame by frame on 26 Sep 2026 (`ai/experiments/sonardetect-review/REVIEW.md`). 7 of these 14 boxes are in two frames that are not clean sonar: `SONARDETECT__000163` is a slide with photographs and `SONARDETECT__000183` is a composed figure with a zoomed inset. They stay in the test split, so every run remains scored on the same data, but only **7 boxes from 5 frames** are clean independent debris. Quote it as "14 boxes, 7 of them from clean frames".
