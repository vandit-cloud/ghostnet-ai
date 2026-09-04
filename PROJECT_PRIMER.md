
# GhostNet-AI — Project Primer

**Start here if you know nothing about this project.** Written 3 September 2026.
Assumes no background in sonar or machine learning; explains every term the
first time it appears.

Everything in this document was checked against the code, the data and the
training logs on the day it was written. Where a number is uncertain or
provisional, it says so.

---

## Part 1 — What are we actually trying to do?

### The problem statement

We are entering **Smart India Hackathon**, problem **SIH26057**. The problem
asks for:

> AI-powered detection of underwater marine debris from side-scan sonar
> imagery, separating natural seafloor topology from artificial anomalies,
> with confidence scoring, noise handling, and geotagged reporting.

In plain words: **find man-made rubbish on the seabed using sonar pictures, say
how sure you are, and say where it is on a map.**

The debris that matters most is **derelict fishing gear** — nets and traps lost
or dumped at sea. They keep catching fish for decades after nobody is
collecting them. That is why the project is called *GhostNet*: a "ghost net" is
a net that keeps fishing with nobody on the other end.

### Why this is hard

You cannot photograph the seabed. Below a few metres, light is gone. So surveys
use **sound** instead, and sound produces a picture that looks nothing like a
photograph:

- It is grey, grainy, and full of speckle.
- A rock and a piece of wreckage can look almost identical.
- A net lies flat, so it barely shows up at all.
- The picture is stretched: one pixel across is not the same distance as one
  pixel down.

And there is a data problem that shapes the entire project: **almost no public
sonar data of fishing nets exists.** We will come back to this — it is the
single most important constraint we work under.

---

## Part 2 — Sonar terminology

Read this once. Everything else depends on it.

### How side-scan sonar works

A torpedo-shaped device called a **towfish** is dragged behind a boat. It emits
a pulse of sound sideways, in both directions, and listens for the echo. One
pulse-and-listen cycle is a **ping**.

Each ping gives one thin strip of seabed. Stack thousands of pings on top of
each other and you get an image called a **waterfall** — because it scrolls down
like water as the boat moves.

```
            towfish (nadir line, directly underneath)
                        │
   port side ◄──────────┼──────────► starboard side
   ░░▒▒▓▓██   ██▓▓▒▒░░  │  ░░▒▒▓▓██   ██▓▓▒▒░░     ← ping 1
   ░░▒▒▓▓██   ██▓▓▒▒░░  │  ░░▒▒▓▓██   ██▓▓▒▒░░     ← ping 2
   ░░▒▒▓▓██   ██▓▓▒▒░░  │  ░░▒▒▓▓██   ██▓▓▒▒░░     ← ping 3
                     ▲
              acoustic shadow behind an object
```

| Term | Meaning |
|---|---|
| **Side-scan sonar (SSS)** | Sonar that looks sideways. This is our data. |
| **Forward-looking sonar (FLS)** | Sonar that looks ahead. **Different physics — we deliberately excluded all FLS datasets.** |
| **Ping** | One sound pulse and its echo. One row of the image. |
| **Waterfall** | Many pings stacked into a picture. |
| **Towfish** | The device being towed. Also called "the fish". |
| **Nadir** | The line directly beneath the towfish, down the centre of the image. |
| **Water column** | The dead band either side of nadir where sound hasn't reached the seabed yet. **No usable information — and no position can be calculated there.** |
| **Port / starboard** | Left / right of the towfish. |
| **Across-track** | Sideways, perpendicular to the boat's path. Left-right in the image. |
| **Along-track** | Forwards, the direction of travel. Up-down in the image. |
| **Swath** | The full width of seabed covered by one ping. |
| **Backscatter** | How much sound bounced back. Bright = hard/rough. Dark = soft/absent. |
| **Acoustic shadow** | The dark area behind an object that stands proud of the seabed, where sound couldn't reach. A real clue that something is there. |
| **Speckle** | The grainy texture in all sonar images. Interference, not seabed. |
| **Dropout** | Rows where the sonar recorded nothing — a glitch, or padding at the edge of a file. Flat black or flat white. |

