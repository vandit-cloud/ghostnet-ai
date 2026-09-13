# gv7 — plan and measurement design

**Status as of 2026-09-13. `gv5-yolo11s` is and remains the shipped model** —
no §6 promotion criterion has been met, and none of the main-track runs that
could meet one has been attempted.

| run | state |
|---|---|
| gv7.0 — re-score gv5 on the current split | **done.** Ruler reproduces to 4 dp; noise floor ±0.002 |
| gv7.T — test-time augmentation | **done. NEGATIVE**, rejected on its recall trade |
| gv7.1 — label audit | **retired.** §13.4: the premise was wrong, see recall_by_size.py |
| gv7.2 — SSL backbone | not started; no implementation, multi-day |
| gv7.3 — pseudo-labelling | **not startable** — no unlabelled pool exists (§2 note) |
| Track B / Track C | not started |
| Track D0 — real net eval set | **blocked on external data** |
| Track D2/D3 — segmentation, despeckle | **done.** §12 and the gv7d run |
| D-geom rect tiling | **closed.** §13 — inapplicable, and rect costs mosaic |

This document is written to be pre-registered: the promotion criteria, the
guardrails and the minimum detectable effects are all fixed *before* any run, so
"it improved" is a decision rule rather than an argument after the fact. That is
the same discipline that made `docs/EXPERIMENT_GV6.md` a usable negative result.
Sections added after a run says so in its own heading, and amendments are dated
in place rather than rewritten over.

**gv7.3 note, 2026-09-13.** The run design assumes a pool of unlabelled sonar to
pseudo-label. There is none: `ai/data/raw/` holds 135 images, all of them
hand-labelled (73 net chips, 62 plane). The same pruning that blocked D1 (§10.2.2)
took gv7.3's input with it. Sourcing that pool is a prerequisite nobody has
costed, and gv5 is a poor teacher for it regardless — it emits zero `ghost_net`
predictions and misclassifies 6 of 7 aircraft, so its pseudo-labels would
reinforce precisely the two failures the cycle exists to fix.

---

## 0. What gv5 actually looks like, so gv7 has a target

Held-out test split, 4,346 frames:

| class | n | precision | recall | mAP50 |
|---|---|---|---|---|
| debris | 629 | 0.798 | 0.855 | **0.869** |
| ghost_pot | 567 | 0.377 | 0.295 | 0.314 |
| wreck | 836 | 0.423 | 0.315 | 0.279 |
| plane | **9** | 0.355 | 0.333 | 0.292 |
| ghost_net | 36 | 1.000 | **0.000** | 0.009 |
| **overall** | 4,346 | 0.580 | 0.361 | 0.352 |

Two things follow, and they shape the whole plan:

1. **`debris` carries the headline.** Remove it and overall mAP50 falls to
   roughly 0.22. `debris` is mostly SubPipe pipelines — large, linear,
   high-contrast. "Improve the model" therefore means *improve `wreck` and
   `ghost_pot`*, which is where the mass of measurable held-out data is
   (836 and 567 boxes).
2. **`ghost_net` is not a *synthetic*-data problem.** — amended 2026-09-05;
   the earlier wording, "not a data problem", was overstated and is corrected
   here. gv6 took the class from 215 to 2,246 training boxes and recall moved
   0.000 → 0.000, but a label-file audit shows that increase was **1,364
   synthetic images against 51 real ones**. Real hand-labelled net imagery in
   the whole dataset is **73 images from two Chinese sites** (train 48 quanzhou
   + 3 yantai = 51, val 11, test 11). So what gv6 disproved is synthetic volume.
   Real net data at scale has never been tested, because it has never existed
   here. The physics still explains *why* nets are hard — flat, shadowless,
   low-contrast, one weak acoustic cue, no shadow to pair it with — but physics
   alone does not close the question, and external evidence now says the
   formulation matters more (§10, Track D).

   `ghost_net` remains **excluded from gv7.1–7.3 success criteria** and is
   pursued separately as Track D, so the main cycle is not held hostage to it.

---

## 1. Isolation and reversibility — read this before running anything

The requirement: **gv7 must not be able to damage gv5, at any point, even if
every run fails.** Today it can, and one mechanism is a live footgun rather
than a discipline problem.

### 1.1 The footgun, and the one-line fix that must land first

`ai/scripts/fit_calibration.py:45` hardcodes its output:

```python
CALIBRATOR = AI_ROOT / "models" / "calibrator"      # writer: hardcoded
...
out = CALIBRATOR / "temperature.json"
```

but the reader honours an environment override:

```python
# ghostnet/decision.py:59
path = Path(settings.models_dir) / "calibrator" / "temperature.json"
# config.py:62  models_dir <- GHOSTNET_MODELS_DIR
```

So `fit_calibration.py --weights <an experiment>` **overwrites the shipped
model's calibration regardless of any environment variable you set.** This is
exactly what happened in gv6 — the temperature was refitted against gv6 weights
while `ghostnet.pt` was still gv5, and had to be reverted by hand.

**Prerequisite P1 — LANDED 2026-09-05, commit `fc60e87`.** No longer
outstanding; this subsection is kept because the *reasoning* still governs how
every gv7 run is set up. `fit_calibration.py` now resolves its output through
`calibrator_dir()`, which honours `GHOSTNET_MODELS_DIR` and is resolved at call
time rather than at import, and an explicit `--out` argument was added as well.
Guarded by `ai/tests/test_run_guards.py` (14 tests, passing), which asserts the
writer does not touch `ai/models/calibrator/` when the override is set.

