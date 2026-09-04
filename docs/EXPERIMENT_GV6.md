# gv6 — did synthetic ghost nets fix the headline class?

**Answer: no. `ghost_net` recall stayed at exactly 0.000.**

This document records a negative result. It is kept because the experiment was
designed to be attributable, so "no" is a real finding rather than a failed run,
and because the reason it failed is a property of the sonar physics rather than
of the code.

- **Run:** `gv6-yolo11s`, launched 2026-09-03 19:55, 60/60 epochs, ~860 s/epoch,
  batch 4, one attempt, no supervisor intervention.
- **Artifacts:** `ai/experiments/gv6-yolo11s/`
- **Outcome:** NOT promoted. `gv5-yolo11s` remains the shipped model.

---

## 1. The hypothesis

`ghost_net` is the problem statement's actual object and it did not work on gv5:
mAP50 0.009, recall 0.000, on 36 held-out real boxes. The obvious explanation was
starvation — only 215 training boxes, against 2,171 for `debris`.

`ai/scripts/synth_ghost_net.py` composites **real** net returns onto **real**
train-split seabed: 1,364 frames, 2,031 boxes, taking `ghost_net` from 215 to
2,246 training boxes. Every net pixel is a real net pixel; only the arrangement
is synthetic, and its position is known exactly because we chose it.

**The experiment tested one variable.** Speckle filtering was deliberately
excluded (it measured negative on gv5) so that any movement was attributable to
the synthetic data alone. `wreck`, `debris` and `ghost_pot` were the controls.
The synthetic frames went entirely to train — a `ghost_net` score measured on
generated nets would be self-congratulation.

The test split was held byte-identical to gv5: 4,346 frames, `ghost_net` n=36.

---

## 2. The result

| class | n (test) | gv5 mAP50 | gv6 mAP50 | gv6 recall |
|---|---|---|---|---|
| debris | 629 | 0.869 | 0.879 | 0.827 |
| ghost_pot | 567 | 0.314 | 0.345 | 0.480 |
| wreck | 836 | 0.279 | **0.238** | 0.334 |
| plane | 9 | 0.292 | 0.378 | 0.333 |
| **ghost_net** | **36** | **0.009** | **0.024** | **0.000** |
| **overall** | 4,346 | 0.352 | 0.373 | 0.395 |

Overall precision fell from **0.580 to 0.373**; overall recall rose 0.361 → 0.395.

**`ghost_net` did not move in any way that matters.** Recall is still exactly
zero. Precision went from 1.000 to 0.000 — gv5 made one correct net prediction,
gv6 made none. The mAP50 rise 0.009 → 0.024 is a sliver of PR-curve area on
n=36 and is not evidence of a working class.

**`plane` did not improve either, despite appearances.** Recall is byte-identical
between the runs at 0.3333 — that is exactly 3 of 9. gv6 found the same three
aircraft gv5 found; the mAP50 rise is re-ranking, not detection. On n=9, recall
cannot move in steps smaller than 0.111, so it is not capable of measuring a
0.086 difference. `plane` must not be quoted at this sample size.

### Cost: more background activations

On the same 2,930 held-out tiles carrying no annotation, at matched raw
threshold:

| raw threshold | gv5 | gv6 |
|---|---|---|
| 0.10 | 7.8% | 12.6% |
| 0.20 | 4.1% | 6.7% |
| 0.25 | 2.9% | 4.7% |

Roughly 1.6× the false-alarm rate at every threshold, consistent with the
precision drop. Note this is the **raw** scale; the deployed review floor is
applied to calibrated confidence, and gv6's temperature refit to 1.657 (from
2.722), so a deployed figure would need `derive_review_floor.py` re-run. That was
not done, because gv6 is not shipping.

Phrase any of these as "tiles carrying no annotation", never "verified-empty
seabed" — see Part 3b of `READING_RESULTS.md`.

---

## 3. Why it failed — physics, not data volume

A **crab pot** is rigid and stands proud of the seabed. It returns a compact
bright blob *and* casts a clean acoustic shadow: two strong, independent cues.

A **net** lies flat. It blocks almost nothing, so it casts barely any shadow, and
it returns a faint low-contrast curvilinear texture. One weak cue.

Synthesis multiplied the number of *examples* tenfold. It could not manufacture a
*cue* that the sonar physics does not put in the image. That is the whole result,
and it also explains the standing gap between `ghost_pot` (0.345) and `ghost_net`
(0.024) — the two classes are both derelict fishing gear, and the difference
between them is acoustic, not annotative.

**This rules out the two explanations that look most likely from the outside:**

1. **Not annotation quality.** The 2,031 synthetic boxes have *perfect* ground
   truth by construction — the compositor chose where each net went, so the box
   cannot be misplaced. A model that cannot learn the class from 2,031
   perfectly-labelled examples is not being held back by hand-drawing.
2. **Not sample size.** 10× the boxes moved recall by 0.000.

---

## 4. What was decided

- **gv5 stays the shipped model.** gv6 buys +0.021 overall mAP50 and better
  calibration (ECE 0.118 → 0.050), against ~1.6× background activations, a
  precision collapse, and a real `wreck` regression on n=836 — a class whose
  numbers actually mean something. The mAP gain is concentrated in classes that
  already worked.
- **`ai/models/calibrator/temperature.json` was reverted** to the gv5 fit
  (temperature 2.722). It had been refitted against gv6 weights while
  `ghostnet.pt` was still gv5, which would have scored the shipped model with a
  temperature fitted for a different one.
- **This is reported as a limitation, not hidden.** Naming an unfixed failure
  mode with a measured reason is worth more than a fractional mAP change.

## 5. What NOT to try next

- **More synthetic nets.** Tested here. The answer is no.
- **Detecting nets by elimination** (if not wreck/plane/debris/pot, call it a
  net). The residual bucket is mostly seabed; this would give the headline class
  a precision near zero and destroy the false-alarm number six runs earned. The
  `unknown` contract class already implements the honest version of this idea.
- **Despeckling at inference.** Measured at −13% mAP50 on gv5. Ships OFF.

The one open candidate with a measured argument behind it is a model **trained**
on despeckled data — no domain mismatch, and the robustness table says there is
something real to gain on noisy input. See `sih26057-transform-symmetry`.
