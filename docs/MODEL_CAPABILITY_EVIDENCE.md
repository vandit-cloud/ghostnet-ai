# What this model can and cannot do

**Model `gv5-yolo11s`, promoted to `ai/models/trained/ghostnet.pt`.**
Every number below is on the held-out test split -- 4,346 frames, 2,077
labelled objects, 2,930 frames carrying no annotation -- and every one is
reproducible with the command beside it.

Nothing here is rounded in the project's favour. Where a number looks good for
the wrong reason, that is said in the same paragraph.

---

## The headline

```
test mAP50 0.352    mAP50-95 0.200    precision 0.580    recall 0.361
```

Trajectory on the same frozen split, which is the honest answer to "is this
going anywhere":

| run | mAP50 | precision | recall |
|---|---|---|---|
| gv | 0.160 | 0.140 | 0.285 |
| gv2 | 0.132 | 0.451 | 0.178 |
| gv4 | 0.247 | 0.191 | 0.362 |
| **gv5** | **0.352** | **0.580** | 0.361 |

Reproduce: `python ai/scripts/train.py` writes `test_metrics.json` at the end
of every run; gv5's is in `ai/experiments/gv5-yolo11s/`.

---

## Per class -- where it works and where it does not

| Class | Train | Test | mAP50 | What that means |
|---|---|---|---|---|
| `debris` | 1,556 | 629 | **0.870** | Works, with a large caveat below |
| `ghost_pot` | 7,434 | 567 | 0.314 | Works. The only class with enough data. |
| `plane` | 39 | 9 | 0.293 | Recall 0.333, up from 0.000. Nine boxes: not a result. |
| `wreck` | 1,373 | 836 | 0.279 | Weak *as averaged*. Read the size breakdown below before quoting it. |
| `ghost_net` | 215 | 36 | **0.009** | **Does not work.** Recall 0.000. |

### `wreck` 0.279 is two populations averaged together — added 2026-09-13

Recall on the test split, split by how much of the frame the object occupies
(`ai/scripts/recall_by_size.py`, deployed operating point conf 0.25, IoU 0.5):

| object size | found | total | recall |
|---|---|---|---|
| <0.2% of frame | 16 | 143 | 0.112 |
| 0.2–0.5% | 11 | 184 | 0.060 |
| 0.5–2% | 13 | 174 | 0.075 |
| **>2%** | **176** | **335** | **0.525** |
| all | 216 | 836 | 0.258 |

**On wrecks large enough to identify, recall is 0.525.** 501 of 836 test boxes
are under 2% of frame and the model finds roughly 8% of those, which is what
drags the average to 0.26.

Those small boxes are not sloppy annotation. AI4Shipwrecks ships **pixel-wise
masks**; `masks_to_yolo.py` derives our boxes from them, so they are tight by
construction and were never hand-drawn.

**Nor are they tiling debris — corrected 2026-09-13.** That was this document's
first explanation and it does not survive the test. A fragment cut by the tile
grid must touch the boundary that cut it, so splitting recall by edge-contact
separates cut fragments from genuinely small objects:

| size | at tile edge | interior |
|---|---|---|
| >2% | 0.522 | 0.533 |
| 0.5–2% | 0.075 | 0.074 |
| <0.5% | 0.000 | 0.097 |

Edge position makes no difference, and **279 of 327 small test boxes are
interior** — 85% were never cut by anything. Size is the whole effect.

So this is a genuine **small-object detection gap**, not a dataset artefact.
The boxes are real, correctly drawn, and the model cannot find them: at 0.5% of
a 640×640 tile an object is roughly 45×45 px. Filtering them out of the dataset
would be removing the evidence of a real weakness, not cleaning data.

**How to quote this.** "Recall 0.525 on wrecks larger than 2% of frame; 0.26
averaged over a test set in which 60% of wreck boxes are sub-2% tiling
fragments." Quoting 0.525 alone would be selecting a favourable subset after
the fact; quoting 0.26 alone reports the tiling grid as if it were the detector.

This still retires the standing hypothesis in EXPERIMENT_GV7_PLAN.md §2 that
`wreck` precision smells of label noise and needs a human audit. A triage pass
over train/val (`ai/scripts/rank_label_suspects.py`) flagged 446 findings whose
median flagged box is 0.245% of frame — the same small objects. The labels are
fine; the model cannot resolve objects that size.

**The fix is therefore a modelling one, not a data one**: input resolution, or a
higher-resolution detection head (P2, stride 4). Both are directly testable and
target a measured cause.