The hardcoded `CALIBRATOR` constant quoted above no longer exists. Do not
re-apply this fix; do still honour the isolation recipe in 1.2.

### 1.2 The isolation recipe

Every gv7 evaluation runs against experiment-local artefacts. No step writes
into `ai/models/`.

```bash
export GHOSTNET_WEIGHTS="ai/experiments/gv7.1-yolo11s/weights/best.pt"
export GHOSTNET_MODELS_DIR="ai/experiments/gv7.1-yolo11s/models"
```

* `GHOSTNET_WEIGHTS` already wins over the promoted model
  (`config.py.__post_init__`), so nothing reads `ghostnet.pt`.
* `GHOSTNET_MODELS_DIR` redirects the calibrator **read**; P1 makes it redirect
  the **write** too.
* `train.py` already writes only to `ai/experiments/<name>/`. It never touches
  `models/trained/`.

### 1.3 Backup before the first run

Cheap, and it makes every later step reversible by copy rather than by rebuild:

```
ai/models/_rollback/2026-09-05-gv5/
    ghostnet.pt
    ghostnet.json          # the promotion sidecar: source path + hash
    temperature.json
    review_floor.json      # whatever derive_review_floor.py produced
```

Record the SHA-256 of each file in a `MANIFEST.txt` beside them. Rollback is
then "copy these four files back and verify the hashes", which is checkable
rather than hopeful.

### 1.4 Promotion is a single ordered transaction

Promotion happens **once**, only after section 6 passes, and in this order.
Doing it out of order is what produces a model scored with someone else's
temperature:

1. Copy `experiments/<run>/weights/best.pt` → `models/trained/ghostnet.pt`
2. Write the sidecar `models/trained/ghostnet.json` — source path, run name,
   SHA-256, dataset_version, git commit
3. **Then** `fit_calibration.py --weights models/trained/ghostnet.pt` (the
   promoted path, not the experiment path)
4. **Then** `derive_review_floor.py --weights models/trained/ghostnet.pt`
5. Re-run both test suites and the app smoke test
6. Commit all four artefacts together in one commit, message naming the run

If any step fails, restore from `_rollback/` and stop. Never leave the tree with
new weights and an old temperature.

### 1.5 The dataset must not drift underneath the comparison

`ai/data/processed/build_report.json` carries
`dataset_version = 8src-12472/1492/4346-ee2f4b940bc1`. Every gv7 run asserts
this hash matches gv5's **for the test split** before training starts. A run
that cannot assert it is not comparable and must say so in its own report.

---

## 2. What gv7 merges, and what it deliberately leaves out

From the approaches surveyed, ranked by expected value against *this* model's
measured failures rather than in general:

| approach | in gv7? | why |
|---|---|---|
| Data-centric iteration | **yes — first** | cheapest, and `wreck` at P 0.42 smells of label noise |
| Self-supervised pretraining | **yes — core** | backbone is ImageNet-pretrained; sonar shares almost no low-level statistics with photographs |
| Semi-supervised pseudo-labelling | **yes — third** | pairs naturally with SSL; uses unlabelled sonar twice |
| Ensembling / TTA | **yes — free** | inference-only, no retrain, measurable independently |
| Transfer learning | already doing | baseline |
| Active learning | **no, this cycle** | the uncertainty ranking exists but the human labelling loop is the cost, and there is no labelling capacity budgeted |
| Weak supervision | **no** | Snorkel-scale machinery for 5 classes is not worth it |
| Physics-based simulation | **no** | expensive; revisit only if SSL underdelivers |
| LoRA adapters | **no, this cycle** | relevant when swapping to a foundation backbone — a gv8 question |

Two additions that are **not** from that table but target the measured failure
directly, kept as separate tracks so attribution survives:

* **Track B — two-stage crop classifier.** 6 of 7 aircraft are called `wreck`
  while the *boxes land correctly*. That is a classification failure, not a
  detection failure, and a small classifier on high-resolution crops with
  balanced sampling fixes it far more cheaply than retraining a detector. It
  also sidesteps the 4 GB ceiling, because crops are small.
* **Track C — physics as input channels.** Shadow mask, range-normalised
  amplitude and incidence angle stacked as extra input channels, so the network
  learns "blob AND shadow at this geometry" rather than rediscovering it from
  pixels. This is the honest, sensor-native form of "give the model
  instructions". It changes the input channel count, so it is the most invasive
  change here and goes last.

---

## 3. Run design — staged, so the merge is still attributable

Merging everything into one run buys a number nobody can explain. Each stage
adds **one** variable and inherits the previous stage's data.

| run | change vs previous | isolates |
|---|---|---|
| **gv7.0** | none — re-evaluate gv5 on the current test split | the ruler itself |
| **gv7.1** | label audit applied to **train/val only** | label quality |
| **gv7.2** | + SSL-pretrained backbone | domain pretraining |
| **gv7.3** | + pseudo-labelled unlabelled frames | semi-supervision |
| **gv7.T** | TTA at inference on the best of the above — **no retraining** | test-time augmentation |
| **Track B** | crop classifier behind the gv5 detector | fine-class accuracy |
| **Track C** | physics input channels | prior injection |

`wreck`, `debris` and `ghost_pot` are the reported classes. `plane` and
`ghost_net` are **controls only** and may not be quoted as evidence — see 4.3.

