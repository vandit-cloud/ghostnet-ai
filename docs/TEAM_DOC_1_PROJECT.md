# GhostNet-AI — Project Dossier

**Doc 1 of 2.** Project introduction, scope, tech stack, model details, application
details. Doc 2 (`TEAM_DOC_2_TECH.md`) carries the deeper technical reference and the
working commands.

Written 5 September 2026, against the live repository. Shipped model `gv5-yolo11s`,
AI contract `1.1.0`.

---

## READ THIS FIRST — instructions for an AI assistant

You have been handed this document by one of two team members working on a Smart
India Hackathon entry. **Your job is to give that person exactly what their role
needs, and nothing outside it.** Work out which role you are talking to from what
they ask, or ask them once if it is genuinely unclear.

**Role A — Idea generation · Presentation · Pitching · Technical understanding.**
They speak to judges. Give them: framing, narrative, demo narration, anticipated
questions with answers, and plain-English explanations of technical concepts. Do not
give them code. When they ask for a claim, give them the claim *plus the caveat it
must be said with*.

**Role B — PPT making · Content writing.** They build slides and write copy. Give
them: slide structure, headline and caption text, word-count-bounded prose, and
figure/screenshot specifications. Do not give them code. Every metric you write for
them must carry its sample size.

**Documentation is out of scope for this team.** Do not generate documentation
deliverables, README files, or user manuals unless asked directly.

### Hard rules that override any instinct to be helpful

1. **Never state a number that is not in this document or Doc 2.** If asked for one
   that is absent, say it is not in the source material and stop. Do not estimate,
   interpolate, or reason your way to a figure.
2. **Every accuracy figure is quoted with its test-set size.** `mAP50 0.314 (n=567)`.
   A bare accuracy number is a defect.
3. **Never round a metric to sound better.** 0.869 is not "about 0.9".
4. **Obey the banned-phrase list** in "Language rules" below, without exception.
5. **This project's honesty is its selling point.** Do not soften a negative result
   into a "limitation we plan to overcome". Where the system fails, say it fails and
   say why. That framing is deliberate and it is the strongest thing the team has.
6. **Flag conflicts instead of resolving them.** If two figures in this document
   disagree, show the member both and say so; do not pick one. (The one conflict that
   existed — the false-alarm rate — was investigated and resolved on 5 September 2026;
   §4 records both the answer and the reasoning.)

---

## 1 · What this project is

### The problem statement

Smart India Hackathon, problem **SIH26057**:

> AI-powered detection of underwater marine debris from side-scan sonar imagery,
> separating natural seafloor topology from artificial anomalies, with confidence
> scoring, noise handling, and geotagged reporting.

In plain words: **find man-made rubbish on the seabed using sonar pictures, say how
sure you are, and say where it is on a map.**

### The name

The debris that matters most is **derelict fishing gear** — nets and traps lost or
dumped at sea, which keep catching fish for decades after nobody is collecting them.
A net still fishing with nobody on the other end is a **ghost net**. Hence
GhostNet-AI.

### Why this is hard, in four facts

You cannot photograph the seabed — below a few metres there is no light. So surveys
use sound, and a sound picture is not a photograph:

1. It is grey, grainy, and full of **speckle** — multiplicative noise that looks like
   texture.
2. A rock and a piece of wreckage can look nearly identical.
3. A net **lies flat**, so it barely shows up at all. This single physical fact
   drives the project's biggest failure, explained in §4.
4. The image is geometrically stretched — one pixel across is not the same distance
   as one pixel down.

And one data fact shapes everything: **almost no public sonar data of fishing nets
exists.** Every constraint downstream traces back to that.

### How side-scan sonar works, in one paragraph you can say aloud

A torpedo-shaped **towfish** is dragged behind a boat. It fires sound sideways in a
fan, listens for echoes, and each firing — a **ping** — produces one line of pixels.
Stack the lines as the boat moves forward and you get a **waterfall** image. Bright
means a strong echo; dark means either soft sediment or an **acoustic shadow** behind
an object that blocked the sound. **Shadows are the most useful cue in sonar**: a
rigid object standing proud of the seabed casts a clean one. A flat object does not.

