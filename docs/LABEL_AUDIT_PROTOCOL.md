# Label audit protocol — gv7.1

**How to run the `wreck` label audit without invalidating every measurement we
have.** Written 2026-09-13. Applies to `ai/data/annotate/wreck_audit/`.

---

## 1. What this audit is, and what started it

`wreck` scores precision 0.42 / recall 0.32 on the test split. §2 of the gv7
plan suspects label noise. gv7.1 is the run that tests that suspicion, and it
cannot start until the labels are actually audited.

A mechanical scan of all 13,896 training frames found **zero** duplicates,
out-of-bounds boxes, or degenerate boxes. So if errors exist they are semantic —
a box around the wrong object, drawn too loosely, or missing — and only a person
can adjudicate those.

**Scope: `wreck` boxes in train and val only. 722 frames, 1,658 boxes.**

---

## 2. The queue, and why it is only an order

`ai/scripts/rank_label_suspects.py --class wreck` produces
`ai/data/annotate/wreck_audit/queue.csv`: **446 findings across 247 frames**,
ranked most-suspicious first.

| kind | n | what it means |
|---|---|---|
| `orphan_label` | 304 | a labelled box the model sees nothing at |
| `loose_box` | 121 | model and label overlap poorly (IoU 0.10–0.50) |
| `missing_label` | 20 | confident prediction where no label exists |
| `class_conflict` | 1 | model confidently calls it another class |

That is 247 frames to look at instead of 722 — but read the ranking correctly:

> **This ranks labels by disagreement with a model that was trained on those
> labels.** A box the model misses may be a bad label *or* a real model failure,
> and nothing here can tell them apart. An error the model learned faithfully
> will not be flagged at all.

So the queue is a **triage order, not a defect list**. Every row is a question.
**"Label was right, the model is wrong" is a valid and expected verdict** — record
it, because a pile of those is evidence about the model rather than the labels,
and it is the result that would make gv7.1 not worth running.

---

## 3. Rules that are not negotiable

**3.1 — Never touch the test split.** Auditing train/val while test keeps its
errors measures a better model with a worse ruler; auditing test silently
destroys comparability with gv1–gv6 (plan §3.1). The ranking script does not
offer `--splits test`, and its manifest refuses to emit an interim target for
any frame that landed in test.

If a test audit is ever wanted it is a separate, announced, one-time event, and
gv5 must be re-scored on the corrected test set too — that is what `gv7.0` is
for, and it has already been run once.

**3.2 — Corrections go to `interim/`, never to `processed/`.**
`ai/data/processed/` is rebuilt in place by `build_dataset.py`; anything edited
there is destroyed by the next rebuild and, worse, silently disagrees with its
source in the meantime. `manifest.json` maps each flagged frame to its real
interim label file.

Two layouts exist. `AI4SHIPWRECKS` keeps upstream split directories
(`interim/AI4SHIPWRECKS/train/labels/`). `SCTD` is flat
(`interim/SCTD/labels/`) because we split it ourselves.

**3.3 — Record every verdict, including "no change".** `queue.csv` has empty
`verdict` and `reviewer` columns. An unfilled row is visibly unreviewed; a row
marked `ok` is a decision. Do not delete rows.

Suggested verdicts: `fixed-tightened`, `fixed-removed`, `fixed-added`,
`fixed-reclassed`, `ok-label-right-model-wrong`, `unsure`.

---

## 4. The split-perturbation trap

The split draw is deterministic — `random.Random(seed=0)` — **given the same set
of groups**. Editing box coordinates does not change that set, so membership is
preserved and this is safe.

**But `assign_groups` walks groups rarest-class first.** If a correction deletes
the *last* `wreck` box from a frame, that group's class composition changes, the
greedy walk can reorder, and frames can move between splits. This is the same
mechanism that moved `ghost_net`'s test boxes 36 → 38 when PLANE-HAND was
imported (plan §1.5).

So `fixed-removed` verdicts carry a risk the other verdicts do not. After the
rebuild:

```bash
python ai/scripts/build_dataset.py
python ai/scripts/verify_dataset.py           # do NOT pass --write yet
```

The test split has **two** digests and they fail differently:

* `image_list` changed → the split moved. **Stop.** The audit perturbed
  membership; nothing measured after this is comparable. Revert and reconsider.
* `label_content` changed while `image_list` held → a test label was edited.
  **Stop.** Rule 3.1 was broken somewhere.
* both unchanged → the ruler is intact and gv7.1 may proceed.

Only run `verify_dataset.py --write` after a *deliberate, announced* test change.

---

## 5. The loop

```bash
# 1. build the queue (already done; re-run after any dataset change)
python ai/scripts/rank_label_suspects.py --class wreck --device cpu --render 150

# 2. review. _review/ holds overlay sheets, numbered by rank.
#    Edit the interim label file named in manifest.json. Fill in queue.csv.

# 3. rebuild and CHECK — see section 4
python ai/scripts/build_dataset.py
python ai/scripts/verify_dataset.py

# 4. only then train
python ai/scripts/train.py --model yolo11s --name gv7.1-yolo11s --epochs 60
```

Step 4 is ~10.4 hours, and §6 requires three seeds before promotion, so budget
~31 hours of GPU for a promotable gv7.1 result.

---

## 6. What to actually fix, for `wreck`

Follow the convention the class already has, rather than inventing a better one
mid-corpus — two contradictory definitions are worse than one imperfect one.

* **Tighten to the acoustic return.** SCTD's convention boxes the return and
  leaves the cast shadow outside. AI4SHIPWRECKS tiles follow the same idea.
  A box that includes the shadow is a `loose_box`, and it is the error most
  likely to explain precision 0.42.
* **Do not add wrecks the corpus never claimed.** `missing_label` findings are
  the model's opinion. Add a box only if you can see the object.
* **Reclass rather than delete** when the object is real but the class is wrong.
  There is exactly one `class_conflict` (`SCTD__000154`, model says `plane`),
  which is worth looking at first precisely because it is unique.
* **Leave ambiguous cases alone and mark `unsure`.** An audit that introduces
  its own noise is worse than no audit.

---

## 7. Honest scoping

247 frames at a careful minute each is roughly **4–5 hours of human work**, plus
~10 hours per training seed afterwards.

**That does not fit before 18 September**, and it should not be attempted in a
rush — a hurried audit produces a dataset nobody can trust and no way to tell
which boxes were touched carefully. Two defensible options:

1. **Do not start it.** gv7.1 stays unrun and is reported as such. The gv7 plan
   already treats an unrun stage as a legitimate state.
2. **Review the top 50 only**, as a *sample*, and report what it found without
   retraining: "we audited the 50 most suspicious `wreck` labels; n were wrong."
   That is a real finding about data quality, costs about an hour, needs no GPU,
   and it does not touch the dataset at all — so nothing downstream is put at
   risk.

Option 2 is the better use of the time remaining. It answers the question §2
actually asked — *is `wreck` precision a label problem?* — without spending
31 GPU-hours to find out.
