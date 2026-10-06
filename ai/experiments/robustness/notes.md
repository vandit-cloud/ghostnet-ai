# Robustness sweep, gv5 (26 Sep 2026)

`python ai/scripts/robustness_report.py --data "E:/New folder/ai/data/processed/data.yaml"`,
on the frozen test split `test4346-8bfbcc102487` (4,346 frames, 2,930 carrying no
annotation). Table: `REPORT.md`. Raw numbers: `robustness_metrics.json`.

**The harness is on the ruler.** The clean row reproduces gv5's record exactly:
mAP50 0.3525 and 7.82% empty-seabed false alarms at the shipped raw gate 0.10.

## What it says

**Two failure modes, and only one of them is loud.**

- **Quiet failure: speckle, low contrast, heavy blur.** Recall falls *and* the
  false-alarm rate falls with it. At speckle 0.50 the model finds 21% of objects
  and flags 1.4% of empty seabed, against 36% and 7.8% clean. A survey in bad
  conditions produces fewer detections, which reads as "less debris here". It is
  the strongest measured argument for a sonar-quality gate that says
  "insufficient coverage" instead of letting an empty result stand.
- **Loud failure: dropout.** With 10% of rows lost in 4-16-row bursts, empty-seabed
  false alarms go from 7.8% to **26.4%**, and precision from 0.58 to 0.12. The
  zeroed stripes create edges the detector reads as objects. Moderate blur (kernel 9)
  is the other condition that raises false alarms (+2.2 pp).

**The single-tile curve in the older docs was wrong in both directions.** It said
speckle "kills it" at 0.35 and blur "barely hurts". On the full split, speckle 0.35
costs 0.090 mAP50 and blur 9 costs 0.146.

**Per class:**
- `ghost_pot` recall goes to 0.007 at speckle 0.35. A pot is a small bright blob, and
  speckle is small bright blobs.
- `debris` (mostly SubPipe pipelines) survives speckle (0.734 at 0.50) but collapses
  at contrast 0.25 (0.011). A pipeline is a long, low-contrast line.
- `wreck` recall goes to 0.024 at blur 9. Wreck detection relies on fine edges, and
  wrecks are mostly small in frame (see `wreck_recall_by_size.json`).
- `ghost_net` box recall is 0.000 everywhere, as it is clean. The U-Net that serves
  nets was not stressed here: 11 test chips cannot carry a curve.

## Open question this raises

`ghostnet.dropout` escalates uncertainty when a box overlaps 25% or more dropout
rows. Nobody has checked whether the extra false boxes under `dropout_10` sit on the
lost rows (so the escalation catches them) or beside them (so it does not). That is
the first thing to measure before the health gate treats dropout as handled.

## Caveats

- The degradations are named, seeded stresses, not models of a real sonar
  (module docstring). The speckle model is unit-mean gamma. The outside review's
  "sigma 0.35" never recorded its model, so the two are not the same axis.
- The per-class rows for `plane` (9 boxes) and `ghost_net` (36) are too small to read.
- Range-dependent behaviour (near versus far from nadir) is not measured: most test
  tiles carry no nadir position.
- The false-alarm rates are upper bounds, as always: "no annotation" is not "verified empty".