### `debris` 0.870 must never be quoted bare

615 of those 629 test boxes come from a **held-out stretch of the same SubPipe
survey** as the training boxes: same AUV, same sonar, same pipeline, separated
only by a 156-second gap in the timestamps. It measures whether the model can
follow a pipeline through seabed it has not seen. It does **not** measure
generalisation to debris elsewhere.

The only independent debris is **14 boxes** from sonar_detect.[^sonardetect] Report both, or
say "one held-out survey track".

### `ghost_net` does not work **as a box detector** — superseded in part, 2026-09-13

Everything in this section remains true of the **box** formulation and of the
shipped gv5 detector. It is no longer the whole story: under a *segmentation*
formulation the class reaches box recall 0.492 ± 0.074 and a centroid detection
rate of 0.607 ± 0.031 across three seeds (`gv7d3`, see
`docs/D2_SEGMENTATION_SUMMARY.md` and EXPERIMENT_GV7_PLAN.md §12).

**Update, 26 Sep:** a U-Net trained with empty-seabed negatives (`gvU1n`, three
seeds) beats gv7d3 on the same 11 chips: Dice 0.600 ± 0.011 against 0.525,
centroid detection rate 0.807 ± 0.042 against 0.607 (paired bootstrap 95% CI on
the gain [+0.105, +0.325]), and it fires on 1.3% of empty chips against 42%.
Seed 1 now outlines `ghost_net` in the app, review-only
(`ai/experiments/unet-scoring/RESULTS.md`, `docs/HANDOFF.md`).

That result is measured on **11 chips from 2 sites** and remains Tier 1 —
review-queue only, never a detection claim — so this section's conclusion stands
for anything gv5 ships. Do not quote the segmentation numbers without their
caveat, and do not quote this section as if the segmentation result did not
exist.

mAP50 0.009, recall 0.000. Its precision reads 1.000 and means nothing -- the
model made almost no net predictions at all. 215 training boxes over 51 images
is not enough for the hardest target in the set: `ghost_pot` needed 7,434 to
reach 0.314, and a net is thin, faint and spatially diffuse where a pot is
compact and bright.

**What may be claimed:** *"We produced the first annotated ghost-net dataset
from public side-scan sonar -- 298 boxes over 73 chips, with a documented
convention. At 215 training boxes the detector does not yet learn the class."*

**What may not:** that it detects ghost nets.

---

## The strongest result: telling artificial from natural

This is the problem statement's own framing, and it is where the model is
genuinely good.

On 2,930 held-out frames carrying **no annotation**, at the deployed operating
point (detector floor raw 0.10, which is calibrated 0.308):

```
7.8% of empty frames put at least one box in front of a reviewer
```

Reproduce: `python ai/scripts/evaluate_background.py` (the raw 0.10 row, 229
of 2,930; the full sweep is in `docs/AI_TRAINING_HANDOFF.md`).

Raise the floor and it falls steeply, at a measured cost in recall. This sweep
is by calibrated floor, taken with the detector floor lowered to 0.02 so the
low rows exist at all:

| calibrated floor | recall | recall retained | false alarms |
|---|---|---|---|
| 0.20 | 0.670 | 98.9% | 16.48% |
| 0.25 | 0.606 | 89.4% | 11.81% |
| 0.30 | 0.534 | 78.8% | 8.29% |
| *0.308 (deployed)* | | | *7.82%* |
| 0.35 | 0.464 | 68.4% | 5.15% |
| 0.40 | 0.408 | 60.3% | 2.94% |

Reproduce: `python ai/scripts/derive_review_floor.py`

**Two traps in that number.** "No annotation" is not "verified empty" -- some
frames come from survey lines the source dataset never annotated at all, so
7.8% is an upper bound. And the calibrated 0.20 review floor in the config is
**inert**: the detector is never asked for boxes below raw 0.10, and raw 0.10
is already calibrated 0.308. The 0.20 and 0.25 rows describe a detector floor
that does not ship, so 16.5% is not the deployed rate -- an earlier version of
this page said it was. The two sweeps agree: 7.82% at calibrated 0.308 sits
just under 8.29% at 0.30.

The negatives it is scored against are deliberately hard: 2,072 China-Offshore
frames of gully fields, riprap, scour patches and sand waves -- the natural
features most easily mistaken for man-made objects.

---

## Confidence means something

Temperature scaling, fitted on validation, applied to every reported score:

```
expected calibration error   0.218 -> 0.089
```

