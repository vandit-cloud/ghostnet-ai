# gv7.T — test-time augmentation on gv5

**2026-09-12. Evaluation only, no training. `ai/scripts/evaluate.py --tta`.**

**Result: NEGATIVE. gv5 without TTA remains the shipped configuration.**

## What changed

One variable: `augment=True` at inference. Same weights, same test split, same
`.val()` defaults otherwise. Ultralytics TTA runs the image at multiple scales
with horizontal flips and merges the results through NMS.

Baseline is **gv7.0**, re-scored today on the same ruler, not gv5's stored file.

## What moved

| metric | gv7.0 (no TTA) | gv7.T (TTA) | delta |
|---|---|---|---|
| overall mAP50 | 0.3525 | 0.3524 | −0.0001 |
| overall mAP50-95 | 0.1995 | 0.1916 | −0.0079 |
| overall precision | 0.5795 | 0.5999 | **+0.0204** |
| overall recall | 0.3609 | 0.3190 | **−0.0419** |

Primary metrics (§4.2), both far inside their MDE:

| class | gv7.0 mAP50 | gv7.T mAP50 | delta | MDE | verdict |
|---|---|---|---|---|---|
| wreck | 0.2794 | 0.2826 | +0.0032 | 0.064 | no measurable change |
| ghost_pot | 0.3142 | 0.3089 | −0.0053 | 0.076 | no measurable change |

Guardrails (§4.2): none breached. `debris` mAP50 0.8663 (floor 0.84), overall
precision 0.5999 (floor 0.52).

## Why it is a negative anyway

Passing the guardrails is not the same as being worth shipping. TTA bought
+0.020 precision and paid −0.042 recall — roughly two found objects given up for
every one false alarm suppressed.

**That is the wrong direction for this system.** GhostNet-AI is a survey triage
tool: an operator reviews what it flags, so a missed net or wreck is invisible
and unrecoverable, while a false alarm costs a few seconds of review. The whole
`review_floor` design (0.20 calibrated, chosen as the highest threshold retaining
≥95% of recall) exists to express that asymmetry. TTA moves against it, and
costs ~3× the inference time to do so.

The mAP50-95 drop (−0.0079) is the clearer tell: merging multi-scale predictions
through NMS loosens box localisation, which mAP50's 0.5 IoU threshold is too
forgiving to show.

## The one number not to misread

`ghost_net` mAP50 appears to rise 0.0088 → 0.0583. **Recall stayed 0.0000.** The
model still emitted no net prediction that matched a label; the mAP change is
precision-at-zero-recall arithmetic on 36 boxes, which §4.3 says supports only an
upper bound. This is not evidence of anything and must not be quoted.

## Not measured

Background activation rate was not re-derived under TTA — `evaluate_background.py`
has no TTA path. Moot here, since the run is rejected on its recall trade, but if
TTA is ever revisited that guardrail needs wiring first.
