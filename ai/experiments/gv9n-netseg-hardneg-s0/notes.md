# gv9n — net segmentation + hard negatives, seed 0

**2026-09-24. `gv9n-netseg-hardneg-s0`.** Same recipe as gv7d3 (`yolo11s-seg`,
1000 epochs, patience off, seed 0) with 102 empty China-Offshore seabed chips
added to train (`E:\New folder\ai\data\net_seg_hardneg`, built by
`ai/scripts/build_net_seg_hardneg.py`). val/test are the same 11+11 net chips.

## Run was cut at epoch 730 / 1000

A Windows Update restart (`MoUsoCoreWorker.exe`, 04:26:09, KB5124010) killed the
run and the overnight queue during epoch 731. Scored from `best.pt` = **epoch
647**. The run had plateaued: the best fitness in each 100-epoch window went
0.248 / 0.278 / **0.287** / 0.278 (400s → 700s), and gv7d3 peaked at 785–853.
The truncation probably costs little, but it is not measured.

## Result vs the pass rule fixed before training

| check | bar | gv9n-s0 | gv7d3 s0 / mean(n=3) | |
|---|---|---|---|---|
| false-alarm frame rate @0.25 (100 held-out empty chips) | < 15% | **3%** (0.04 outlines/chip) | 31% / 42% | pass |
| centroid detection rate (test) | >= 0.576 | **0.640** (32/50, CI 0.41–0.80) | 0.600 / 0.607 | pass |
| test box recall | >= 0.418 | **0.390** (23/59) | 0.576 / 0.492 | **FAIL** |

**Verdict: FAIL.** Under the rule set in advance, seeds 1–2 don't run and
gv7d3-s0 stays the ship candidate.

## What else it shows

| test metric | gv9n-s0 | gv7d3 mean ± sd |
|---|---|---|
| box mAP50 | 0.351 | 0.528 ± 0.018 |
| box precision | 0.475 | 0.663 |
| mask mAP50 | 0.178 | 0.227 ± 0.012 |
| centroid precision | 0.582 | 0.496 |

The recall miss alone is coarse: it is about two instances out of 59. The mAP50
drop is not coarse. Box mAP50 is about 10 gv7d3 seed-sds below the mean, and
mask mAP50 about 4. The hard negatives bought a roughly 10× cut in false alarms
on empty seabed, paid for with a real loss of localisation quality on nets.
Centroid rate held up because it only asks "is there an outline near each net".

False alarms at 0.25 by group: `quanzhou_RP` 1/10, `yantai_SS` 1/9,
`yantai_SW` 1/2; every other group 0.

## Scoring notes

- `evaluate.py` was run with `--allow-dataset-drift`. `net_seg_hardneg` has no
  fingerprints block, but its `test/images` and `test/labels` are **md5-identical**
  (11/11 files) to `net_seg/test`, the split gv7d3 was scored on. The ruler did
  not move.
- Artefacts: `centroid_test.json` (here), `../net-negatives/gv9n-netseg-hardneg-s0.json`,
  `../gv9n-netseg-hardneg-s0-test/test_metrics.json`, log
  `../probe_logs/gv9n-netseg-hardneg-s0.score.log`.