When the model says 0.7, it is right about 70% of the time. Raw YOLO scores are
not probabilities and are systematically overconfident; nothing in the shipped
path exposes them.

---

## Where it breaks -- tested deliberately

### Non-sonar input

| input | detections | verdict |
|---|---|---|
| flat grey, gradient, random noise | 0 | correctly rejects |
| simulated desk photo | 0 | correctly rejects |
| text document screenshot | 2 @ 0.45 | **fails** -- now warned about |
| synthetic nautical chart | 3 @ 0.46 | **fails**, and not caught |

A greyscale, unsaturated chart still gets through. The frame is flagged when
more than 35% of it is near-pure white, which catches the screenshot and
nothing in 400 real sonar tiles -- but one statistic does not solve non-sonar
rejection, so it **warns rather than blocks**.

### Degradation

Measured on the full 4,346-frame test split (`ai/scripts/robustness_report.py`,
26 Sep; the clean row reproduces gv5's record exactly):

| condition | mAP50 | recall | false alarms on empty seabed |
|---|---|---|---|
| clean | 0.352 | 0.361 | 7.82% |
| speckle 0.20 / 0.35 / 0.50 | 0.310 / 0.263 / 0.221 | 0.316 / 0.246 / 0.212 | 4.91% / 2.32% / 1.37% |
| contrast 0.5x / 0.25x | 0.305 / 0.085 | 0.313 / 0.115 | 5.84% / 3.65% |
| blur kernel 9 / 21 | 0.206 / 0.061 | 0.228 / 0.083 | **9.97%** / 5.80% |
| 10% of rows dropped | 0.099 | 0.243 | **26.42%** |

Two failure modes. Speckle, low contrast and heavy blur make the model **quiet**:
recall and false alarms fall together, so a bad survey reads as an empty one.
Dropped rows make it **loud**: false alarms more than triple. An earlier version
of this page quoted a single-tile curve ("speckle kills it at 0.35, blur barely
hurts"); the full split says the opposite on both counts. Details and per-class
rows: `ai/experiments/robustness/REPORT.md` and `notes.md`.

### Out of distribution

On 24 KLSG frames from a survey nothing in training resembles: 9 of 16
shipwreck frames produced detections, **all labelled `debris`, none `wreck`**;
0 of 8 aircraft frames produced anything. The aircraft result is expected at 39
training boxes. The wreck-as-debris confusion on a new source is not, and is
the most substantive open question about the model.

### Domain

Held-out test frames come from the same surveys as training -- same sonar, same
water, same gear. That is genuine generalisation, but within one domain. Expect
a large drop on a different sonar. Say so before being asked.

---

## Things the model is not asked to do alone

These are handled around it, and are reported as evidence rather than acted on:

- **Acoustic shadow** -- `shadow_context` reports whether the flank away from
  nadir is darker than the near flank. Measured signal is modest (flank
  asymmetry 0.384 against 0.255 for a random pair) and it never suppresses a
  detection. Physics is respected: wrecks show it (+0.263), pipelines and nets
  do not (+0.014, +0.023), so "absent" is not doubt for a flat target.
- **Missing data** -- rows carrying no acoustic return are found and any
  detection more than 25% on top of them has its uncertainty widened.
- **Position** -- slant-range corrected, with an error radius, or no position
  at all when navigation is missing. Never a coordinate the geometry cannot
  support.

---

## Reproducing any of this

```powershell
python ai\scripts\pick_samples.py --class any --n 20 --out E:\sonar-test
python ai\scripts\try_model.py --images E:\sonar-test        # + report.csv
python ai\scripts\derive_review_floor.py                     # the floor curve
start ai\experiments\gv5-yolo11s\testbench.html              # 14 real cases
```

`testbench.html` is the one to open first. It holds 5 hits, 3 misses, 3 correct
rejections of empty seabed and 3 false positives, with a live confidence
slider. It is not a highlight reel -- the failures are in there on purpose,
because a reviewer who has seen the failure modes can build a UI that handles
them.

[^sonardetect]: Reviewed frame by frame on 26 Sep 2026 (`ai/experiments/sonardetect-review/REVIEW.md`). 7 of these 14 boxes are in two frames that are not clean sonar: `SONARDETECT__000163` is a slide with photographs and `SONARDETECT__000183` is a composed figure with a zoomed inset. They stay in the test split, so every run remains scored on the same data, but only **7 boxes from 5 frames** are clean independent debris. Quote it as "14 boxes, 7 of them from clean frames".