### The geometry that puts a detection on a map

This is the part most projects get wrong, so it is worth understanding.

| Term | Meaning |
|---|---|
| **Slant range** | The straight-line distance from towfish to target. What the sonar measures — the hypotenuse of a triangle. |
| **Ground range** | The horizontal distance along the seabed. What a map needs. |
| **Altitude** | The towfish's height **above the seabed**. **Not the same as depth** (depth is how far below the surface it is). |
| **Range resolution** | Metres of seabed per **pixel**. **Not the same as range** (which is the whole swath width). |
| **Layback** | How far behind the boat's GPS antenna the towfish trails. The GPS knows where the boat is; the fish is somewhere behind it. |
| **Heading** | The direction the boat is travelling, in degrees (0 = north). |

To convert slant range to ground range you use Pythagoras:

```
ground² = slant² − altitude²
```

If altitude is 3 m and slant range is 5 m, ground range is exactly 4 m. Skip
this correction and every coordinate is wrong — worst near nadir, which is
where an operator most trusts the position.

**If the slant range is shorter than the altitude, there is no answer.** That
means the point is in the water column, and our code returns "no position"
rather than inventing one.

### File formats

| Term | Meaning |
|---|---|
| **XTF** | eXtended Triton Format. What real sonar hardware writes. Contains the pings *and* the navigation data (position, heading, altitude) for each one. We can read this. |
| **JSF** | Another sonar format. **We cannot read this yet.** |

---

## Part 3 — Machine learning terminology

### The basic idea

We are doing **object detection**: given an image, draw boxes around the things
of interest and label each box. This is different from *classification*
(labelling a whole image) and *segmentation* (outlining exact shapes).

To do this you need thousands of examples where a human has already drawn the
boxes. The model looks for statistical patterns that separate "box here" from
"no box here".

| Term | Meaning |
|---|---|
| **Model** | The thing that makes predictions. |
| **Weights** | The numbers inside the model that get adjusted during training. Our file is `ghostnet.pt`, about 19 MB. |
| **Annotation / label** | A human-drawn box plus its class. The ground truth. |
| **Bounding box** | A rectangle, stored as `[x, y, width, height]`. |
| **Class** | A category of object. We have five. |
| **Training** | Showing the model examples repeatedly and nudging the weights until predictions improve. |
| **Inference** | Using the trained model to predict on new images. Fast: 0.058 seconds per frame for us. |
| **Epoch** | One complete pass through all the training images. |
| **Batch** | How many images the model looks at simultaneously. Ours is 4 — limited by graphics memory. |
| **VRAM** | Memory on the graphics card. **Ours is 4 GB, and this is our biggest technical constraint.** |
| **imgsz** | The size images are resized to for training. Ours is 640×640 pixels. |
| **Augmentation** | Artificially varying training images (flips, brightness) so the model doesn't memorise. |

### Splitting the data — and why it must be strict

The data is divided three ways:

| Split | Ours | Purpose |
|---|---|---|
| **Train** | 13,896 images | The model learns from these. |
| **Validation (val)** | 1,492 images | Checked during training to see if it's improving. Not learned from. |
| **Test** | 4,346 images | **Touched only once, at the end.** The honest score. |

If test data leaks into training, the model has effectively seen the exam paper
and every number becomes meaningless. Our `build_dataset.py` splits by **source
frame group**, not by file, so all the tiles cut from one sonar image stay
together on the same side of the wall. Otherwise two nearly-identical tiles
could land in train and test, and the score would be inflated.

**Our test split is frozen at 4,346 images.** It hasn't changed across runs, so
every run's score is directly comparable.

### How performance is measured