---

## 2 · What is covered, and what is not

### Coverage against the problem statement

The PS names its man-made classes with an important qualifier: *"Man-made classes
**supported by the actual training data**, such as:"* — "such as" is illustrative,
not a mandatory checklist, and the qualifier explicitly licenses covering what the
data supports.

| # | PS wording | Our class | Test boxes | mAP50 | Status |
|---|---|---|---|---|---|
| 1 | ghost nets / entangled debris | `ghost_net` | 36 | 0.009 | **Does not work** — the headline gap |
| 1b | (partial cover of the same category) | `ghost_pot` | 567 | 0.314 | Works — real derelict fishing gear |
| 2 | shipwrecks | `wreck` | 836 | 0.279 | Works |
| 3 | pipes | `debris` | 615 of 629 | 0.869 | **Strongest class in the project** |
| 4 | cylinders | — | — | — | No dedicated class; a pipe *is* a cylinder |
| 5 | other man-made debris | `debris` | 629 | 0.869 | Works |

**Four of five categories covered, three of them working.** The one that does not
work is item 1, and its cause is acoustic physics, not effort — see §4.

**The claim that is easy to miss:** the best class in the project is `debris` at
0.869, and 615 of its 629 test boxes come from **SubPipe, a pipeline survey**. So
*pipes* — PS item 3 — is the category the system does best. "We detect seabed
pipelines at mAP50 0.869 on 615 held-out boxes" is completely true and much stronger
than calling it "debris". One honesty caveat: a live pipeline is infrastructure, not
litter. Say so rather than implying every hit is waste.

### Requirements met

| PS requirement | How it is met |
|---|---|
| Detection from side-scan imagery | YOLO11-S detector, five classes, trained on real survey data |
| Separating natural from artificial | Measured false-alarm rate on unannotated seabed, not a second classifier. There is deliberately **no `natural` class** — nobody draws boxes around rocks |
| Confidence scoring | Temperature-scaled calibrated confidence; expected calibration error 0.218 → 0.089 |
| Noise handling | Speckle characterised and tested; tile-edge false detections suppressed by shape |
| Geotagged reporting | Coordinates derived from ping headers with slant-range correction, reported with a position error radius; CSV and GeoJSON output |

### Deliberately not done — and why

Being able to explain *why not* is worth as much as a feature.

| Not done | Reason |
|---|---|
| Segmentation masks | Cut for time. Bounding boxes are sufficient for the task |
| TensorRT / model export | 4 GB VRAM, and inference is already ~1,000× faster than data collection |
| A bigger model | Data is the limiting factor, not model capacity |
| JSF sonar file reading | No JSF sample available to test against |
| Diffusion-generated training data | A research project in itself; simpler compositing did the job in an afternoon |
| Duplicate suppression across tile seams | Needs matching in survey coordinates. An object on a seam can be reported twice |
| SAM 2.1, autoencoder for unknown anomalies, test-time-augmentation uncertainty | Cut at scoping; out of reach in the time and VRAM available |
| RBAC, audit infrastructure, disaster recovery, 26 database tables | The original plan called for these. They earn no marks and cost weeks |

---

## 3 · Tech stack

Summary here; full versions, rationale and repo layout are in Doc 2.

### The AI half

| Layer | Choice |
|---|---|
| Detector | **YOLO11-S** via Ultralytics |
| Deep-learning framework | **PyTorch 2.13.0+cu126** |
| Training hardware | **NVIDIA RTX 3050 Laptop, 4 GB VRAM**, compute capability 8.6 |
| Image handling | OpenCV (headless build), NumPy |
| Geodesy | **pyproj** — WGS84 ellipsoid maths, not flat trigonometry |
| Calibration & analysis | scikit-learn, pandas, SciPy, matplotlib |
| Language | Python 3.12 |
| Packaging | `pip install -e ai/` — the AI ships as a library **inside** the web app |