### 3.1 The label-audit trap, and how to avoid poisoning the ruler

Cleaning train/val labels while the test split keeps the same errors means
measuring a better model with a worse ruler. But changing the test split breaks
comparability with gv1–gv6.

The resolution: **if a test-set audit is done, it is a separate, announced,
one-time event, and gv5 is re-scored on the corrected test set too** (that is
what gv7.0 is for). Both models are then measured on the same ruler and the
comparison is honest. Never audit test silently mid-cycle.

### 3.2 Cost, and why the cheap thing runs first

At ~860 s/epoch × 60 epochs, one detector run is ~14 h on this GPU. SSL
pretraining is a multi-day job at 4 GB. So:

**gv7.1 runs first and alone.** It is one training run and a labelling pass. If
label cleanup alone moves `wreck` recall past the threshold in section 4, that
is a large finding for a small cost, and it changes what SSL is being asked to
do. Gate the expensive work on the cheap measurement.

---

## 4. Measurement design

### 4.1 Frozen ruler

* Test split byte-identical, `dataset_version` asserted before training.
* Same evaluation command, same `imgsz`, same IoU thresholds as gv5.
* Metrics reported at **matched raw threshold**, not matched calibrated
  threshold — temperature differs per run and would otherwise silently move the
  operating point (gv6, §2).

### 4.2 Metrics, in priority order

**Primary:** `wreck` mAP50 and `ghost_pot` mAP50. These are the two classes with
enough held-out data to support a claim and enough headroom to be worth the run.

**Secondary:** overall mAP50; overall precision/recall.

**Guardrails — a run fails if any of these regress beyond tolerance:**

| guardrail | gv5 value | fail if |
|---|---|---|
| background activation rate @ raw 0.20 | 4.1% | > 5.1% (see 4.4) |
| `debris` mAP50 | 0.869 | < 0.84 |
| overall precision | 0.580 | < 0.52 |
| calibration ECE | 0.118 | > 0.15 |

gv6 is the cautionary case: +0.021 overall mAP50 bought with a precision
collapse 0.580 → 0.373 and 1.6× background activations. Guardrails exist so that
trade is refused automatically rather than argued about.

### 4.3 Minimum detectable effect — what the test set can and cannot see

Computed from the gv5 recall and n of each class. "MDE" is the smallest true
difference detectable at 80% power, two-sided, α = 0.05:

| class | n | recall granularity | 95% CI half-width | MDE (80% power) |
|---|---|---|---|---|
| debris | 629 | 0.0016 | ±0.027 | 0.056 |
| wreck | 836 | 0.0012 | ±0.031 | **0.064** |
| ghost_pot | 567 | 0.0018 | ±0.038 | **0.076** |
| ghost_net | 36 | 0.0278 | — (0 events) | can only bound: true recall < 0.083 |
| plane | **9** | **0.111** | ±0.308 | **0.622** |

Read those last two rows carefully:

* **`plane` cannot be measured at all.** Recall moves in steps of 0.111, and
  detecting a real change needs a 62-point swing. gv6's apparent `plane`
  improvement was recall 0.3333 → 0.3333 — the same 3 of 9 aircraft, re-ranked.
  **`plane` must not be quoted as evidence for or against gv7.** Track B is the
  right response to the aircraft problem, and it must be validated on a
  purpose-built crop set, not on n=9.
* **`ghost_net` supports only an upper bound.** With 0 of 36 found, the rule of
  three gives 95% confidence that true recall is below 8.3%. That is the only
  honest statement available, and it is the one to make.

**Decision rule:** a per-class change smaller than that class's MDE is reported
as "no measurable change", never as an improvement.

### 4.4 Confidence intervals on the background rate

The background set is n = 2,930 tiles carrying no annotation, so the false-alarm
rate is tight: ±0.010 at 7.8%, ±0.007 at 4.1%, ±0.006 at 2.9%. The 1-point
guardrail tolerance in 4.2 is therefore roughly 1.4 CI widths — deliberately
loose enough not to trip on noise, tight enough to catch a gv6-scale regression.

Phrase this metric as **"tiles carrying no annotation"**, never "verified-empty
seabed" (`READING_RESULTS.md` Part 3b).

### 4.5 Bootstrap, because single numbers hide variance

Report every primary metric with a 95% bootstrap CI over 1,000 resamples of the
test frames. A point estimate that moves inside its own CI has not moved.

### 4.6 Seeds

Each promoted candidate is re-run at **three seeds**. If the primary metric's
spread across seeds exceeds the MDE, the effect is seed noise and the run does
not promote. One seed is an anecdote.

---

## 5. What each stage must produce

Every run writes, into `ai/experiments/<run>/`:

* `test_metrics.json` — overall and per class, matching gv5's schema
* `background_metrics.json` — activation rate at raw 0.10 / 0.20 / 0.25
* `provenance.json` — git commit, dataset_version, seed, full CLI
* `calibration.json` — the run's own temperature, **written run-local**
* `notes.md` — what changed, what moved, what did not, in that order

A run with no `notes.md` is not a result.

---

## 6. Pre-registered promotion criteria

gv7 promotes over gv5 **only if all of the following hold**, on three seeds:

1. `wreck` mAP50 improves by ≥ 0.064 (its MDE), **or** `ghost_pot` mAP50
   improves by ≥ 0.076, and
