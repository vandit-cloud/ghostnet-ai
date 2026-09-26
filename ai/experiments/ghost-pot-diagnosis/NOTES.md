# ghost_pot diagnosis (24 Sep 2026)

Question: why does ghost_pot score 0.31 test mAP50 and "not fit its own training
data" (gv5 train recall 0.284 at conf 0.25, zero train/val gap), when it has
the most boxes of any class (7,434)?

Scripts: `ai/scripts/diagnose_ghost_pot.py` (recall by family, size, rotation
and IoU) and `ai/scripts/ghost_pot_fp_sheet.py` (train precision and a crop
sheet of the most confident false positives). Weights: gv8b-nosynth best.pt.

## The data: one source, a Roboflow export

* Every ghost_pot box comes from **GHOSTVISION**. The frames are Roboflow
  exports (`<original>_png_jpg.rf.<hash>.jpg`), 640x640.
* Train has **5,704 frames from 1,367 originals**, up to 12 augmented copies
  each. The copies include ~90° rotations and shears (`roboflow_copies_Rec5_00010.png`),
  which side-scan geometry does not allow.
* **Different images share one original name.** Copies 6, 10 and 12 of
  `Rec5_wcp_ss_star_00010` are a different scene. The name-based leakage
  check (0 originals shared between splits) is therefore not proof of no
  leakage.
* The splits are different surveys: train covers Rec1-21, BC, baycove, TI,
  MC; **val is 100% `Contact_*_sslo`, all colour-palette frames, median box
  18 px**; test is Rec8/9/14 plus a few others, 4% colour, median box 51 px. So
  val, which picks best.pt, is not representative of test.

## Finding 1: the model finds pots but will not commit (a confidence problem)

Train recall on 2,054 pot boxes (60 frames per survey family):

| conf | recall @IoU .5 | @IoU .1 |
|---|---|---|
| 0.25 (app) | ~0.11 | ~0.12 |
| **0.05** | **0.721** | 0.768 |

* It is not a box-looseness problem: IoU 0.5 and 0.1 give nearly the same
  recall.
* Rotated copies are not the problem: rotated 0.723 vs unrotated 0.717 at 0.05.
* Size matters only at the low end: under 16 px 0.49; 16-32 px 0.69; 64 px and
  up 0.81.
* The median confidence of a TRUE positive is **0.069**. Correct pot
  detections sit far below the 0.25 threshold the app ships.

So the earlier "fitting failure" reading was mostly this. The detector
localises 72% of training pots and scores them at ~0.07.

## Finding 2: many "false positives" are unlabelled pots

Train precision (400 frames, not one-to-one): 0.37 @0.05, 0.46 @0.10, 0.76 @0.25.
The median confidence of a false positive (0.084) is HIGHER than a true
positive's (0.069).

Eyeballing the 40 most confident FPs that have no truth box within IoU 0.1
(`top_false_positives_train.png`):
* **~23 are plainly pots**: a bright object, an acoustic shadow, often a
  tether line.
* ~12 are hairline-thin boxes on line or shadow features. That is the model's
  own quirk: only 6 of 7,434 labels are that shape.
* ~5 are ambiguous.

Mechanism: every unlabelled pot is a training example that says "this pot is
background". The loss pushes pot confidence down everywhere, and real pots and
"background" pots become indistinguishable in score. That explains the low
confidence, the poor ranking (mAP) and the zero train/val gap, which is a
labelling ceiling rather than model bias. Test labels are probably incomplete
too, so the test mAP50 of 0.31 likely UNDERSTATES the detector.

This corrects `trainfit-verdict`, which said "not label noise". It is label
noise of the omission kind; an IoU/size analysis cannot see it.

## Not a U-Net problem

Boxes fit pots well (tight IoU works) and pots are compact objects. The fix
is the labels, not the architecture.

## Fixes, ranked

1. **Complete the labels without hand-relabelling.** Mine candidates with the
   detector (conf >= ~0.1, no overlap with an existing box), group them by
   ORIGINAL rather than by copy, and review them in a fast accept/reject page
   (`build_box_review.py` exists). Accepted boxes propagate to every copy.
   Then retrain and re-score on a test set completed the same way.
2. **Per-class threshold for pots**, as a stopgap: at 0.25 the app shows ~11%
   of pots. Cheap, but it only helps once the ranking is fixed (precision is
   0.37 at 0.05).
3. **Rebuild val** from held-out Rec originals, grouped by original, so best.pt
   is not chosen on one colour-palette survey of 18 px contacts.
4. De-duplicate the Roboflow copies (keep one per original, drop the ~90°
   rotations, use our own physically valid augmentation) and de-alias the
   colliding names. Low priority: rotation measured harmless for recall.

Not done: the same measurement on gv5 (the loop failed on the space in its
weights path).
