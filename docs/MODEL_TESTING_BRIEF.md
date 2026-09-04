# Testing GhostNet-AI — brief for an outside reviewer

**Read this before running anything. You are here to evaluate a model, not to
change it.**

You have been given `best.pt` and this document. That is deliberate: everything
below can be done with the weights alone, and nothing below requires editing a
file in this project.

---

## The one rule

**Do not modify anything.** In particular, never run:

| Command | Why not |
|---|---|
| `build_dataset.py` | rebuilds `ai/data/processed/` **in place**. It destroys the exact split the model was scored against, and those numbers then become unreproducible. This has already cost this project one run's per-class metrics. |
| `train.py`, `train_all.ps1` | starts an 8-hour GPU job and overwrites weights |
| `fit_calibration.py` | overwrites the fitted temperature every other number depends on |
| anything writing to `ai/data/` | same reason as the first row |

Report findings. Do not fix them.

---

## How to run the model

**Use `ghostnet.detect()`, never `ultralytics` directly.**

```
python ai/scripts/try_model.py --images path/to/folder
```

This is the only path that tests what actually ships. It applies temperature
calibration, the review-floor policy, the geotagging, and emits the contract
payload the web application consumes. Loading the `.pt` with ultralytics and
reading `results[0].boxes` exercises a code path nobody uses, and gives raw
scores that are systematically overconfident.

To get test tiles that actually contain something:

```
python ai/scripts/pick_samples.py --class any --n 20 --out E:/sonar-test
python ai/scripts/pick_samples.py --list
```

The test split is ~67% empty seabed. Browsing it by hand and grabbing files
gives you tiles with nothing in them, the model correctly reports nothing, and
it looks broken.

There is also a prebuilt page with 14 real cases and a live confidence slider:

```
ai/experiments/<run>/testbench.html
```

It contains hits, misses, correct rejections AND false positives, in roughly the
proportions the metrics imply. It is not a highlight reel.

---

## Numbers: which ones are real

**Quote test figures. Never validation.** The model is early-stopped against
validation, so a val score is contaminated by model selection. `results.csv`
holds val; `test_metrics.json` holds test.

**Quote calibrated confidence. Never the raw score.** Raw YOLO scores are not
probabilities. Temperature scaling is fitted on validation and stored in
`ai/models/calibrator/temperature.json`. `detect()` applies it; ultralytics does
not.

**mAP50 is an unweighted mean over classes.** A class with 9 test boxes counts
as much as one with 567. Adding a thin class mechanically lowers the headline
without anything getting worse. Always read the per-class table.

---

## Caveats that must travel with specific numbers

These are not modesty. Quoting any of these figures without its qualifier makes
a claim the data does not support.

- **`debris`** — most of its held-out boxes come from one continuous SubPipe
  survey: same AUV, same sonar, same pipeline, separated from training only by
  a 156-second gap in the timestamps. It measures tracking through unseen
  seabed, **not** generalisation to debris elsewhere. The only independent
  debris is 14 boxes from sonar_detect. Report both.
- **`ghost_net`** — the ground truth is *ours*. 298 boxes hand-drawn on 73 chips
  that the source dataset ships as classification-only, by one annotator, from
  one region. The convention is documented with worked examples in
  `ai/data/annotate/ghost_net/_guide/`. The class is real; the count is small
  and must be stated.
- **`plane`** — starved. Check the box count before drawing any conclusion from
  its score.
- **False-alarm rate on "empty" seabed** — the tiles are *unannotated*, which is
  not the same as *verified empty*. Some come from survey lines the source
  dataset never annotated at all. Every figure from it is an upper bound.
- **Domain** — held-out tiles come from the same surveys as training: same
  sonar, same water, same gear. That is genuine generalisation, but within one
  domain. Expect a large drop on a different sonar.

---

## What is actually worth testing

Metrics on the test split are already computed. The valuable work is finding
where the model breaks, which the test split cannot show you because it comes
from the same surveys as training.

1. **Out-of-distribution sonar.** Any side-scan image from a survey not in
   `docs/DATA.md`. This is the single most informative test available.
2. **Not-sonar inputs.** A photograph, a screenshot, a chart. The model should
   report nothing. If it confidently reports a wreck in a photo of a desk, the
   review floor is too low.
3. **Degradation curves.** Take tiles it gets right, add speckle noise, blur, or
   contrast changes in increasing amounts, and find where detection collapses.
   The problem statement names speckle and varying resolution explicitly, and
   the project has **no preprocessing for either** — so this measures a known,
   documented gap rather than hunting for a surprise.
4. **Acoustic shadow.** Objects are often visible mainly through their shadow.
   `shadow_context` in the output is currently hardcoded to `"not_evaluated"`;
   this is a known unimplemented requirement, not a bug to report.
5. **The threshold trade.** Open `testbench.html` and move the slider. The
   review floor is currently 0.20 and was never derived from a measured
   recall-versus-false-alarm curve. A recommendation here would be genuinely
   useful.
6. **Empty-seabed stress.** Feed it natural clutter — gullies, rock fields, sand
   ripples. Firing on those is the exact failure the project is scored on.

---

## What a useful report looks like

- the **command** you ran and the **file** you ran it on, so it can be repeated
- the **calibrated** confidence, and whether the detection was above or below
  the review floor
- for a false positive: the image, so it can be added to the negative set
- for a miss: whether the object is visible to *you* in the image

Please distinguish **a bug** (the code does something other than what it says)
from **a limitation** (the model is weak because a class has 39 training boxes).
The second is documented in `docs/AI_TRAINING_HANDOFF.md` and does not need
rediscovering; the first is worth a great deal.