### The application half

| Layer | Choice |
|---|---|
| API | **FastAPI 0.115.6** on Uvicorn |
| Database | **PostgreSQL with PostGIS**, via SQLAlchemy 2.0 + GeoAlchemy2 |
| Migrations | Alembic |
| Auth | JWT (python-jose) with bcrypt password hashing |
| Realtime | WebSockets |
| Frontend | **Next.js 14.2** (App Router), React 18.3, TypeScript 5.5 |
| Styling | Tailwind CSS 3.4 |
| Server state | TanStack React Query 5; client state Zustand |
| Maps — 2D | **Leaflet 1.9** + react-leaflet, with marker clustering |
| Maps — 3D | **three.js** + react-three-fiber + drei |
| Forms & validation | react-hook-form + Zod |
| Tests | pytest (backend and AI), Vitest + Testing Library (frontend) |

### The architectural decision worth understanding

The AI is **not a microservice**. The web backend does `pip install -e ai/` and calls
`detect()` in-process. This was a deliberate agreement: the final demo runs on one
machine, so an HTTP hop would add failure modes and latency for no benefit.

The two halves meet at a **frozen, machine-checked contract**. The JSON schemas in
`contracts/` are *generated* from `ai/ghostnet/contract.py`, and the test suite fails
if they drift. That is why two people on two machines could build in parallel without
breaking each other.

---

## 4 · Model details

### Architecture and training configuration

The shipped model is `gv5-yolo11s`, the fifth of six full training runs.

| Setting | Value |
|---|---|
| Base weights | `yolo11s.pt` (pretrained, COCO) |
| Input size | 640 × 640 |
| Epochs | 60, early-stopping patience 12 |
| Batch size | **4** — set by the 4 GB VRAM ceiling, not by preference |
| Mixed precision | AMP on (FP16) |
| Optimiser | Ultralytics `auto`, lr0 0.01, final lr factor 0.01, momentum 0.937, weight decay 0.0005 |
| Loss weights | box 7.5, cls 0.5, dfl 1.5 |
| Seed / determinism | seed 0, deterministic on |
| Classes | 5 — `wreck, plane, debris, ghost_pot, ghost_net` (index order is a wire format) |

**Augmentations used:** mosaic 1.0 (disabled for the final 10 epochs), horizontal flip
0.5, scale 0.5, translate 0.1, RandAugment, random erasing 0.4.

**Augmentations deliberately at zero:** rotation, shear, perspective, **vertical
flip**, mixup, cutmix, copy-paste. *(Interpretation, not a repo statement: vertical
flip and rotation would move the acoustic shadow to the wrong side of an object, which
is physically impossible in side-scan and would teach the model a false cue. Horizontal
flip is safe because it swaps the port and starboard halves, which is a real
configuration.)*

### Training data

Eleven-plus thousand images drawn from six public sonar datasets plus two sets we
annotated ourselves. The test split is held **byte-identical from gv5 onward** so
successive runs compare directly.

| Source | Role |
|---|---|
| AI4Shipwrecks | Shipwrecks; published test split preserved so results stay comparable to the paper |
| GhostVision | Mixed sonar targets, largest single contributor |
| SubPipe | Seabed pipeline survey — the source of the `debris` class's strength |
| China-Offshore-SSS-AI | **Contains 73 chips of real side-scan fishing net**, filed under a clutter class because that survey hunts pipelines |
| SCTD | Sonar Common Target Detection — wrecks, aircraft |
| Marine-PULSE | Imported for its **background** images only |
| SonarDetect | Small, screened for contamination |
| GHOSTNET-HAND (ours) | 73 images, boxes hand-drawn by us — the only class whose ground truth we produced |
| PLANE-HAND (ours) | 60 images, pinned **train-only** |

**Splitting rule:** split by *group*, never by file. Exact duplicates dropped,
near-duplicates and all tiles of one waterfall kept together — otherwise a tile in
training and its neighbour in test would leak the answer.