2. no guardrail in 4.2 is breached, and
3. overall precision does not fall below 0.52, and
4. the improvement survives bootstrap CIs that do not overlap gv5's, and
5. the dataset hash assertion passed.

Anything else is a documented negative result, kept in `docs/`, and gv5 stays.
Being able to say "we ran it, here is what it cost, we did not ship it" is worth
more than a fractional mAP change — that is the gv6 precedent and it should be
the gv7 precedent too.

---

## 7. Rollback

At any point:

```bash
# restore the four shipped artefacts and verify
cp ai/models/_rollback/2026-09-05-gv5/{ghostnet.pt,ghostnet.json} ai/models/trained/
cp ai/models/_rollback/2026-09-05-gv5/temperature.json ai/models/calibrator/
sha256sum -c ai/models/_rollback/2026-09-05-gv5/MANIFEST.txt
```

Then re-run both suites and one app smoke run. Rollback is not complete until
`detect()` reports `model_version: gv5-yolo11s` again — check the provenance
block, not the filename, because `ghostnet.pt` is a copy and its name proves
nothing.

---

## 8. What not to try, carried forward from gv6

* **More synthetic nets.** Tested. Recall 0.000 → 0.000. (Still true. But see
  §10 — this rules out synthetic volume, not real net data, and not a change
  of task formulation.)
* **Nets by elimination** (anything not wreck/plane/debris/pot is a net). The
  residual bucket is mostly seabed; this destroys the false-alarm number six
  runs earned. The `unknown` contract class is the honest version.
* **Despeckling at inference only.** −13% mAP50 on gv5. A despeckle-*trained*
  model remains open, but train and inference must match — see
  `sih26057-transform-symmetry`.
* **Refitting the calibrator against experiment weights while `ghostnet.pt` is
  something else.** Section 1.1 exists because this already happened once.

---

## 9. Open questions to settle before starting

1. **Which SSL objective?** MAE is simple and strong but wants a ViT; DINO-style
   distillation can sit on the existing CNN backbone and is friendlier to 4 GB.
   Decide on VRAM, not on paper results.
2. **How much unlabelled sonar is actually reachable?** `ai/data/raw` is 229 MB
   after the prune. SSL wants far more than that. Sourcing this is a
   prerequisite, not a detail — if it cannot be sourced, gv7.2 does not run and
   the cycle is gv7.1 + Track B.
3. **Is a test-set label audit in scope?** It re-baselines every historical
   number. Worth doing once, but it must be a deliberate, announced decision
   (§3.1), not a side effect.

---

## 10. Track D — the `ghost_net` question, reopened

Added 2026-09-05 after an external-evidence review. Track D is **separate from
gv7.1–7.3** and does not gate them; it exists because two facts surfaced that
the original plan did not have.

### 10.1 The two facts

**Fact 1 — we have almost no real net data.** Counted from
`ai/data/processed/*/labels/`, class 4:

| split | images | boxes | composition |
|---|---|---|---|
| train | 1,415 | 2,246 | **1,364 synthetic**, 48 `quanzhou_HN`, 3 `yantai_HN` |
| val | 11 | 47 | 10 quanzhou, 1 yantai |
| test | 11 | 36 | 10 quanzhou, 1 yantai |

73 real images, two sites (51 train + 11 val + 11 test). See the amendment in §2.

**Fact 2 — someone solved this with barely more data than we have, by asking a
different question.** GhostNetZero (Microsoft AI for Good Lab, WWF Germany,
Accenture; tech report Sept 2025) reports **~90% ghost-net detection** trained
on **239 Baltic Sea + 173 Puget Sound annotated segments** — 412 real images.

Their choices differ from ours in four ways, and each is separately testable:

| | GhostNetZero | GhostNet-AI gv5 |
|---|---|---|
| task | semantic segmentation, DeepLabV3 + ResNet50 | bounding-box detection, YOLO11-S |
| patch | 2000×500 or 1000×250, resized to 2000×500 | **640×640 square** |
| channels | left/right SSS views split | single view |
| metric | **centroid detection rate** @ 3/5/10/20 px | mAP50 @ IoU 0.5 |
| despeckling | **none** | none at train; inference filter ships OFF |

Their stated reason for rejecting bounding boxes is the one that matters to us:
segmentation gives "more accurate localization... particularly important for
irregularly shaped ghost nets, such as those in string-like shapes."

Their combined BS+PS model: mIoU 0.739 / 0.685, centroid detection 0.891 /
0.929. Cross-region transfer was weak (BS-only scored 0.607 on PS), which is a
warning about our own two-site training data.

### 10.2 What Track D tests, cheapest first

| step | change | cost | rationale |
|---|---|---|---|
| **D0** | build a real net evaluation set | labelling, no GPU | prerequisite — see 10.3 |
| **D-geom** | **anisotropic tiles + segmentation head, merged** | ~1 day labelling + one run | one hypothesis, one run — see 10.2.1 |
| **D3** | despeckle-**trained** model | one training run — **already committed** | a *different* hypothesis; stays separate |
| **D5** | low-threshold net proposals → review queue | hours, no GPU | inference-layer; composes with any of the above |
| **D4** | texture / curvilinear input channels | invasive — **cut this cycle** | needs a custom model YAML + dataloader, and breaks pretrained first-conv loading |

### 10.2.1 Why D1 and D2 merge, against §3's default