| Term | Meaning |
|---|---|
| **IoU** (Intersection over Union) | How much a predicted box overlaps the true box. 1.0 = perfect. A prediction usually counts as correct at IoU ≥ 0.5. |
| **Precision** | Of the things the model flagged, what fraction were real? Low precision = crying wolf. |
| **Recall** | Of the real things present, what fraction did it find? Low recall = missing things. |
| **mAP50** | mean Average Precision at IoU 0.5. The standard single-number score for detection. **Averaged over classes without weighting** — so a class with 9 examples counts as much as one with 567. This is why we never lead with it alone. |
| **mAP50-95** | Stricter version, averaged over many IoU thresholds. Always lower. |
| **False alarm / false positive** | Flagging something that isn't there. |
| **Background** | An image with nothing to find. Also called a **hard negative** when it's a tricky one — a rock that looks like debris. |
| **Confidence score** | The model's own 0–1 rating of a prediction. |

**There is always a trade-off between precision and recall.** Lower the
threshold and you find more real things but also more false alarms. Raise it and
the reverse. There is no setting that is good at both.

### Calibration — an important idea

A raw confidence score is **not a probability**. A detector that says 0.95 is
often nowhere near 95% likely to be right. It is over-confident.

**Temperature scaling** fixes this: fit a single number *T* on the validation
set and use it to squash the scores toward 0.5. Ours is **T = 2.722**.

The effect at the top of the range is severe:

| Raw score | Honest (calibrated) score |
|---|---|
| 0.99 | 0.85 |
| 0.98 | 0.80 |
| 0.84 | 0.65 |
| 0.50 | 0.50 |

Read it right-to-left: **to get an honest 0.85, the detector must first produce
a raw 0.99** — which almost never happens.

**ECE** (Expected Calibration Error) measures how far off the confidences are.
Ours went **0.218 → 0.089** after calibration. Lower is better.

**This has caused three separate bugs in this project.** Someone picks a
threshold like 0.85 while thinking about raw scores, applies it to calibrated
scores, and it silently selects nothing. Always say which scale a number is on.

### Terms specific to this project