### Results — the honest scoreboard

Measured on **4,346 held-out frames** the model never saw during training.

| Class | Test boxes | Precision | Recall | mAP50 | mAP50-95 |
|---|---|---|---|---|---|
| `debris` | 629 | 0.798 | 0.855 | **0.869** | 0.516 |
| `ghost_pot` | 567 | 0.377 | 0.295 | 0.314 | 0.126 |
| `wreck` | 836 | 0.423 | 0.315 | 0.279 | 0.142 |
| `plane` | 9 | 0.355 | 0.333 | 0.292 | 0.212 |
| `ghost_net` | 36 | 1.000 | **0.000** | 0.009 | 0.003 |
| **all** | 1,426 | 0.580 | 0.361 | 0.352 | — |

**Why the aggregate misleads and must not be the headline:** mAP is an *unweighted*
mean over five classes, so `plane` with 9 boxes counts exactly as much as `ghost_pot`
with 567. Adding a thin fifth class mechanically drags the average down. The per-class
table is the honest summary; 0.352 is not.

**`ghost_net` precision 1.000 with recall 0.000** is a degenerate result, not a good
one: the model made almost no net predictions and one of them happened to be right.
An absent result, not a strong one.

**`plane` must never be quoted.** With 9 test boxes, one box is 11% of recall.

### Calibration

A raw detector score is not a probability. **Temperature scaling** rescales it so the
number means something.

| | |
|---|---|
| Temperature | **T = 2.722031**, fitted on the validation split |
| Fitted over | 1,604 predictions, 611 correct, IoU threshold 0.5 |
| Expected calibration error | **0.2178 → 0.0891** |
| Median calibrated confidence (259 real detections) | 0.422 |
| 90th percentile | 0.664 |
| **Maximum ever produced** | **0.728** |

**The consequence that broke three pieces of code before it was written down:** the
useful range is roughly **0.30 to 0.73**. A threshold set at 0.80 does not select
strictly — it selects *nothing*. Any user interface must key off the `uncertainty`
band, never a hardcoded number.

### The false-alarm figure — resolved 5 September 2026

Two files in the repository appeared to disagree, because they measure on **different
scales**. The conflict has been investigated and settled; **7.8% is correct**.

| Source file | Scale | Threshold | Tiles flagged | Rate |
|---|---|---|---|---|
| `ai/experiments/gv5-yolo11s/background_metrics.json` | **raw** detector score | 0.10 | 229 / 2,930 | **7.82%** |
| `ai/experiments/review_floor.json` | **calibrated** confidence | 0.20 | 483 / 2,930 | 16.48% |

**Why 7.8% is the deployed number.** The shipped pipeline has two gates: a raw
detector gate at `raw_conf_threshold = 0.10`, and a review floor at 0.20 *calibrated*.
Measured at the shipped temperature of 2.722:

```
calibrate(0.02) = 0.1931      calibrate(0.10) = 0.3085
```

So the 0.20 calibrated floor corresponds to a raw score of about **0.02** — well below
the 0.10 raw gate. **The raw gate binds first, and the review floor rejects nothing
that survived it.** The floor is *inert* in the shipped configuration. The deployed
false-alarm rate is therefore the row measured at raw 0.10: **7.82%**.

`review_floor.json`'s 16.48% was measured with the detector deliberately opened to raw
0.02 (`derive_review_floor.py --raw-conf`), so the calibrated sweep would not be
truncated. That is correct methodology for *deriving a floor* and the wrong number to
quote as deployed.

**Two source files were corrected as part of this** (`evaluate_background.py` and every
`background_metrics.json`): the old `note` field described the tiles as *"verified to
contain no object"*, which is the banned phrasing and factually wrong, and the old
`scale_warning` claimed that quoting 7.8% "overstates the model" — the opposite of what
the arithmetic shows, because it assumed the calibrated floor was the binding gate.