§3 says merging buys a number nobody can explain, and that rule is right for
gv7.1–7.3. It does **not** hold here, for a reason specific to this class:

**Staged attribution requires an evaluation set that can resolve the stages.**
Ours cannot. Per §4.3, `ghost_net` at n=36 supports only an upper bound. Running
anisotropic tiling and a segmentation head as two separate 14-hour runs would
cost 28 GPU-hours to produce **two numbers neither of which is individually
interpretable**. Attribution you cannot measure is not attribution; it is just
a slower way to reach the same ambiguity.

They also test **the same hypothesis**: *the target's geometry is wrong for our
formulation.* A ghost net is a long, thin, string-like, fragmented object. Square
tiles cut it; axis-aligned boxes cannot describe it. Those are two symptoms of
one mismatch, and GhostNetZero changed both at once for the same reason.

So D-geom is one run: **1024×256 tiles, `rect=True`, `yolo11s-seg`.** If it
moves the needle, D0 then tells us by how much, and the stages can be
disentangled later *on an eval set that can actually see the difference*.

**D3 stays separate** because it is a genuinely different hypothesis — *the cue
is present but buried in speckle* — and merging it would confound two unrelated
explanations. It is also already committed as its own run.

### 10.2.2 D1 is BLOCKED, and partly inapplicable — found 2026-09-05

Two facts discovered while implementing it. Both are about our data, not the
idea, and the second is the more important one.

**Blocked: the source waterfalls are gone.** `ai/data/raw/` is down to 229 MB
holding only `GHOSTNET-HAND`, `PLANE-HAND` and `MGDS_Download` — the prune in
commit `ad70122` removed the AI4Shipwrecks, GhostVision, SubPipe and
China-Offshore originals. What survives in `ai/data/interim/` is **already
tiled to 640×640**. Re-tiling a tile is meaningless, so the dataset cannot be
rebuilt at another tile shape without re-downloading the sources.

**Inapplicable to nets anyway, which matters more.** The anisotropic-tile
argument assumes a net is a long feature spanning a large waterfall that we
then chop into squares. Our net data is not shaped like that. Every
`GHOSTNET-HAND` image is a small pre-cut chip — 486×373, 348×378, 359×501,
740×496 — handed to the detector whole. **Square tiling is not cutting our
nets, because our nets were never tiled.** The mechanism D1 was meant to fix is
not operating on this class.

So D1 does not run this cycle, and D-geom reduces to D2 (segmentation), which
is unaffected: a net inside a 486×373 chip is still a long, thin, fragmented
object that an axis-aligned box describes badly.

**What was still worth building.** `masks_to_yolo.py --tile` now accepts `HxW`
(`--tile 256x1024`), validated, tested and ready for the day sources exist
again or new survey data arrives. It is the correct default for *future* full
waterfalls, and it cost an hour. The residual idea for the current data —
training with `rect=True` so a 486×373 chip is not letterboxed into a square —
is cheap and can ride along with D2 rather than justifying its own run.

### 10.2.3 The rectangular-training trap, for whenever D1 does run

`imgsz=[1024,256]` **does not work.** `engine/trainer.py` calls
`check_imgsz(..., max_dim=1)`, which silently collapses a list to `max()` and
warns *"'train' and 'val' imgsz must be an integer"*. Verified against the
pinned `ultralytics 8.4.134`.

The working route is to cut anisotropic tiles **on disk** — give
`masks_to_yolo.py --tile` a `H×W` form — and train with `rect=True` and
`imgsz=1024` as the long side. `rect=True` is refused only for multi-GPU, so it
is fine on the single 3050. A 1024×256 tile is ~1.6× the pixels of 640×640, so
expect **batch 2–3** under the 4 GB ceiling.

**D2 has a real annotation cost we should not hide.** `masks_to_yolo.py` exists,
so masks-to-boxes is a solved path — but it runs on AI4Shipwrecks, which shipped
with masks. `ai/data/raw/research/GHOSTNET-HAND/` is `images/` + `labels/` only:
the net annotations were drawn as **boxes**, not masks. Segmentation therefore
means re-annotating 73 images as polygons. That is roughly a day, not a project,
and it is the single highest-information day available on this class.

**D3 note.** GhostNetZero reached ~90% with **no despeckling at all**, which
weakens the "speckle is burying the cue" hypothesis. This does not cancel the
run — different architecture, different data, and the −13% figure that ships the
filter OFF was inference-only and therefore a transform-symmetry violation
rather than a verdict. It does set expectations.

### 10.3 D0 is not optional, and it comes first

**An 11-image / 36-box test set from two sites cannot evaluate D-geom or D3.**
Per §4.3 it supports only a rule-of-three upper bound: true recall < 8.3%. A
real improvement to recall 0.15 would show as 5 of 36 boxes and be
indistinguishable from noise. Running D1–D4 against the current split produces
numbers nobody can interpret — the gv6 mistake in a new costume.

Sourcing routes found, in order of plausibility:

* **ghostnetzero.ai** is explicitly a data-*donation* platform — research
  institutes, authorities and offshore wind operators upload sonar to it. A
  two-way ask is plausible and costs an email.
* **MARELITT Baltic** deployed two authentic 400 m ghost-net fleets as a
  purpose-built **sonar testbed** off Simrishamn; 60+ net/line/cable targets
  were diver-ground-truthed. This is labelled net data that exists.
