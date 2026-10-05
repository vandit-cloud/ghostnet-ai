# Per-class confidence calibration (gv5, 5 Oct 2026)

**Verdict: ship per-class temperature.** On the held-out test split, pooled ECE
falls from 0.147 to 0.046 and NLL from 0.525 to 0.462. The calibrated maximum
rises from 0.739 to 0.913, so `low` uncertainty (and Priority.HIGH) can now be
reached. To keep recall and false alarms where they were, two calibrated floors
had to come down (`review_floor_artificial` 0.20 → 0.12, `review_floor_net`
0.10 → 0.05). Left at the old values they would have quietly cut ghost_pot
recall from 0.429 to 0.303. ghost_pot calibration gets worse (ECE 0.064 → 0.110),
and the cause is val's ghost_pot labels, not the method. CRITICAL is still never
produced.

Reproduce:

    python ai/scripts/fit_calibration.py --weights ai/models/trained/ghostnet.pt \
        --data "E:/New folder/ai/data/processed/data.yaml" --device 0
    python ai/scripts/evaluate_calibration.py --dump --data "E:/New folder/ai/data/processed/data.yaml"
    python ai/scripts/evaluate_calibration.py

All numbers are in `calibration_metrics.json`. The old calibrator is
`git show 8ce8d9d:ai/models/calibrator/temperature.json`.

## Setup

- Weights: gv5-yolo11s (`ghostnet.pt`, sha256 4ba7703e…). Dataset
  8src-12472/1492/4346. Val has 1,492 frames, test has 4,346.
