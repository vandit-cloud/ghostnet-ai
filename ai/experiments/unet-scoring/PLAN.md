# Track U: ghost_net U-Net. Pass rules fixed BEFORE training (24 Sep 2026)

Written before either run had trained a single epoch.

## Runs (seed 0 first)

| run | data | compared against | question |
|---|---|---|---|
| `gvU1-unet-s0` | `net_seg` (51 net chips, no empties) | gv7d3 (YOLO11s-seg, 3 seeds) | Does per-pixel segmentation outline nets better, all else equal? |
| `gvU1n-unet-hardneg-s0` | `net_seg_hardneg` (51 net + 102 empty) | gv9n (YOLO-seg + same negatives) | Can a U-Net use the negatives without losing the nets, as gv9n did? |

Both use U-Net with a ResNet34 encoder (ImageNet weights, 1-channel input),
640 letterbox, batch 4, 300 epochs, BCE+Dice loss, best checkpoint on val Dice
@0.5. Scripts: `ai/scripts/train_net_unet.py`, `_net_unet.py`,
`evaluate_net_unet.py`.

## One harness for every model

All numbers, the YOLO baselines included, come from `evaluate_net_unet.py`:
the same test chips (md5-identical to `net_seg/test`), the same native-
resolution masks, and centroid matching through `centroid_metric.py`'s own
code. Harness check: gv7d3-s0 through it must reproduce its recorded centroid
result (30/50 hits, 32 false alarms @0.25).

Operating points, fixed now: **YOLO at conf 0.25** (what the app ships) and
**U-Net at pixel threshold 0.5** (the natural sigmoid midpoint). U-Net blobs
under 0.1% of the chip are discarded; the smallest real polygon is 0.24%. The
other thresholds are reported but are not used to judge a run.

## Pass rules

**gvU1n passes** (the run the idea exists for) if at threshold 0.5 ALL hold:
1. empty-chip false-alarm frame rate < 15%  (gv7d3 31-50%, gv9n 3%)
2. centroid detection rate >= 0.638  (gv7d3 mean 0.607 + 1 sd 0.031)
3. test Dice >= gv7d3 3-seed mean Dice, measured by this harness

**gvU1 is informative, not pass/fail.** It isolates the architecture. It
counts as a real gain if test Dice > gv7d3 mean + 1 sd OR centroid >= 0.638,
with its false-alarm rate reported alongside.

Box recall @IoU 0.5 is reported for all models but is NOT a gate for a U-Net.
One blob covering two touching chains scores as a box miss even when both
chains are found. That penalises merging, which centroid rule C deliberately
forgives. Pixel Dice is the outline-quality guard instead.

If gvU1n passes, run seeds 1-2 before any claim. If both fail or tie, the
reading is that architecture is not the bottleneck on 73 chips from two sites.

## Baselines through the harness (computed 24 Sep before any U-Net was scored)

Harness check PASSED: gv7d3 s0/s1/s2 and gv9n reproduce their recorded
centroid hits and false alarms exactly at 0.25 (30/32, 32/27, 29/34, 32/23).
The first attempt took YOLO outlines from `retina_masks=True` and was off by 2
hits on s0; outlines now come from the default pass, Dice from the retina pass.

| model @ its operating point (YOLO 0.25) | Dice pooled | per-chip Dice | centroid | box R @IoU.5 | empty-chip FA |
|---|---|---|---|---|---|
| gv7d3-s0 | 0.536 | 0.506 | 0.600 | 0.576 | 31% |
| gv7d3-s1 | 0.528 | 0.486 | 0.640 | 0.576 | 50% |
| gv7d3-s2 | 0.511 | 0.479 | 0.580 | 0.559 | 44% |
| **gv7d3 mean ± sd** | **0.525 ± 0.013** | 0.490 | 0.607 | 0.570 | 42% |
| gv9n-s0 (+negatives) | 0.513 | 0.445 | 0.640 | 0.458 | 3% |

**Dice bar for rule 3: 0.525.** A "real gain" for gvU1 is Dice > 0.538 (mean + 1 sd).

Side finding: by pixel Dice, gv9n lost little (0.513 against 0.525), even
though its box mAP50 fell from 0.528 to 0.351. Most of gv9n's loss is in
instance boxes and confidence calibration (its Dice at 0.5 collapses to 0.260),
not in which pixels it paints.