* **WWF Germany** holds the Baltic corpus behind the tech report.
* **Dead end, confirmed:** HuggingFace `PINGEcosystem/sss-crab-pot-detection-ds`
  is 6,674 images of crab pots with **no netting**, and at 6,674 vs our
  GhostVision 6,655 we almost certainly already have it.

### 10.4 A metric change worth adopting regardless

GhostNetZero argues that IoU-based metrics understate operational utility: you
only need to point a diver at the right spot, and three disconnected polygons
over one long net should count as one true positive, not two false ones. Their
**centroid detection rate** does exactly that.

Our `ghost_net` mAP50 of 0.009 is therefore *partly* a metric artefact for a
long, fragmented, string-like target. It does not rescue gv5 — recall was
0.000, meaning no predictions at all, and no metric repairs that — but any
Track D result should be reported under **both** mAP50 and a centroid detection
rate, or we will under-read a real improvement.

### 10.5 Promotion criterion for `ghost_net` — DECIDED 2026-09-05

The strict-vs-lenient framing was a false binary. It was hard to answer because
it bundled two different questions: *what may we ship?* and *what may we
claim?* Those have different risk profiles and deserve different bars.

**The rule: two tiers. Shipping is lenient. Claiming is strict.**

**Tier 1 — review-queue eligibility (lenient).** A `ghost_net` prediction never
asserts a detection. It enters the review queue as a candidate, surfaced under
the `unknown`/review vocabulary, and the UI must not render it the way a
`ghost_pot` detection is rendered. A Track D run earns Tier 1 if:

* it produces any non-zero `ghost_net` recall at the deployed operating point, and
* **no guardrail in §4.2 is breached** — in particular the background activation
  rate at raw 0.20 stays ≤ 5.1% and overall precision stays ≥ 0.52, and
* `debris`, `wreck` and `ghost_pot` mAP50 do not regress beyond §4.2 tolerance.

The bar is low on the net class *because the output makes no claim*. The bar
stays full-strength on everything else, because gv6's real damage was never its
net score — it was 1.6× background activations and precision 0.580 → 0.373
inflicted on the four classes that do work. That must not happen again, and
Tier 1 is the clause that prevents it.

**Tier 2 — detection claim (strict).** Before `ghost_net` may be quoted as a
working class — in the submission, to a jury, in `MODEL_CAPABILITY_EVIDENCE.md`,
or anywhere a number stands without a caveat — all of:

* a rebuilt evaluation set of **≥ 300 real net boxes from ≥ 3 sites** (D0), and
* recall **≥ 0.30** at the deployed operating point, and
* three seeds, with spread below the effect size, and
* a bootstrap 95% CI that does not overlap gv5's, and
* reported under **both** mAP50 and centroid detection rate (§10.4).

**Until Tier 2 passes, no `ghost_net` number may stand without its caveat.** The
honest public statement is the deliverable — it is not a failure to report, and
it is the same discipline that made `docs/EXPERIMENT_GV6.md` worth having.

**What that statement is — AMENDED 2026-09-13.** It used to be the rule-of-three
bound: *"with 0 of 36 found we are 95% confident true recall is below 8.3%."*
That described the **box** model, which emitted no net predictions at all. It no
longer describes the system and must not be quoted: the segmentation model finds
nets, and repeating the old bound now would understate our own result.

The current form, from `gv7d3` (three seeds, §12.1):

> Under a segmentation formulation, `ghost_net` reaches box recall 0.49 ± 0.07
> and a centroid detection rate of 0.61 ± 0.03 across three seeds. That is
> measured on **11 chips from 2 sites**, which cannot support a generalisation
> claim, so the class ships as a review candidate and not as a detection.

Both sentences are bounds. The old one bounded a model that found nothing; this
one bounds a result whose limit is the evaluation set rather than the model. The
discipline is unchanged — what moved is which thing is uncertain.

### 10.6 Tier 2 progress — 2026-09-13

| condition | state |
|---|---|
| ≥ 300 real net boxes from ≥ 3 sites (D0) | **NOT MET** — 59 instances, 2 sites |
| recall ≥ 0.30 at the deployed operating point | met — 0.492 |
| three seeds, spread below the effect size | met — `gv7d3`, spread 0.074 vs effect ~0.49 |
| bootstrap 95% CI not overlapping gv5's | not computed |
| reported under both mAP50 and centroid rate | met — §10.4 implemented |

Three of five, with a fourth cheap to compute. **The single blocker is D0, and
it is data, not modelling.** No training run can clear it: the requirement is a
third site, and the reason is GhostNetZero's own measured cross-region drop
(Baltic-trained, 0.607 on Puget Sound). With two sites on one coastline,
"the model learned nets" and "the model learned Chinese coastal seabed" predict
identical numbers on our test split and cannot be told apart.

**Why this way.** A single threshold would have forced a choice between
shipping nothing useful and claiming something unsupported. Splitting the tiers
lets a weak signal reach a human — which is exactly what GhostNetZero's
human-in-the-loop platform does with its own predictions — while keeping the
number we quote anchored to evidence we actually have.

---

## 11. D2 status — BUILT and ready to train (2026-09-06)

The annotation pass is complete and the dataset exists. Training has NOT been
started.

### 11.1 What was produced

**73 chips re-annotated as polygons: 425 polygons, every one valid.** Measured
against the boxes they replace:

| | old hand-drawn boxes | new polygons |
|---|---|---|
| shapes | ~4 per chip | 425 total |
| median frame area claimed as net | **56.5%** | **7.0%** |

