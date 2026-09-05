# gv7 — plan and measurement design

**Status: PLAN. Nothing has been run. `gv5-yolo11s` is and remains the shipped
model until a promotion criterion in section 6 is met on measured evidence.**

This document is written to be pre-registered: the promotion criteria, the
guardrails and the minimum detectable effects are all fixed *before* any run, so
"it improved" is a decision rule rather than an argument after the fact. That is
the same discipline that made `docs/EXPERIMENT_GV6.md` a usable negative result.

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
2. **`ghost_net` is not a data problem.** gv6 took it from 215 to 2,246
   perfectly-labelled training boxes and recall moved 0.000 → 0.000. It is a
   flat, shadowless, low-contrast target: one weak acoustic cue. gv7 does not
   attempt to fix it and does not count it toward success.

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

**Prerequisite P1 (do before any gv7 run):** make the writer honour
`GHOSTNET_MODELS_DIR`, or add an explicit `--out` argument. Either removes the
whole class of accident. Ship it with a test that asserts the writer does not
touch `ai/models/calibrator/` when the override is set.

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

* **More synthetic nets.** Tested. Recall 0.000 → 0.000.
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