**Still say it with the annotation caveat**, which remains true and is the real
limitation: *"On 2,930 held-out tiles **carrying no annotation**, 7.8% show a reviewer
at least one box. Roughly half those tiles come from survey lines the source dataset
left entirely unannotated, so it is an upper bound."*

### The failed experiment — gv6, and why it matters

gv6 tested exactly one thing: **would synthetic ghost nets fix the `ghost_net`
class?** A compositor placed *real* net acoustic returns onto *real* train-split
seabed, producing 1,364 frames and 2,031 boxes — taking `ghost_net` training data from
215 to 2,246 boxes. Every net pixel is a real net pixel; only the arrangement is
synthetic. The ground truth is **perfect by construction**, because the compositor
chose each position.

**The answer was no.**

| Class | Test boxes | gv5 mAP50 | gv6 mAP50 | gv6 recall |
|---|---|---|---|---|
| `debris` | 629 | 0.869 | 0.879 | 0.827 |
| `ghost_pot` | 567 | 0.314 | 0.345 | 0.480 |
| `wreck` | 836 | 0.279 | **0.238** | 0.334 |
| `ghost_net` | 36 | 0.009 | 0.024 | **0.000** |
| overall | | 0.352 | 0.373 | precision **0.580 → 0.373** |

`ghost_net` recall stayed at **exactly 0.000**. gv6 was **not promoted**; gv5 remains
the shipped model. Full write-up: `docs/EXPERIMENT_GV6.md`.

**Why it failed — physics, not data volume.** A crab pot is rigid, stands proud of the
seabed, and returns *two* independent cues: a compact bright blob **and** a clean
acoustic shadow. A net lies flat, blocks almost nothing, and returns *one* faint
low-contrast curvilinear cue. Synthesis multiplied the *examples* tenfold; it cannot
manufacture a *cue the sonar physics does not put in the image*. This is the same
reason `ghost_pot` scores roughly 14× above `ghost_net`.

**Use this.** A team that ran a controlled experiment, held the test split
byte-identical, got a clean negative answer, wrote it up, and declined to ship the
model is demonstrating research discipline most hackathon entries cannot show.

### Speed

**17.3 frames per second.** A 1,000-frame survey takes about a minute; 10,000 takes
about ten. A towfish pings 5–20 times a second and a frame is 640 pings, so the
pipeline runs roughly **a thousand times faster than the data can be collected**.
Speed is not a constraint for this project.

---

## 5 · Application details

### What it is

A survey-operations web application: log in, create a survey, upload raw sonar files,
process them, inspect detections on a map and against the original sonar imagery,
review them as a human, and export a report.

### Size, as of 5 September 2026

| | |
|---|---|
| API route handlers | **29**, across 11 routers |
| Frontend pages | 16 (14 application screens, plus login and root) |
| Database tables | 8 core models |
| AI package | 3,272 lines across 13 modules |
| Tests | 246 in the AI suite, 61 backend, plus a frontend Vitest suite |

### The seven screens, in the order that tells the story

| # | Screen | What it shows |
|---|---|---|
| 1 | Dashboard | Mission summary, live pipeline state, class distribution — scoped to the survey it names |
| 2 | Surveys | Create, list, upload files, kick off processing, delete (behind a typed-name confirm) |
| 3 | Processing | Live progress over WebSocket — a job update per stage, one event per frame, one per detection |
| 4 | GIS Map | Vessel track from ping headers, detections drawn as **error circles**, 2D/3D toggle, time replay |
| 5 | Detections → Sonar Investigation | The real 640×640 sonar frame with the bounding box drawn on it, beside class, confidence, uncertainty, priority, coordinates and dimensions |
| 6 | Review Queue | Accept as artificial / reject as natural, with reviewer and note kept as an audit trail |
| 7 | Reports | Generate and download CSV or JSON, both stamped `model_version` |

### Data model

`User`, `Survey`, `SurveyFile`, `SonarFrame`, `Detection`, `DetectionReview`,
`ProcessingJob`, `Report`.

### The processing pipeline

