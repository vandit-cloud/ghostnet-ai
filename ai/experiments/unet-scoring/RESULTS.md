# Track U results: seed 0 (24 Sep 2026)

Pass rules: `PLAN.md`, written before training. All numbers come from
`evaluate_net_unet.py`, the harness that reproduces every recorded YOLO
centroid result exactly. Test split = 11 chips, 59 polygons, 50 nets.

## Headline

| model | operating point | Dice | centroid | centroid prec | box R @IoU.5 | empty-chip FA |
|---|---|---|---|---|---|---|
| gv7d3 mean (YOLO-seg, 3 seeds) | conf 0.25 | 0.525 ± 0.013 | 0.607 | 0.495 | 0.570 | 42% |
| gv9n-s0 (YOLO-seg + negatives) | conf 0.25 | 0.513 | 0.640 | 0.582 | 0.458 | 3% |
| **gvU1-s0** (U-Net) | pixel 0.5 | **0.580** | **0.800** | 0.615 | 0.525 | 44% |
| **gvU1n-s0** (U-Net + negatives) | pixel 0.5 | **0.588** | **0.760** | 0.623 | 0.559 | **1%** |

**gvU1n-s0 PASSES all three rules:** FA 1% (< 15%), centroid 0.760 (>= 0.638),
Dice 0.588 (>= 0.525). By PLAN.md, seeds 1-2 are now running
(`probe_launchers/unet_seeds_2026-09-24.ps1`).

**gvU1-s0 is a real gain by its own rule:** Dice 0.580 > 0.538 and centroid
0.800 >= 0.638. It fires on 44% of empty chips, the same as gv7d3, so the
architecture alone improves outlines and hit rate but does nothing for false
alarms. The negatives fix false alarms, and in a U-Net they cost nothing.

## What the pairing says, and how strong it is

Paired chip bootstrap (5000 resamples, the same 11 chips for both models),
gvU1n-s0 centroid rate minus each baseline:

| vs | diff | paired 95% CI | P(diff <= 0) |
|---|---|---|---|
| gv7d3-s0 | +0.160 | [-0.026, +0.373] | 0.066 |
| gv7d3-s1 | +0.120 | [-0.034, +0.281] | 0.086 |
| gv7d3-s2 | +0.180 | [+0.000, +0.358] | 0.035 |
| gv9n-s0 | +0.120 | [-0.036, +0.286] | 0.086 |

Consistent in sign against every baseline, but one seed with every interval
touching zero is suggestive, not established. The seeds decide it. Per chip,
gvU1n matches or beats gv7d3-s0 on 8 of 11 chips; the biggest moves are
HN_051 (0 -> 3 of 4 nets), HN_060 (1 -> 5 of 5) and HN_017 (5 -> 7 of 7).
The gain is not carried by a single chip.

## Robust to its threshold

gvU1n barely moves between pixel thresholds 0.25 / 0.5 / 0.75 (Dice 0.589 / 0.588 /
0.583, centroid 0.76 throughout, FA 1% throughout). YOLO-seg is fragile here:
gv9n's Dice goes from 0.513 at 0.25 to 0.260 at 0.5. So the U-Net result does
not depend on the threshold choice fixed in PLAN.md.

## Caveats

* n = 11 test chips, 10 of them Quanzhou. An upper bound, a review candidate,
  never a detection claim.
* One seed so far.
* Empty-chip FA is measured on China-Offshore seabed only. The one false alarm
  is `quanzhou_RP` (rock/reef).
* Val Dice (0.592 best) chose the checkpoint. Val holds no empty chips, so
  nothing tuned the 1% FA figure.

# Seeds 1-2: CONFIRMED (24 Sep 2026, 15:50)

All three seeds pass every PLAN.md rule at pixel threshold 0.5.

| seed | Dice | centroid | centroid prec | box R @IoU.5 | empty-chip FA |
|---|---|---|---|---|---|
| s0 | 0.588 | 0.760 | 0.623 | 0.559 | 1% |
| s1 | 0.607 | 0.840 | 0.636 | 0.610 | 1% |
| s2 | 0.606 | 0.820 | 0.661 | 0.525 | 2% |
| **gvU1n mean ± sd** | **0.600 ± 0.011** | **0.807 ± 0.042** | **0.640 ± 0.019** | 0.565 ± 0.043 | **1.3%** |
| gv7d3 mean ± sd (YOLO-seg @0.25) | 0.525 ± 0.013 | 0.607 ± 0.031 | 0.496 ± 0.042 | 0.571 ± 0.010 | 42% |

Paired chip bootstrap on the 3-seed means (10,000 resamples): centroid
+0.200, 95% CI **[+0.105, +0.325]**, P(diff <= 0) < 0.0001. gvU1n is better on
9 of 11 test chips, equal on 2, worse on none. Dice moves by about 6 gv7d3 sds.

Box recall @IoU 0.5 is a tie (0.565 vs 0.571). That is expected: it
penalises merged blobs, which is why PLAN.md made it a report and not a gate.

**Verdict: gvU1n replaces gv7d3-s0 as the ghost_net ship candidate.** Best
single seed: s1 (Dice 0.607, centroid 0.840, FA 1%).

Still true: 11 test chips, 10 of them Quanzhou; the empty-chip FA is on
China-Offshore seabed only. An upper bound, a review candidate, not a detection claim.

Incident: the seeds queue's CPU scoring failed (exit 2) on a relative script
path, because pwsh inherited `ai/experiments` as its working directory. Scored by
hand afterwards; the launchers now use absolute paths.