| Term | Meaning |
|---|---|
| **Contract** | The exact shape of the data the AI hands to the web app. Frozen and version-numbered so the two halves can't drift apart. Currently **v1.1.0**. |
| **Provenance** | Which model, dataset and calibration produced a result. Stamped on every detection. |
| **Review floor** | The confidence below which a detection is hidden from the reviewer. |
| **Uncertainty band** | `low` / `medium` / `high`, derived from calibrated confidence. |
| **Localization** | `frame-level` (we know roughly where) or `none` (we don't). |
| **Position error radius** | The circle within which the object probably lies. We draw a circle, never a pin. |
| **Domain shift** | When new data looks different from training data (different sonar, different seabed) and accuracy drops. |

---

## Part 4 — The datasets

This is the heart of the project. **We have no proprietary data**; everything is
public research data, and finding it was most of the early work.

We ended up with **18,310 images from 10 sources**. Here is each one.

### AI4Shipwrecks — 6,976 images
**Shipwrecks in Lake Huron, USA.** From the University of Michigan Field
Robotics group. Real side-scan sonar of 24 wreck sites, published with
pixel-perfect outlines of each wreck.

- **Gives us:** wrecks, and most of our empty seabed
- **Format:** segmentation masks (outlines), which we convert to boxes
- **Licence:** open research dataset
- **The catch, and it's important:** it annotates *one target wreck per site*.
  Survey lines that pass over other man-made structures get a **completely
  blank label** even though objects are visible. **100 of 261 waterfalls (38%)
  are blank this way.** So "no annotation" does not mean "empty seabed" — which
  is why every false-alarm number we quote is an **upper bound**.

### GhostVision — 6,655 images
**Derelict crab pots in Delaware Bay, USA.** Published on Zenodo. Real
side-scan sonar of abandoned crab traps, with detection annotations already
drawn.

- **Gives us:** `ghost_pot` — our strongest and most important class
- **Licence:** CC-BY-SA 4.0
- **Why it matters:** a crab pot is **real derelict fishing gear in real sonar**.
  It is the closest thing to the problem statement that ground truth actually
  exists for anywhere in the world.
- **It is not a net.** Never call it one.

### China-Offshore-SSS-AI — 2,072 images
**Chinese offshore survey data.** Its purpose is pipeline inspection, so it
labels gullies, riprap, scour marks and sand waves as things to *ignore*.

- **Gives us:** **hard negatives** — natural features that look like debris.
  Priceless for teaching the model not to cry wolf at rocks.
- **And unexpectedly:** 73 chips of **fishing net**, filed under `hard_negative`
  because a net is what *they* want to ignore. For us it's the headline object.

### SubPipe — 2,049 images
**Underwater pipeline inspection survey.** Real side-scan sonar following a
submarine pipeline.

- **Gives us:** `debris` — went from 122 to 1,556 training boxes
- **Licence:** CC BY 4.0
- **The catch:** 615 of our 629 `debris` test boxes come from **one** SubPipe
  survey line. So `debris` is arguably a *pipeline* detector, not a general
  debris detector. Must be said whenever the number is quoted.

### SCTD (Sonar Common Target Detection) — 327 images
**Chinese academic dataset**, freely downloadable from GitHub with no email
required. Ships, aircraft and human-made objects with real bounding boxes.

- **Gives us:** most of our `wreck` and all our original `plane` boxes
- **Format:** Pascal VOC XML
- **Note:** the paper claims 596 images; the published class breakdown sums to
  357, and we actually have 327 after removing duplicates.

### GHOSTNET-HAND — 73 images (annotated by us)
**The 73 fishing-net chips from China-Offshore, with boxes we drew ourselves.**
298 boxes, one per net panel.

- **This is the only ground truth in the project that we produced rather than
  inherited.** The annotation convention — one box per panel, bounded by where
  the netting stops, never spanning empty seabed — is documented with worked
  examples in `ai/data/annotate/ghost_net/_guide/`, and is therefore part of
  the result.

### GHOSTNET-SYNTH — 1,364 images (generated by us)
**Synthetic ghost nets.** `ghost_net` had only 215 training boxes and scored
essentially zero, and there is no more real net data on earth to collect. So we
synthesised more.

- **How:** real net returns from real sonar are composited onto real seabed
  tiles. **Every net pixel is a real net pixel.** Only the arrangement is
  synthetic, and the box position is known exactly because we chose it.
- **Crucially, the compositing is multiplicative, not a paste.** A net
  *attenuates* the echo from the seabed, it doesn't replace it. A rectangular
  paste creates a brightness seam, and the model would learn the seam instead of
  the net — scoring beautifully on synthetic data and finding nothing real.
- **Train only.** Val and test contain zero synthetic images, so the score is
  still measured on real data.
- **This must always be disclosed** when quoting `ghost_net` results.

### PLANE-HAND — 60 images (annotated by us)
**62 submerged-aircraft images from the KLSG dataset**, which is
classification-only, so we drew the boxes. Follows SCTD's convention: box the
acoustic return, leave the cast shadow outside.

### Marine-PULSE — 88 images and SonarDetect — 70 images
Small sets. Marine-PULSE gives empty seabed across five *different* sonar
models, which helps the model generalise. SonarDetect (CC BY 4.0 — the only
dataset here with an explicit permissive licence) gives 14 independent `debris`
boxes, and those 14 are our only debris test data not from SubPipe.

### Datasets we deliberately rejected

Knowing what *not* to use is as important as what to use.

| Dataset | Why rejected |
|---|---|
| **MDT, UATD** | Forward-looking sonar, not side-scan. Acoustic shadow forms differently, so results wouldn't transfer. |
| **CleanSea** | Optical photographs, not sonar. Has a "Fishing Net" class, which is tempting — and useless. |
| **KLSG's 578 seafloor images** | Advertised but not in the public repo. Cloning it yields zero, silently. |
| **BenthiCat** | Right classes, but unpublished DOI and a non-commercial licence. |
| **SWDD** | "7,904 images" is really 216 originals plus augmentation and video frames of one harbour wall. |
| **Seafloor Sediments (434k images)** | 52 GB unsliceable archive, natural classes only. |

All of this is recorded in `ai/data/provenance/dataset_candidates.csv` so nobody
repeats the search.

---

## Part 5 — The five classes

The model predicts five classes. Their order is fixed — it is effectively a
wire format — and must never be reshuffled.

| id | Class | Train boxes | Test boxes | What it is |
|---|---|---|---|---|
| 0 | `wreck` | 1,373 | 836 | Ships, shipwrecks, large hulls |
| 1 | `plane` | 100 | 9 | Submerged aircraft |
| 2 | `debris` | 1,556 | 629 | Miscellaneous man-made seabed objects, mostly pipelines |
| 3 | `ghost_pot` | 7,434 | 567 | Derelict crab pots — **real derelict fishing gear** |
| 4 | `ghost_net` | 2,246 | 36 | Derelict fishing net — **the problem statement's actual object** |

**The pattern here explains every strength and weakness the model has:**
7,434 boxes gives a class that works. 100 boxes gives a class that does almost
nothing. There is no mystery — it's a data shortage.

### Why there is no `natural` class

The problem statement asks us to separate natural seafloor from artificial
anomalies. You might expect a `natural` class. There isn't one, on purpose:

**Nobody has drawn boxes around rocks.** Every natural example we have is an
image with *nothing* on it, which the training format expresses as an empty
label file — not as a class. A `natural` class would contain zero examples.

So we measure the separation a better way: **the false-alarm rate on thousands
of held-out tiles that contain no annotation.** A model that cries wolf at rocks
scores badly there. That is a stronger claim than a class label, because it's a
measurement rather than an assertion.

### The three vocabularies

Confusingly, three different naming systems exist, and keeping them separate is
deliberate:

1. **Source classes** — whatever each dataset calls things ("ship", "shipwreck", "yuwang")
2. **Training classes** — the five above, what the model learns
3. **Contract classes** — the four values the web app accepts: `ghost_net`, `debris`, `natural`, `unknown`

`wreck`, `plane`, `ghost_pot` and `debris` all report as `debris` to the web
app; the finer class is preserved in a free-text note so a reviewer still sees
it. `ghost_pot` is **never** mapped to `ghost_net` — that would be the single
most tempting lie in the project.

---

## Part 6 — Model training basics

### What we're using

**YOLO11-S**, via the `ultralytics` library. YOLO ("You Only Look Once") is a
family of object detectors that predict all boxes in one pass, which makes them
fast. The `-S` means "small" — there are bigger variants.

**Why small?** Our graphics card has **4 GB of VRAM**, and that is the binding
constraint on the whole project. A bigger model wouldn't fit. Also, our limit is
*data*, not model capacity — a bigger model would overfit sooner, not score
better.

We start from **pretrained weights** (`yolo11s.pt`), a model already trained on
millions of ordinary photographs. It arrives knowing about edges, shapes and
textures, and we retrain it on sonar. This is **transfer learning**, and it is
why 18,000 images is enough — from scratch you'd need millions.

### What a training run actually does

1. Take a batch of 4 images.
2. Predict boxes. Compare to the human-drawn truth.
3. Compute how wrong it was (the **loss**).
4. Nudge the weights slightly to reduce the loss.
5. Repeat for all 13,896 images — that's one **epoch**.
6. After each epoch, score on the validation set.
7. Keep the weights from the **best** epoch, not the last.

**Early stopping / patience:** if validation stops improving for 12 consecutive
epochs, stop. Continuing past that point makes the model memorise the training
data (**overfitting**) rather than learn.

### Where we trained

| | |
|---|---|
| **GPU** | NVIDIA GeForce RTX 3050 **Laptop** — 4 GB VRAM |
| **Software** | torch 2.13.0+cu126, ultralytics 8.4.134, Python 3.12 |
| **Settings** | imgsz 640, batch 4, mixed precision, `workers 0` |
| **Speed** | roughly 800–1,000 seconds per epoch — about 15 minutes |
| **A 60-epoch run** | **13 to 16 hours.** Usually left overnight. |

All training was done **on one laptop**. No cloud, no cluster, no rented GPUs.

`workers 0` is load-bearing — the Windows data-loader crashes otherwise.

---

## Part 7 — Our training history

Every run, what changed, and what it taught us. This is the story of the
project, and it is more useful than the final number alone.

| Run | mAP50 | What changed | Outcome |
|---|---|---|---|
| `baseline` | — | First attempt, small data | Proved the pipeline worked |
| `gv` | 0.160 | 5 sources, 4 classes, 40 epochs | Precision 0.140 — crying wolf badly |
| `gv2` | 0.132 | Added far more empty seabed | Precision 0.140 → **0.451**. False alarms collapsed 34% → 2.9%. Recall fell. |
| `gv3` | — | **Killed.** | See below. |
| `gv4` | 0.247 | More data | Best epoch was its *last* — it hadn't converged |
| `gv5` | **0.352** | Added SubPipe (`debris`) and hand-drawn nets (`ghost_net`) | **The model we currently ship** |
| `gv6` | *training now* | Added synthetic nets and hand-drawn planes | Result unknown |

### The lesson from gv3, which is the most useful mistake we made

gv3 was launched, ran 13 epochs, and produced a learning curve **identical to
gv2, digit for digit.** That is how we caught it.

We had converted new data into the staging folder but **never re-ran the script
that rebuilds the merged dataset.** So gv3 trained on exactly the gv2 data. Same
data plus the same random seed gives the same result.

**The lesson, and it is cheap to apply:** after importing anything, rebuild, and
then *read the build report* before launching. It states the sources and the
per-class box counts. gv3's own record said `debris: 122` at launch — the
evidence was written down and nobody read it.

### Where things stand right now

- **Shipped model:** `gv5`, promoted to `ai/models/trained/ghostnet.pt`
- **In progress:** `gv6`, about 8 epochs of 60 done, finishing roughly 09:00 tomorrow
- **Promotion rule agreed in advance:** gv6 replaces gv5 **only if `ghost_pot`
  mAP50 ≥ 0.314 and false alarms stay ≤ 8%**. A `ghost_net` improvement is a
  bonus, **not** grounds for promotion — 36 real test boxes cannot promote a
  model.

Deciding the rule *before* seeing the numbers is deliberate. Decide afterwards
and you rationalise whatever you got.

---

## Part 8 — How good is the model, honestly?

### Per-class results (gv5, on 4,346 held-out images)

**Always quote per-class with the box count beside it. Never the aggregate alone.**

| Class | Test boxes | Precision | Recall | mAP50 | Verdict |
|---|---|---|---|---|---|
| `debris` | 629 | 0.798 | 0.855 | **0.869** | Strong — but see caveat |
| `ghost_pot` | 567 | 0.377 | 0.295 | 0.314 | **The headline result** |
| `wreck` | 836 | 0.423 | 0.315 | 0.279 | Moderate |
| `plane` | 9 | 0.355 | 0.333 | 0.292 | Too few to mean anything |
| `ghost_net` | 36 | 1.000 | **0.000** | 0.009 | Broken on real data |
| **all** | 1,426 | 0.580 | 0.361 | 0.352 | Misleading — see below |

**Why the aggregate misleads:** mAP is an unweighted mean over five classes, so
`plane` with 9 boxes counts as much as `ghost_pot` with 567. Adding a thin fifth
class mechanically drags it down.

**`debris` 0.869 needs its caveat:** 615 of those 629 boxes are one SubPipe
pipeline survey. It measures tracking a known pipeline through unseen seabed,
not finding debris in general.

**`ghost_net` precision 1.000 with recall 0.000** is the degenerate case: it made
almost no predictions, and one happened to be right. Not a good result — an
absent one. This is what gv6's synthetic data is trying to fix.

### The artificial-vs-natural result — our strongest claim

On **2,930 held-out tiles carrying no annotation**, at the deployed operating
point, the detector flags **7.8%**.

Say it with both caveats: *"At the deployed operating point, 7.8% of held-out
frames carrying no annotation show a reviewer at least one box. Some of those
frames come from survey lines AI4Shipwrecks left entirely unannotated, so even
that is an upper bound."*

### Calibration

T = 2.722, fitted on validation. **ECE 0.218 → 0.089.** When the model says
70%, it approximately means 70%.

Measured across 259 real detections, calibrated confidence runs:

| | |
|---|---|
| median | 0.422 |
| 90th percentile | 0.664 |
| **maximum** | **0.728** |

**The useful range is about 0.30 to 0.73.** A threshold set at 0.80 selects
nothing — it isn't strict, it's dead. This is the fact that broke three
different pieces of code before we wrote it down.

### Speed

**17.3 frames per second.** A 1,000-frame survey takes 1 minute; 10,000 takes
about 10. For context, a towfish pings 5–20 times a second and a frame is 640
pings, so **the pipeline is roughly a thousand times faster than data can be
collected.** Speed is not a constraint for us.

---

## Part 9 — What we built

The project splits into two halves, built by two people on two machines, meeting
at a frozen contract.

### Member 1 — the AI (`ai/`)

**`ai/ghostnet/` — 2,800 lines. This is the product; it ships inside the web app.**

| Module | What it does |
|---|---|
| `infer.py` | `detect()` — the single function the web app calls |
| `survey.py` | `detect_survey()` — a whole XTF file → frames → detections |
| `xtf.py` | Reads real sonar files and extracts navigation from ping headers |
| `geo.py` | Slant range → ground range → latitude/longitude, plus error radius |
| `decision.py` | Calibration and the report/suppress policy |
| `shadow.py` | Acoustic-shadow evidence for a reviewer |
| `dropout.py` | Flags detections standing on dead sonar |
| `preprocess.py` | Speckle suppression |
| `taxonomy.py` | The three class vocabularies and the mapping between them |
| `contract.py` | The frozen output shape |
| `report.py` | CSV export |

**`ai/scripts/` — 6,300 lines across 25 scripts. This is the factory; it does
not ship.** Dataset importers (one per annotation format), the dataset builder,
the trainer, calibration fitting, false-alarm evaluation, annotation tooling,
demo builders.

That split is normal and healthy: `train.py` built the model, but no production
system runs it. Those scripts are also the reproducibility evidence — the thing
a judge asks about when they want to know whether the numbers are real.

**`ai/tests/` — 235 tests, all passing.**

### Member 2 — the web application

FastAPI backend, Next.js frontend, PostgreSQL with PostGIS (a geographic
extension). 22 API routes. Surveys, file upload, processing jobs, detections,
review workflow, a GIS map with vessel-track playback, reports, dashboard,
login, live progress over websockets. 32 tests passing.

### How the two halves meet

The web app does `pip install -e ai/` and calls:

```python
from ghostnet import detect, warmup
result = detect(image_path, survey_meta)
```

No HTTP service, because the demo runs on one machine. `detect()` is
contracted **never to raise** — a missing model, missing metadata, an
unreadable image or a missing GPU all come back as a valid response with
`warnings` explaining what happened.

### The design principle worth understanding

**The system is built to degrade rather than fail, and to say so.**

- No navigation data → detection reported **without** coordinates, never invented
- Detection in the water column → position withheld, uncertainty widened
- Unreadable image → a warning, not a crash and not a fake "clean" result
- Corrupt calibration file → says so, rather than silently using raw scores
- Wrong metadata units → refuses the substitution and reports no position

That last one matters most. `depth` is not `altitude`, and using one for the
other doesn't degrade a position — it **corrupts** it, producing a map that
looks right and is wrong by a variable amount. **A missing pin is recoverable; a
confidently wrong pin is not.**

---

## Part 10 — Things deliberately not done

Being able to explain *why not* is worth as much as the features.

| Not done | Why |
|---|---|
| Segmentation masks | Cut for time. Boxes are enough for the task. |
| TensorRT / model export | Cut. 4 GB VRAM, and speed already 1,000× faster than needed. |
| A bigger model | Data is the limit, not capacity. |
| JSF file reading | No JSF sample to test against. |
| Diffusion-generated data | A research project; multiplicative compositing did the job in an afternoon. |
| Duplicate-detection suppression across tile seams | Needs matching in survey coordinates. An object on a seam can be reported twice. |
| RBAC, audit trails, disaster recovery, 26 database tables | The original plan called for these. They earn no marks and cost weeks. |

---

## Part 11 — Where everything lives

```
E:\New folder\                     ← the AI repo (Member 1)
├── ai/
│   ├── ghostnet/                  the shipping package
│   ├── scripts/                   importers, training, evaluation
│   ├── tests/                     235 tests
│   ├── data/
│   │   ├── raw/research/           downloaded datasets, untouched
│   │   ├── interim/                converted to a common format
│   │   ├── processed/              the merged train/val/test dataset
│   │   ├── annotate/               images we hand-annotated
│   │   └── provenance/             the dataset claims registry
│   ├── models/trained/ghostnet.pt  the shipped model (+ .json sidecar)
│   └── experiments/                every training run and its results
├── contracts/                      generated JSON schemas
├── docs/                           see below
└── PROJECT_PRIMER.md               this file

E:\SIH-Debries-rudra\               ← the web app (Member 2)
```

| Document | Read it for |
|---|---|
| `docs/HANDOFF.md` | The contract, for Member 2. **The two score scales are in §3b.** |
| `docs/AI_TRAINING_HANDOFF.md` | Model status, rules, traps already hit |
| `docs/COMMANDS.md` | Every command |
| `docs/DATA.md` | Dataset sourcing and licences |
| `docs/READING_RESULTS.md` | How to interpret the output |
| `docs/TESTING_GUIDE.md` | How to test it |

**Weights are not in git** (too large). `ghostnet.pt` **and** `ghostnet.json`
must travel together — without the sidecar, provenance silently reports
`v0-stub`.

---

## Part 12 — Commands you'll actually use

```powershell
$PY = ".\.venv\Scripts\python.exe"

# Run the model on your own images
& $PY ai/scripts/try_model.py --images "E:/demo-tiles" --weights ai/models/trained/ghostnet.pt

# Get test tiles that definitely contain something
& $PY ai/scripts/pick_samples.py --class ghost_pot --n 12 --out "E:/demo-tiles"

# The tests
& $PY -m pytest ai/tests -q

# Check the contract schemas haven't drifted
& $PY ai/scripts/export_schemas.py --check

# Train (train → calibrate → false-alarm curve, unattended)
powershell -ExecutionPolicy Bypass -File .\ai\scripts\train_all.ps1 -Name gv7 -Epochs 60
```

**Always pass `--weights` explicitly.** The default picks the newest run's
checkpoint — which, while a run is in progress, is a half-trained model.

---

## Part 13 — What to say, and what not to say

### Fair to claim

- "Detects derelict crab pots in real side-scan sonar" — with the per-class mAP50 and its box count
- "At the deployed operating point, 7.8% of unannotated seabed frames show a reviewer at least one box — an upper bound"
- "Reports position with an error radius, or no position at all when navigation data is missing"
- "Calibrated confidence: expected calibration error 0.089, down from 0.218"
- "Reads raw XTF sonar files and derives its own survey geometry"

### Never claim

- **Don't call a crab pot a ghost net.** It's fishing gear; it isn't a net.
- **Don't quote `plane` or the old `ghost_net` numbers** — 9 and 36 test boxes.
- **Don't say "verified-empty seabed."** Say "carrying no annotation."
- **Don't quote `debris` 0.869 without saying** 615 of 629 test boxes are one pipeline survey.
- **Don't quote a threshold without saying which scale** it's on.
- **Don't present `ghost_net` improvements without disclosing** the training data is largely synthetic.

### The thing that actually distinguishes this project

The accuracy numbers are modest, and with this much public sonar data they
always will be. What is genuinely unusual is that **the system says "I don't
know" in specific, measured ways** — calibrated confidence, a published
false-alarm rate, error radii instead of pins, a refusal to invent coordinates,
and a warnings channel that explains everything odd on screen.

Plenty of projects can show a demo that works. Very few can show you exactly
where and why theirs doesn't. **That is the thing to lead with.**
