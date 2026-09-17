# gv7d3 — D2 net segmentation, three seeds, patience corrected

**2026-09-13. `gv7d3-netseg-s0/s1/s2`, seeds 0/1/2.**
`yolo11s-seg`, 1000 epochs, **patience 1000 (early stopping off)**, batch 4,
imgsz 640, `close_mosaic=50`, dataset `netseg-51/11/11`, test split asserted
`test11-8835e2482d97`. 74 min per run, ~3.7 h total.

Supersedes `gv7d2b/c/d`, whose `patience=60` aborted seed 1 at epoch 131 and cut
the other two short — see `ai/experiments/gv7d2c-netseg/notes.md` for the
diagnosis this run was designed to fix.

## Result

| metric | s0 | s1 | s2 | mean | sd | range |
|---|---|---|---|---|---|---|
| box recall | 0.576 | 0.458 | 0.441 | **0.492** | 0.074 | 0.441–0.576 |
| box precision | 0.615 | 0.659 | 0.715 | 0.663 | 0.050 | 0.615–0.715 |
| box mAP50 | 0.542 | 0.507 | 0.534 | **0.528** | 0.018 | 0.507–0.542 |
| mask mAP50 | 0.215 | 0.239 | 0.228 | **0.227** | 0.012 | 0.215–0.239 |
| centroid detection rate | 0.600 | 0.640 | 0.580 | **0.607** | 0.031 | 0.580–0.640 |
| centroid precision | 0.484 | 0.542 | 0.460 | 0.496 | 0.042 | 0.460–0.542 |

Scored through `ai/scripts/evaluate.py` (which persists box and mask metrics;
`train_net_seg.py` does not) and `ai/scripts/centroid_metric.py` at tolerance
0.10, conf 0.25.

## The patience fix is confirmed

The apparent seed catastrophe was entirely an artefact of early stopping.

| | gv7d2 (patience 60) | gv7d3 (patience off) |
|---|---|---|
| epochs run | 608 / **131** / 558 | 1000 / 1000 / 1000 |
| mask mAP50 | 0.204 / **0.004** / 0.153 | 0.215 / 0.239 / 0.228 |
| spread (sd) | **0.101** | **0.012** |
| centroid rate | 0.680 / **0.020** / 0.640 | 0.600 / 0.640 / 0.580 |

Seed variance fell by a factor of eight on mask mAP50 once every run was allowed
to leave the dead zone. Seed 1, which read as a total failure at 0.004, lands at
0.239 — the *best* of the three. There was never anything wrong with that seed.

## 1000 epochs is enough, and that is now measured

Best epoch: **785 / 853 / 797** of 1000. All three peaked with 150–215 epochs of
headroom, so the budget is no longer the binding constraint — unlike the gv7d2
runs, which peaked at 586/608 and 551/558 and were plainly still climbing.

This answers the open question the patience fix raised. No case for raising the
epoch budget further on this dataset at this image size.

## How to read the numbers against the published one

`docs/D2_SEGMENTATION_SUMMARY.md` currently quotes **box recall 0.525** from
gv7d2b, a single seed under the broken config. The correct replacement is
**0.492 ± 0.074 (n=3)**. The old figure sits inside that spread, so it was not
wrong — it was one draw reported without a spread, and slightly optimistic
relative to the mean.

Recall carries by far the widest spread (sd 0.074) because it steps coarsely
over 59 test instances. **Box mAP50 (sd 0.018), mask mAP50 (sd 0.012) and the
centroid rate (sd 0.031) are all far more stable**, and the centroid rate is the
one with operational meaning. `0.61 ± 0.03` is the most defensible single figure
this experiment produces.

## What this still does not license

Unchanged by three seeds. §10.5's promotion rule requires **≥300 real net
instances from ≥3 sites**; this is 59 instances from 2 sites across 11 chips.
The three-seed requirement in §4.6 is now satisfied, and it was only ever one of
four conditions.

So the class stays **Tier 1 — review candidate**, shipping under the review-only
contract, and no number here may be quoted as a detection claim. What improved
is the *confidence* in the formulation finding, not its licence.

The measurement problem still precedes the modelling problem: these seeds agree
with each other far more tightly than 11 chips can justify generalising from.
Agreement across seeds is not agreement across sites.