An 8× reduction in seabed labelled as net. That over-claiming is the most
plausible mechanical reason the class trained to recall 0.000: most of what the
old boxes called `ghost_net` was empty seabed, so "seabed" was the majority of
the class's training signal.

Artefacts:

* `ai/data/annotate/ghost_net_seg/` — chips, labelme JSON, YOLO-seg labels,
  `HOW_TO_LABEL.md`, and `_guide/` review sheets
* `ai/scripts/labelme_to_yoloseg.py` (+ 7 tests) — polygon conversion
* `ai/scripts/build_net_seg_dataset.py` — dataset builder
* `ai/scripts/train_net_seg.py` — training entry point
* `ai/data/net_seg/` — `dataset_version: netseg-51/11/11-db1888319541`

### 11.2 Two design decisions worth keeping

**Single-class segmentation model, separate from gv5.** Ultralytics requires
every label in a segmentation dataset to be a polygon. The other four classes
exist only as boxes and the raw imagery to re-derive them was pruned in
`ad70122`. Converting those boxes to 4-point rectangles to satisfy the format
would teach the model that debris is rectangular — fake segmentation that
damages the classes which currently work. So `ghost_net` gets its own model and
gv5 keeps the other four unchanged.

**The split is inherited, never recomputed.** 51/11/11, read back from
`ai/data/processed/` by filename. Re-splitting 73 chips randomly would place a
chip in test that gv5 trained on, and every later comparison would be measuring
memorisation.

### 11.3 The comparison trap this creates

The 11 test chips now carry polygon labels. This is **not** the silent
test-set edit §3.1 warns against — it is a new ruler for a different task, and
the box-based detection ruler is untouched.

But **a segmentation score from this dataset is not comparable with gv5's
mAP50.** Different task, different label geometry, different metric. The caveat
is written into `data.yaml`, `build_report.json` and `provenance.json` because
someone will eventually put the two numbers side by side. At n=11 the honest
output remains an upper bound (§4.3), reported under Tier 1 of §10.5 as a
review candidate — never as a detection claim.

### 11.4 To start it

```bash
python ai/scripts/fetch_weights.py            # once, needs network
python ai/scripts/train_net_seg.py --dry-run  # confirms the plan
python ai/scripts/train_net_seg.py            # ~13 iters/epoch
```

`degrees=0` in that script is not a free choice: side-scan across-track is
RANGE, so a rotated tile is not an image the sonar can produce. Flips stay on —
`fliplr` is the port/starboard mirror, `flipud` is the vessel running the other
way, and both are real surveys.

---

## 12. D2 RESULT — run, seeded, and what it cost to get right (2026-09-13)

§11 ended at "BUILT and ready to train". It has now run four times: once as
`gv7d2b` (the result quoted in `docs/D2_SEGMENTATION_SUMMARY.md`), and then as
`gv7d3-netseg-s0/s1/s2`, three seeds under a corrected config.

### 12.1 The headline

Three seeds, 1000 epochs, early stopping off, dataset `netseg-51/11/11`, test
split asserted `test11-8835e2482d97`:

| metric | mean | sd | range |
|---|---|---|---|
| box recall | **0.492** | 0.074 | 0.441–0.576 |
| box mAP50 | 0.528 | 0.018 | 0.507–0.542 |
| mask mAP50 | 0.227 | 0.012 | 0.215–0.239 |
| **centroid detection rate** | **0.607** | 0.031 | 0.580–0.640 |
| centroid precision | 0.496 | 0.042 | 0.460–0.542 |

Against gv5's box formulation on the same class: recall 0.000, mAP50 0.009.

**The published 0.525 is superseded by 0.492 ± 0.074.** It was not wrong — it
was one draw quoted without a spread, and slightly optimistic against the mean.

### 12.2 Quote the centroid rate, not recall

Recall carries by far the widest variance (sd 0.074) because it steps coarsely
over 59 test instances — one instance found or lost moves it ~0.017. Box mAP50
(0.018), mask mAP50 (0.012) and the centroid rate (0.031) are all substantially
more stable.

So the metric adopted in §10.4 for *operational* reasons turns out to also be
the better-behaved one statistically. Worth stating plainly in any write-up: it
was not chosen because it flattered the result.

### 12.3 The bug the seeds found, which is the real lesson here

Seeding was meant to put an error bar on 0.525. It found a training defect.

Under the original `patience=60`, seed 1 scored mask mAP50 **0.004** against
seed 0's 0.204 and seed 2's 0.153 — apparent catastrophic seed variance. It was
not. It ran **131 epochs** where the others ran 608 and 558.

On 51 images this model sits at mask mAP50 ≈ 0.000–0.002 for roughly the first
200 epochs **in every seed** before it learns anything. That flat region is
structural, not a plateau of convergence. Early stopping evaluates "has it
improved lately?" inside it, where the metric is pinned near zero and moves only
in the fourth decimal — so the decision is made on noise.

Worse: both surviving seeds peaked at 586/608 and 551/558, still climbing when
patience ended them. The old default was cutting **every** run short, including
the one the published number came from.

With patience off, seed spread on mask mAP50 falls **0.101 → 0.012**, an
eightfold reduction, and seed 1 lands at 0.239 — the best of the three.

`train_net_seg.py --patience` now defaults to 1000, with the dead zone written
into its docstring.