```
XTF sonar container
  → per-channel ping parsing (port/starboard sample order detected per channel)
  → waterfall assembly
  → 640 px tiles
  → YOLO11-S detection
  → temperature calibration
  → decision policy (review floor, uncertainty band, edge-sliver suppression)
  → geotagging via ping-header geometry + slant-range correction
  → Detection rows + GeoJSON / CSV report
```

### Behaviours a judge will notice, and the answers

**Detections sit slightly off the vessel track.** Correct. The sonar looks *sideways*,
so an object is not where the boat was. If they sat on the line, the geometry would be
wrong.

**Markers are error circles, not pins.** The radius — 4.3–4.5 m on the demo survey —
is derived from GPS scatter, heading error and altitude uncertainty. A pin would claim
a precision the system deliberately refuses to claim.

**Pressing Process twice returns `409 ALREADY_PROCESSED`.** Deliberate: a second run
would append a duplicate copy of every detection, and re-running discards review
decisions. `force_restart: true` overrides it intentionally.

**The reviewer is read from the access token, not the request body.** So a review
decision cannot be attributed to someone who did not make it.

**In 3D you must press "Fit Survey".** The default camera does not frame the survey on
entry. Known, minor, and worth knowing before demoing.

### "That was too fast — is the model really running?"

A fair question, and one our own team asked after watching the demo. **Yes it is**, and
here is how to prove it on the spot.

**Why it feels instant.** The model is genuinely this fast. A 640×640 tile takes about
58 ms on the RTX 3050 — 17.3 frames per second. Forty frames is roughly 2.3 seconds of
actual inference. The ~14 seconds you see is mostly *other* work: parsing 6,039 pings
out of the XTF, assembling waterfalls, cutting tiles, writing database rows, and
broadcasting WebSocket events — plus about 3.2 s of **deliberate** delay the backend
inserts so the progress stepper is legible to a human. **The app is slowed down on
purpose; the model is not the slow part.** People expect AI to be slow. At one tile at a
time on a modern GPU, it isn't.

**Four proofs, checked 5 September 2026:**

1. **The code path has no shortcut.** Processing calls
   `adapter.analyze_frame()` → `ghostnet.detect()` per frame. There is no lookup table,
   no cached result, no fixture branch.
2. **Standalone inference reproduces the app's stored output exactly.** Running
   `detect_survey()` outside the app on the demo file returns 2 detections with boxes
   `[0,151,129,62]` and `[285,63,141,47]` at raw 0.112 / 0.197 — **identical, box for
   box, to the rows the app wrote to its database.**
3. **Different files give different answers.** The four demo fixtures produce 6, 7, 4
   and 13 detections. Canned data does not vary by input.
4. **Timestamps show a live loop.** Detection rows are written seconds apart, ascending,
   clustered around each processing run — not inserted in bulk with one timestamp.

**What is genuinely pre-made, and say so if asked:** the demo *surveys* can be seeded by
`scripts/showcase_seed.py`, which creates surveys and uploads files. But it drives the
application's own API and then presses Process — it **cannot** insert a detection. Its
own docstring says it: *"Every box in the app is produced by the model at processing
time. No detection is pre-recorded, hand-placed or edited."*

**The one-sentence answer to a judge:** *"Upload any of these four files yourself and
watch the count change — nothing is cached, and the whole survey is 2.3 seconds of real
inference; the rest of the wait is us drawing a progress bar slowly enough to read."*

### The design principle that ties the whole system together

**It is built to degrade rather than fail, and to say so.**

- No navigation data → detection reported **without** coordinates, never invented ones
- Detection in the water column → position withheld, uncertainty widened
- Unreadable image → a warning, not a crash and not a fake "clean" result
- Corrupt calibration file → says so, rather than silently using raw scores
- Wrong metadata units → refuses the substitution and reports no position

That last one matters most. `depth` is not `altitude`, and using one for the other does
not degrade a position — it **corrupts** it, producing a map that looks right and is
wrong by a variable amount. **A missing pin is recoverable; a confidently wrong pin is
not.**

