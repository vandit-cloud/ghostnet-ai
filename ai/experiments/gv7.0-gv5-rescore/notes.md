# gv7.0 — re-score gv5 on the current test split

**2026-09-12. Evaluation only, no training. `ai/scripts/evaluate.py`, no flags.**

Purpose, per EXPERIMENT_GV7_PLAN.md §3: establish that the ruler still reads the
same before anything is compared against it. This run measures the *measurement*,
not the model.

## What changed

Nothing. Same weights (`gv5-yolo11s/weights/best.pt`), same test split, same
`.val()` defaults as `train.py` used when gv5 was originally scored. `--conf` and
`--iou` were left unset so the call matches.

Test-split fingerprint asserted clean: `dataset_version: test4346-8bfbcc102487`,
4,346 frames, 2,930 backgrounds.

## What moved

| metric | gv5 as recorded | gv7.0 re-score | delta |
|---|---|---|---|
| overall mAP50 | 0.3525 | 0.3525 | +0.0000 |
| overall mAP50-95 | 0.1995 | 0.1995 | +0.0000 |
| overall precision | 0.5795 | 0.5795 | +0.0000 |
| overall recall | 0.3609 | 0.3609 | +0.0000 |

Per class, mAP50:

| class | gv5 | gv7.0 | delta |
|---|---|---|---|
| debris | 0.8695 | 0.8695 | +0.0000 |
| ghost_pot | 0.3143 | 0.3142 | −0.0001 |
| wreck | 0.2787 | 0.2794 | +0.0007 |
| plane | 0.2923 | 0.2904 | −0.0019 |
| ghost_net | 0.0093 | 0.0088 | −0.0005 |

## What did not move, and the one thing this buys

The ruler is intact. gv5's published table is reproducible on demand, so every
gv7 comparison is against a number that was re-derived today rather than
copied out of a nine-day-old file.

The per-class jitter is worth keeping. The split is byte-identical, so those
deltas are not data variance — they are non-deterministic NMS tie-breaking and
AMP reduction order on the GPU. That fixes an **empirical noise floor of roughly
±0.002 mAP50 per class** for single-seed evaluation on this hardware.

It is two orders of magnitude below the MDEs in §4.3 (wreck 0.064, ghost_pot
0.076), which confirms those MDEs are set by the size of the test split and not
by run-to-run hardware noise. The statistics bind, the hardware does not.

`plane` shows the largest jitter (−0.0019) for the expected reason: n=9, so a
single re-ranked box moves it further than anything else. §4.3 already forbids
quoting `plane`; this is one more reason.