**The generalisable point:** early stopping assumes the metric it watches is
informative from the start. On a dataset this small it is not, for hundreds of
epochs. Any future small-data run in this project should treat patience as a
parameter to justify rather than inherit — and §4.6's three-seed rule earned its
place here by catching a config bug that a single run reported as a result.

### 12.4 Two artefacts this exposed, both now fixed

* `train_net_seg.py` ran a test eval but persisted only `provenance.json`. Every
  D2 number published so far existed solely in terminal output. All runs are now
  scored through `ai/scripts/evaluate.py`, which writes `test_metrics.json` for
  box and mask heads.
* `ai/data/net_seg/build_report.json` carried a `dataset_version` but no
  fingerprint block, so the split could not be asserted. Written with
  `verify_dataset.py --root ai/data/net_seg --write`.

### 12.5 What is still not licensed

Unchanged. §10.5 Tier 2 needs ≥300 real net boxes from ≥3 sites; this is 59
instances from 2 sites across 11 chips. Three seeds satisfies §4.6, which was
one of five conditions — see §10.6 for the full ledger.

`ghost_net` stays Tier 1, review-only. Seeds agreeing with each other is not
sites agreeing with each other.

---

## 13. D-geom, mosaic, and a correction — 2026-09-13

### 13.1 The correction

On 2026-09-13 the `rect=True` half of D-geom was described as "never tested"
and a run was queued for it. **That was wrong, and §10.2.2 already said so on
2026-09-05.** The tiling half of D-geom is not open:

* re-tiling is impossible — `interim/` is already cut to 640×640, and the
  sources that could be re-cut were pruned in `ad70122`;
* more importantly it is **inapplicable to nets**. Our net images are small
  pre-cut chips (486×373, 348×378, 359×501) handed to the detector whole.
  Square tiling was never cutting our nets, because our nets were never tiled.

§10.2.2's conclusion stands unchanged: **D-geom reduces to D2 (segmentation)**,
which has now run and is reported in §12. What remained was the much smaller
idea of `rect=True` so a 486×373 chip is not letterboxed — described there as
"cheap and can ride along with D2 rather than justifying its own run".

### 13.2 Why even that residual is now closed

`rect=True` cannot ride along, because ultralytics couples it to mosaic:

```python
hyp.mosaic = hyp.mosaic if self.augment and not self.rect else 0.0
```

Turning rect on silently turns mosaic off. So the residual idea was priced by
running the control alone — `gv7e-ctrl-nomosaic`, square, mosaic off, seed 0 —
against the three-seed gv7d3 baseline:

| metric | gv7d3 (mosaic on) | control (mosaic off) | delta |
|---|---|---|---|
| box recall | 0.492 ± 0.074 | 0.441 | −0.05 |
| box mAP50 | 0.528 ± 0.018 | 0.423 | −0.11 |
| **mask mAP50** | **0.227 ± 0.012** | **0.073** | **−0.15** |
| centroid rate | 0.607 ± 0.031 | 0.560 | −0.05 |

Mask mAP50 falls by two thirds. At sd 0.012 over three seeds the control sits
roughly **13 standard deviations** below the mean — far outside anything seeds
explain, even from one run.

Recovering wasted letterbox padding cannot be worth that. **`rect=True` is
closed for this dataset**, and the rect run was not re-attempted after the
system killed it. Testing D-geom properly would require rect-compatible mosaic,
i.e. patching ultralytics dataset internals, which is not a change to make five
days from a deadline.

### 13.3 The finding that came out of it, which is the useful part

**Mosaic is load-bearing on 51 images, and is now measured rather than
reasoned.** `train_net_seg.py` justified `mosaic=1.0` on the argument that with
51 images the risk is memorisation and mosaic is the cheapest defence. That was
a good argument with no number attached. It now has one: **−0.15 mask mAP50**.

The two metrics disagree in an informative way. Mask quality collapses while
the centroid rate barely moves (−0.05, inside its own CI). So without mosaic the
model still finds roughly the same nets — it just draws them badly, which is
what overfitting on 51 images should look like and where it should show first.
It is also a reminder that the choice of headline metric would have given two
different answers about the same run.

### 13.4 `wreck` — §2's label-noise hypothesis is retired

§2 ranked data-centric iteration first because "`wreck` at P 0.42 smells of
label noise". Measured, it does not.

Recall by object size (`ai/scripts/recall_by_size.py`): **0.525 on wrecks larger
than 2% of frame**, against 0.060–0.112 below that, and 501 of 836 test boxes
are sub-2%. The average of 0.26 is the tiling grid, not the detector.

The boxes are not sloppy: AI4Shipwrecks ships pixel-wise masks and
`masks_to_yolo.py` derives tight boxes from them, so they were never hand-drawn.
A triage pass over train/val (`ai/scripts/rank_label_suspects.py`, 446 findings)
has a median flagged box of 0.245% of frame — the same fragments.

**So gv7.1 as specified — a human label audit — is aimed at a cause that is not
there.** The tooling and `docs/LABEL_AUDIT_PROTOCOL.md` are kept, because the
triage and the test-split guards are correct and reusable, but the audit itself
should not be run on this evidence.

The real question is now whether to drop sub-threshold fragments from the
dataset. That runs straight into §3.1 — cleaning train/val while test keeps its
fragments trains a model that is then scored on missing them — so it is an
announced, one-time test correction with gv5 re-scored on the result. gv7.0
exists for exactly that and has already been run once.