- The fit uses VAL and every number reported here comes from TEST. Detections
  use the served NMS settings (IoU 0.5, max_det 300). The old file used
  ultralytics' default of 0.7, which kept 1,604 val boxes against the 1,238 the
  app keeps. Boxes are matched greedily, class-aware, at IoU ≥ 0.5 (the
  fitter's own `match`).
- Fit population: raw ≥ 0.05. "Served" means what the policy can actually show:
  raw ≥ 0.10, or raw ≥ 0.03 for ghost_net.
- Minimum evidence for a class's own map: **30 matched and 30 unmatched val
  detections.** Classes below that use the global T, and the file records why.

## What was fitted (val)

| class     | val boxes | correct | map |
|-----------|----------:|--------:|-----|
| wreck     | 554 | 148 | **own T = 1.145** |
| plane     | 21  | 8   | global (8 positives < 30) |
| debris    | 22  | 6   | global (6 positives < 30; every val debris is SONARDETECT) |
| ghost_pot | 638 | 442 | global (**degenerate**: the T fit ran into the search wall at 20) |
| ghost_net | 4   | 1   | global (1 positive) |
| *global*  | pooled wreck+plane+debris+net | | **T = 1.202** |

**Why ghost_pot is degenerate.** On val, ghost_pot is correct 60% of the time at
raw 0.07 and 69% of the time overall. No temperature can map that, so the NLL
keeps falling as T → ∞, which flattens every score to 0.5. On test the same
class is correct 30% of the time (val is an unrepresentative survey, and many of
test's ghost_pot "false positives" are unlabelled pots; see
memory/ghost-pot-unlabelled). Using the wall-T would push ghost_pot's test ECE
from 0.064 to 0.178. The fitter now rejects any fit at the search bound and
keeps that class out of the pooled global fit. Without this exclusion, ghost_pot
pulls the global T to 6.31, and every fallback class inherits that T (debris
test ECE 0.326).

**The old T = 2.72 came from val ghost_pot.** It was never a measure of general
overconfidence. With gv5 at the served NMS setting, raw YOLO scores for wreck
and debris are already close to calibrated (test ECE 0.021 and 0.092). The
shared T pulled every class toward 0.5.

## Calibration on TEST (fit population, raw ≥ 0.05, 3,803 boxes)

| ECE (NLL)          | old global T 2.72 | global refit (6.31) | **per-class T** | per-class Platt | raw |
|--------------------|------:|------:|------:|------:|------:|
| pooled             | 0.147 (0.525) | 0.233 (0.605) | **0.046 (0.462)** | 0.036 (0.462) | 0.064 (0.469) |
| wreck (1,673)      | 0.174 | 0.263 | **0.042** | 0.041 | 0.021 |
| debris (870)       | 0.249 | 0.326 | **0.118** | 0.118 | 0.092 |
| ghost_pot (1,238)  | **0.064** | 0.127 | 0.110 | 0.110 | 0.144 |
| plane (13)         | 0.138 | 0.144 | 0.287 | 0.287 | 0.304 |
| ghost_net (9)      | 0.293 | 0.406 | 0.123 | 0.123 | 0.088 |
| max calibrated     | 0.739 | 0.610 | 0.913 | 0.913 | — |

Served boxes only (2,394): pooled ECE goes 0.145 → **0.054**, NLL 0.572 →
0.511. Platt scores 0.038 and 0.511.

Reliability on test, wreck, predicted → actual:
- before: 0.27 → 0.06, 0.34 → 0.15, 0.55 → 0.70
- after: 0.24 → 0.26, 0.35 → 0.37, 0.55 → 0.59, 0.74 → 0.79

Reliability on test, debris: before 0.66 → 0.94, after 0.85 → 0.94.
For ghost_pot, both maps under-predict: after 0.14 → 0.26, 0.34 → 0.50.

**Method choice: temperature.** Platt differs from temperature only on wreck,
the one class that fits its own map. There, Platt ties on held-out NLL (0.3916
vs 0.3916, and 0.519 vs 0.517 on served boxes, where temperature is ahead) and
ties on per-class ECE (0.041 vs 0.042). Platt's lower *pooled* ECE (0.036)
comes from its +0.52 intercept moving wreck boxes into bins shared with debris.
Each class is no better calibrated. That is not "clearly better", so the
one-parameter map ships. Both are implemented (`--method platt`), and the loader
reads either.

**Honest caveat: val gets worse.** Pooled val ECE goes 0.141 → 0.279, all of it
from val ghost_pot (0.356 → 0.503). That is the same label shift seen from the
other side. The old T fitted val's ghost_pot labels better and test's worse.
Test has 3× the frames and is the split that is held out.

## What a reviewer sees (TEST, policy applied)

| | FA on empty frames (2,930) | wreck R | debris R | ghost_pot R | plane R | net R | reported |
|---|---:|---:|---:|---:|---:|---:|---:|
| before (T 2.72, floors 0.20/0.10) | 7.75% | 0.355 | 0.833 | 0.429 | 0.333 | 0.028 | 2,394 |
| new calibrator, **old floors** | 4.91% | 0.318 | 0.824 | **0.303** | 0.222 | 0.000 | 1,716 |
| **shipped: new calibrator, floors 0.12/0.05** | **7.75%** | **0.355** | **0.833** | **0.429** | **0.333** | **0.028** | **2,394** |

Val shows the same pattern: identical to the box at 0.12/0.05, and FA 4.63% →
2.68% with the old floors.

**Floor change.** Under T = 2.72, the lowest calibrated score that could reach
the policy was 0.309, so the 0.20 floor never bound. The per-class map sends
raw 0.10 to 0.128 for wreck and 0.139 for the rest, and sends raw 0.03 to 0.053
for nets. 0.12 and 0.05 sit just under those values and reproduce the shipped
queue exactly. `tests/test_review_only.py` now checks this for every class
against the shipped file, so a future refit that makes a floor bind will fail.

The floor is now a real lever. Choosing to use it is a policy decision, so it
was left out of this change:

| artificial floor | 0.12 | 0.15 | 0.20 | 0.25 | 0.30 |
|---|---:|---:|---:|---:|---:|
| FA, empty frames | 7.75% | 6.89% | 4.91% | 3.52% | 2.63% |
| ghost_pot recall | 0.429 | 0.395 | 0.303 | 0.240 | 0.206 |
| wreck recall     | 0.355 | 0.341 | 0.318 | 0.273 | 0.245 |

## Uncertainty bands and priority

**Rule.** The edges are probabilities. Each band's held-out precision must fall
inside the band: low ≥ 0.75, medium 0.45–0.75, high < 0.45. With the per-class
map the existing edges (0.75 / 0.45) pass that check, so they stay.

| band (test, 2,394 reported) | share | precision |
|---|---:|---:|
| low (≥ 0.75)     | 15.1% | 0.939 |
| medium           | 17.7% | 0.726 |
| high (< 0.45)    | 67.2% | 0.262 |

On val: low 0.5% (4 wrecks, all correct), medium 10.6%, high 88.8%. Before,
`low` was 0% on both splits.

Breaking `low` down by class on test: 351 of the 362 are debris (95% correct)
and 11 are wreck (64% correct, a small sample). No ghost_pot, plane or net box
reaches `low`.

**Rejected rule.** "Lowest score above which val precision ≥ 0.80 / 0.50" gives
edges of 0.467 and 0.128. On test, those put 68% of detections in `medium` at
precision 0.27 and label wrecks `low` at 0.68. Val's ghost_pot labels inflate
val precision in exactly the score range where those edges land.

**Priority** (`_priority_for`; detector boxes only; the U-Net is off for the
nets here):

| | CRITICAL | HIGH | MEDIUM | LOW |
|---|---:|---:|---:|---:|
| test before | 0 | 0 | 963 | 1,431 |
| test after  | 0 | **362** | 450 | 1,582 |
| val before  | 0 | 0 | 151 | 610 |
| val after   | 0 | 4 | 97 | 660 |

**CRITICAL is still never produced.** It requires a ghost_net in the `low`
band. The highest calibrated score for a detector net box on test is 0.21, and
U-Net net candidates are uncalibrated and capped at `medium` on purpose (this
change leaves that alone). Reaching CRITICAL is lever (b) of
docs/FEATURE_PROMPT_SIZE_AWARE_PRIORITY.md §4.3 (the risk score), not a
calibration question.

Uncertainty escalation (water column, dropout) is not modelled in these counts.
In the app it can only move detections toward `high`.

## Not done / open

- ghost_pot needs a val split whose pot labels look like the deployment surveys,
  or the mined-label pass extended to val. Until one exists, ghost_pot runs on
  the global T, and its test ECE (0.110) is worse than under the old T (0.064).
- debris and plane have almost no val evidence (6 and 8 positives). Their maps
  are the global T. The test reliability for debris (0.85 → 0.94 at the top)
  shows real underconfidence that cannot be fitted honestly from val.
- `try_model.py` and `evaluate_pinta.py` read `review_floor_artificial` as
  their default, so they follow the change from 0.20 to 0.12.
