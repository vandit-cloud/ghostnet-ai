# Centroid detection rate for `gv7d2b-netseg`

**2026-09-12. Metric only — no training, no GPU. `ai/scripts/centroid_metric.py`.**

Implements the commitment in EXPERIMENT_GV7_PLAN.md §10.4 to report Track D
results under a centroid detection rate alongside mAP50, because IoU-based
metrics penalise a long, thin, fragmented target for a fragmentation that has no
operational meaning.

## The rule adopted (rule C)

Both ground truth and predictions are collapsed into **nets** before anything is
compared: single-linkage clustering on centroid distance at the match tolerance,
then greedy nearest-first one-to-one matching between net centroids.

Single linkage is normally the objectionable choice — it chains. Here that is
the point: a 400 m net traced as six bead chains end to end has distant
endpoints and is still one net. A compactness-based clustering would split
exactly the long nets we most want counted once.

Two rejected alternatives, and why:

* **Strict one-to-one on polygons** re-introduces the fragmentation penalty the
  metric exists to remove — one blob correctly covering a net traced as three
  chains would score 1/3.
* **Lenient many-to-one** cannot charge for over-prediction at all. A model
  spraying polygons scores near-perfectly. These predictions feed a human review
  queue, so that cost is real and has to be countable.

The price of rule C is that the denominator is nets, not polygons — so these
figures are **not on the same footing as our mAP50 numbers**, and the JSON says
so in `denominator_note`.

## A defect found and fixed on the way

YOLO normalises x by width and y by height *independently*. That is fine for
boxes and wrong for distances. Our chips are not square and not consistently
shaped — 322×280, 401×316, **331×112** — so on the 3:1 chip a "distance of 0.10"
was 33 px across and 11 px down: the tolerance was an ellipse, differently shaped
on every chip.

Worse, in side-scan the two axes mean different physical things (across-track is
RANGE, along-track is vessel travel), so the distortion was not merely cosmetic.

`aspect_correct()` puts both axes in units of chip width. The correction moved
the headline rate **0.596 → 0.680**, which is the measure of how much the bug
mattered. Every number below is post-fix.

## Result, test split, 11 chips

At the operating tolerance of 0.10 (chip widths), conf 0.25:

| | |
|---|---|
| ground-truth polygons | 59 |
| ground-truth **nets** after clustering | **50** |
| predicted polygons | 81 |
| hits / misses | 34 / 16 |
| false alarms | 26 |
| **centroid detection rate** | **0.680** |
| centroid precision | 0.567 |

For contrast, the same model's IoU-based scores: box recall 0.525, mask mAP50
0.204. The centroid rate sits above box recall, which is the effect §10.4
predicted — part of the mask penalty was fragmentation, not localisation failure.

## Tolerance sensitivity — publish this, not just the headline

The rate is strongly tolerance-dependent, and the denominator moves with it:

| tolerance | GT nets | rate | precision |
|---|---|---|---|
| 0.05 | 59 | 0.508 | 0.462 |
| 0.08 | 53 | 0.623 | 0.532 |
| **0.10** | **50** | **0.680** | **0.567** |
| 0.15 | 32 | 0.656 | 0.512 |
| 0.20 | 23 | 0.739 | 0.515 |
| 0.25 | 16 | 0.812 | 0.565 |
| 0.30 | 15 | 0.800 | 0.571 |

Two things to read here, both cautionary:

1. **The headline can be dialled.** Quoting 0.812 by choosing tolerance 0.25
   would be indefensible — a quarter of a chip width is not "pointing at the
   spot", and the denominator has collapsed to 16. The sweep is published
   precisely so the operating point cannot be tuned quietly.
2. **The rate is not monotonic** (0.680 at 0.10, 0.656 at 0.15). A rate that
   dips as the rule gets more generous is a sign the estimate is unstable at
   this sample size, not a property of the model.

**Why 0.10 is the operating point:** it is the smallest tolerance at which the
clustering does real work (59 → 50 nets) while staying a tight radius. Below
that, rule C degenerates into the strict rule; above 0.15 the denominator falls
under 32 and the number stops being interpretable at n=11.

**No physical grounding is available.** These chips come from published figures
with no recorded ground resolution, so the tolerance cannot be converted to
metres. If GN0 or MARELITT data arrives with georeferencing, the tolerance
should be re-derived from a diver search radius and this number recomputed.

## Standing caveat

n = 11 chips. This is an upper bound reported under Tier 1 of §10.5 — a review
candidate, never a detection claim. The promotion rule is unchanged: ≥300 real
net instances from ≥3 sites, recall ≥0.30, three seeds, non-overlapping
bootstrap CI, under both mAP50 and this metric.

Tests: `ai/tests/test_centroid_metric.py`, 17 cases.
