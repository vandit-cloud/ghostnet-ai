# D2 seed replication — seeds 1 and 2, and what they exposed

**2026-09-13. `gv7d2c-netseg` (seed 1) and `gv7d2d-netseg` (seed 2).**
Identical config to `gv7d2b-netseg` (seed 0) in every respect but the seed:
`yolo11s-seg`, 1000 epochs, patience 60, batch 4, imgsz 640, `close_mosaic=50`,
dataset `netseg-51/11/11`.

Purpose: EXPERIMENT_GV7_PLAN.md §4.6 requires three seeds before any result is
quotable. The D2 finding (net recall 0.000 → 0.525) rested on one.

## Headline: the spread is enormous, and it is NOT model variance

| seed | run | epochs | box recall | box mAP50 | mask mAP50 | centroid rate |
|---|---|---|---|---|---|---|
| 0 | gv7d2b | 608 | 0.525 | 0.473 | 0.204 | 0.680 |
| 1 | gv7d2c | **131** | 0.254 | 0.143 | **0.004** | **0.020** |
| 2 | gv7d2d | 558 | 0.458 | 0.483 | 0.153 | 0.640 |

Seed 1 is not a bad draw. It is an **unconverged run that early-stopping killed
in the dead zone**, and the epoch column is the tell.

## The mechanism

Best-epoch and trajectory, mask mAP50:

| run | epochs run | best epoch | mAP50 at epoch ~130 |
|---|---|---|---|
| gv7d2b | 608 | **586** | 0.001 |
| gv7d2d | 558 | **551** | 0.002 |
| gv7d2c | 131 | 116 | 0.001 |

On 51 training images this model sits at mask mAP50 ≈ 0.000–0.002 for roughly
the first 200 epochs, in **every** seed, before it learns anything at all. That
flat region is structural, not a plateau of convergence.

`patience=60` evaluates "has it stopped improving?" inside that region, where
the metric is pinned near zero and moves only in the fourth decimal. Early
stopping there is therefore decided by noise. Seeds 0 and 2 happened to twitch
upward often enough to survive it; seed 1 did not, and died at 131 epochs — well
before the point where the other two were still at 0.002 and had another 400
epochs of real learning ahead of them.

This is the same effect already recorded in `docs/D2_SEGMENTATION_SUMMARY.md`:
"an earlier 300-epoch run of the identical configuration reached only Mask mAP50
0.059 — on 51 training images, 300 epochs had not converged." That observation
was about the epoch budget. This is the same fact wearing a different hat:
patience can end the run before the budget is ever spent.

## A second finding, from the seeds that worked

**Both surviving seeds peaked within 25 epochs of where they stopped** (586 of
608; 551 of 558). They were still improving when patience ended them. So 1000
epochs with patience 60 is not merely risky for the unlucky seed — it is cutting
every run short, including the one we shipped a number from.

## What this does and does not say about D2

**Does not overturn it.** Two independently seeded, converged runs agree closely:
box recall 0.525 / 0.458, centroid rate 0.680 / 0.640. That is a consistent
result from the only two runs that were allowed to finish, and the formulation
change (boxes → polygons) is still the thing that moved recall off 0.000.

**Does block the three-seed claim.** §4.6 needs three, and we have two valid
runs plus one aborted one. Reporting n=3 with seed 1 included would understate
the model by averaging in a training failure; reporting n=2 and silently
dropping seed 1 would be worse. Neither is acceptable, so the number stays
single-run-caveated until the re-run lands.

## Action required

Re-run all three seeds with patience raised well past the dead zone (≥300, or
disabled — at ~5.6 s/epoch a full 1000-epoch run is only ~90 min). All three,
not just seed 1, so the three share one config and the comparison is clean.
Estimated ~4.5 h total.

`train_net_seg.py` should have its `--patience` default raised at the same time,
with the dead-zone reason recorded, or this will recur.

## Incidental: two gaps closed while scoring these

* `train_net_seg.py` runs a test eval but **never persists it** — it writes only
  `provenance.json`. The published D2 numbers existed solely in stdout. All
  three runs above were therefore re-scored through `ai/scripts/evaluate.py`,
  which writes `test_metrics.json` for box and mask heads.
* `ai/data/net_seg/build_report.json` carried a `dataset_version` but no
  fingerprint block, so `evaluate.py` correctly refused to score against an
  unassertable ruler. Fixed with `verify_dataset.py --root ai/data/net_seg
  --write`; the test split is now `test11-8835e2482d97`.