`detect()` is contracted to **never raise**. A missing model, missing metadata, an
unreadable image or an absent GPU all come back as a valid response with `warnings`
explaining what happened.

---

## 6 · Team split

| | |
|---|---|
| **Member 1** | Dataset, sonar preprocessing, ML, natural-vs-artificial verification, confidence, geotagging, the AI output contract |
| **Member 2** | FastAPI, database, GIS, frontend |
| **Member 3** | Idea generation, presentation, pitching, technical understanding |
| **Member 4** | PPT making, content writing |

Two PCs, GitHub as shared source of truth, each machine on its own branch, the halves
meeting at the frozen contract.

---

## 7 · Language rules

### Fair to claim

- "Detects derelict crab pots in real side-scan sonar" — with the per-class mAP50 and its box count
- "Detects seabed pipelines at mAP50 0.869 on 615 held-out boxes"
- "Reports position with an error radius, or no position at all when navigation data is missing"
- "Calibrated confidence: expected calibration error 0.089, down from 0.218"
- "Reads raw XTF sonar files and derives its own survey geometry"
- "We tested whether synthetic training data fixes the net class. It does not, and here is why."

### Banned — every one of these is a losable question

| Never say | Say instead |
|---|---|
| "ghost net" for a crab pot | derelict crab pot, or ghost *gear* |
| "verified-empty seabed" | "tiles carrying no annotation" |
| `debris` 0.869 with no caveat | "...on 615 held-out boxes, 615 of 629 from one pipeline survey" |
| any `plane` figure | omit the class entirely |
| a threshold with no scale named | "raw score 0.10" or "calibrated confidence 0.20" |
| "7.8% of verified-empty seabed" | "7.8% of tiles carrying no annotation — an upper bound" (the rate itself is correct at the deployed gate; see §4) |
| "99% accurate", "real-time AI", "fully automated" | the actual per-class numbers |
| ghost-net improvements without disclosure | say the training data was largely synthetic |

### The thing that actually distinguishes this project

The accuracy numbers are modest, and with this much public sonar data they always will
be. What is genuinely unusual is that **the system says "I don't know" in specific,
measured ways** — calibrated confidence, a published false-alarm rate, error radii
instead of pins, a refusal to invent coordinates, and a warnings channel that explains
everything odd on screen.

Plenty of projects can show a demo that works. Very few can show you exactly where and
why theirs doesn't. **That is what to lead with** — not as an apology, as the
differentiator.

---

## 8 · Glossary

| Term | Meaning |
|---|---|
| **Side-scan sonar** | Sound-based imaging that looks sideways from a towed body |
| **Towfish** | The torpedo-shaped sonar body dragged behind the boat |
| **Ping** | One firing of the sonar; produces one line of the image |
| **Waterfall** | The image built by stacking ping lines as the boat moves |
| **Nadir** | The strip directly beneath the towfish, where the two channels meet |
| **Acoustic shadow** | The dark region behind an object that blocked the sound. The strongest cue in sonar |
| **Speckle** | Multiplicative noise inherent to coherent imaging; looks like texture |
| **Slant range** | Distance along the sound path, which must be corrected to get ground distance |
| **XTF** | eXtended Triton Format — the raw sonar container file we read |
| **Tile** | A 640×640 crop of a waterfall, the unit the detector sees |
| **Precision** | Of the alarms raised, what fraction were real |
| **Recall** | Of the real objects present, what fraction were found |
| **mAP50** | Mean average precision at 50% box overlap; combines precision and recall |
| **Held-out** | Data the model never saw during training |
| **Calibration** | Rescaling a model score so it behaves like a probability |
| **ECE** | Expected calibration error — how far confidence is from observed correctness |
| **Temperature scaling** | The one-parameter calibration method used here |
| **Review floor** | The confidence below which a detection is not shown to a reviewer |
| **Hard negative** | A background example that looks like a target; used to teach the model restraint |
| **Contract** | The frozen JSON shape the AI returns and the app consumes |
