# Training handoff — read this before touching the model

**For any AI assistant helping with GhostNet-AI training, and for the user.**

Everything here was learned the expensive way. Following it avoids repeating
mistakes that cost whole days. Last updated 2026-09-03.

---

# PART 1 — STATUS REPORT

## What the model is right now

**`gv4-yolo11s`** — YOLO11-S, trained 2026-09-02, 40 epochs, 8h 13m.

`ai/experiments/gv4-yolo11s/weights/best.pt`

**`gv5-yolo11s` is training as of 2026-09-03 00:00** — 60 epochs, first run to
include the `ghost_net` class and the SubPipe temporal split. When it finishes,
replace the numbers below and re-run `make_demo.py` + `build_testbench.py`.

### Why gv3 does not exist as a result

gv3 was launched, ran 13 epochs, and was killed. It was a bit-exact replay of
gv2: SubPipe had been converted into `ai/data/interim/` but `build_dataset.py`
was never re-run, so `data/processed/` still held the gv2 dataset. Identical
data plus `seed: 0` gives an identical curve, digit for digit, which is how it
was caught.

**The lesson, and it is cheap to apply:** after importing anything, rebuild, and
read `data/processed/build_report.json` before launching. It states the sources
and the per-class box counts. gv3's own `provenance.json` recorded
`"debris": 122` at launch — the evidence was written down and nobody read it.

## What it was trained on

Eight sources merged into one dataset, 18,310 images:

| Source | Images | What it contributes |
|---|---|---|
| AI4SHIPWRECKS | 6,976 | shipwrecks + most of the empty seabed |
| GHOSTVISION | 6,655 | derelict crab pots — the project's actual subject |
| CHINA-OFFSHORE | 2,072 | **hard** negatives: gullies, riprap, scour, sand waves |
| SUBPIPE | 2,049 | submarine pipelines — this is what `debris` now is |
| SCTD | 327 | ships, aircraft, human objects |
| MARINE-PULSE | 88 | empty seabed only, but across five different sonars |
| GHOSTNET-HAND | 73 | **fishing nets, hand-annotated here** |
| SONARDETECT | 70 | mixed objects |

## The five classes and how much data each has

**This table explains every strength and weakness the model has.**

| Class | Train boxes | Test boxes | Verdict |
|---|---|---|---|
| `ghost_pot` | **7,434** | 567 | Works. Enough data. |
| `debris` | **1,556** | **629** | Was 122/14 and unmeasurable. Now both trained and testable. |
| `wreck` | 1,373 | 836 | Weak. Some data, noisy labels. |
| `ghost_net` | **215** | 36 | New in gv5. Thin — always quote the count beside the metric. |
| `plane` | **39** | 9 | Starved. 62 KLSG images are being annotated to fix this. |

The pattern is exact: 7,434 boxes gives a working class; 39 boxes gives a class
that does nothing. There is no mystery here, only a data shortage.

### Two caveats that must travel with these numbers

**`debris` test boxes are one survey.** 615 of the 629 come from a held-out
stretch of the same SubPipe track the training boxes come from — same AUV, same
sonar, same pipeline, separated by a 156-second gap in the timestamps. It
measures tracking through unseen seabed, NOT generalisation to debris
elsewhere. The only independent debris is the 14 sonar_detect boxes. Report
both; never quote 629 alone.

**`ghost_net` ground truth is ours.** 298 boxes hand-drawn on the 73 fishing-net
chips China-Offshore ships as classification-only. The convention — one box per
net panel, bounded by where the beads stop, never spanning empty seabed — is
documented with worked examples in `ai/data/annotate/ghost_net/_guide/` and
checked by `ai/scripts/check_annotations.py`. That makes the convention part of
the result, so keep it reproducible.

## Overall test numbers (quote these, never validation figures)

gv4, on 4,346 held-out tiles:

```
precision 0.191    recall 0.362    mAP50 0.247    mAP50-95 0.113
```

Trajectory on the same frozen test split — this is the number to show if anyone
asks whether the work is going anywhere:

| run | mAP50 | precision | recall |
|---|---|---|---|
| gv | 0.160 | 0.140 | 0.285 |
| gv2 | 0.132 | 0.451 | 0.178 |
| **gv4** | **0.247** | 0.191 | **0.362** |

Do not lead with mAP50 alone. It is an **unweighted mean over the classes**, so
`plane` (9 boxes) counts as much as `ghost_pot` (567), and adding a fifth thin
class mechanically drags it down. Lead with the per-class table and with the
false-alarm rate below.

Calibration: temperature 2.0167, fitted on val. Expected calibration error
**0.166 -> 0.063**. When the model says 70%, it approximately means 70%.

## False alarms on empty seabed

**This is the artificial-vs-natural requirement, and it is the strongest result
the project has.** gv4, on 2,930 held-out tiles carrying no annotation:

| Threshold | Frames flagged |
|---|---|
| 0.10 | 12.0% |
| **0.20** (current setting) | **5.2%** |
| 0.30 | 2.5% |
| 0.50 | 0.4% |
| 0.70 | 0.0% |

gv2 scored 1.30% at 0.30 against gv4's 2.5%, which reads like a regression and
is not one: gv4's test set adds 310 China-Offshore hard negatives — gully
fields, riprap, scour patches — that gv2 was never shown. It is a harder exam,
and comparing the raw percentages across the two is not valid.

**Say it with the caveat** (see Trap 6): *"On 2,930 held-out tiles carrying no
annotation, 2.5% were flagged at threshold 0.30. Some come from survey lines
AI4Shipwrecks left entirely unannotated, so this is an upper bound."*

## Data downloaded but NOT yet used

**KLSG — 447 images in `ai/data/raw/research/KLSG/`.** 385 ships + 62 aircraft.
Classification-only: whole-image labels, no boxes.

The 62 aircraft are the only aircraft data available anywhere and `plane` is the
worst class at 39 boxes. They are staged for hand-annotation at
`ai/data/annotate/plane/`, with the SCTD box convention captured in
`ai/data/annotate/plane/_guide/`: **box the aircraft's acoustic return, exclude
the cast shadow.** The 385 ships are lower priority — `wreck` already has 1,373
boxes.

The interrupted `Unconfirmed 126530.crdownload` is gone; SubPipeMini2 landed.

## Data registered but not downloaded

**SubPipeMini2.zip — 4.9 GB, Zenodo record 12666132.** 10,030 side-scan images,
6,335 YOLO detection boxes of submarine pipelines.

**Download the right archive.** The record has three:
- `SubPipe.zip` (28 GB) — far too big
- `SubPipeMini.zip` (6.1 GB) — **optical camera images, useless here**
- `SubPipeMini2.zip` (4.9 GB) — **the sonar one, with YOLO boxes. This one.**

## What the problem statement needs most

SIH26057 asks for detection of marine debris and separation of natural seafloor
from artificial anomalies. Against that:

| Requirement | State | What is missing |
|---|---|---|
| Artificial vs natural | **Strongest result** — 2.5% false alarms at 0.30 | nothing; keep the caveat |
| Confidence / noise filtering | **Done** — calibrated, ECE 0.063 | nothing |
| Geotagging | **Done** — coordinates + error radius | real survey metadata; no `test_geo.py` |
| Detect ghost gear | **Works** — crab pots; nets now trained too | `ghost_net` has 215 boxes, thin |
| Detect general debris | **Fixed for training** — 1,556 boxes | independent test data (see caveat above) |
| Detect aircraft | **Broken** — 39 boxes | the 62 KLSG images, being annotated |

### The gap nobody has started

Five of the fourteen core requirements in the build plan §2 are **unimplemented
code**, not accuracy problems, and none of them need a GPU:

| # | Requirement | State |
|---|---|---|
| 3 | Speckle / noise handling | missing — and §12 warns any filter must be validated against the model, so this one does imply a run |
| 5 | Acoustic shadow | **DONE** — `ghostnet/shadow.py`. Paired away-flank vs near-flank test, direction taken from nadir. Reports evidence for a reviewer; never suppresses a detection. |
| 6 | Sonar/vehicle dropouts | **DONE** — `ghostnet/dropout.py`. Frame warning plus a per-detection note; a detection >25% on dead rows has its uncertainty widened, matching the water-column precedent. |
| 8 | Sonar metadata parsing | partial — a hand-written JSON sidecar. No XTF/JSF reader, and no XTF file to test one against. |
| 12 | JSON / **CSV** reports | **DONE** — `ghostnet/report.py`, `write_csv(frames, path)`. `try_model.py` writes `report.csv` for every run. |

Requirement 3 (speckle) is the last of the named challenges still open, and it
is the one that needs a training run rather than an afternoon: §12 of the build
plan says any filter must be validated against the model, not assumed.

### What the dropout work found

The corpus contains almost NO dropouts: 2 frames in 500 carry any degenerate
row, and both are padding rather than lost pings -- 19 rows at the bottom edge
of an AI4Shipwrecks tile, 256 interior rows of a SubPipe tile that runs past
the end of its swath. Both pure black, mean 0.0.

That is not evidence dropouts are rare in the wild. These are curated tiles
whose authors already removed bad pings and cropped around annotated objects.
What the corpus DOES establish is the false-positive rate: the test fired twice
in 500 frames and was right both times.

Padding is reported as a dropout deliberately. The operational question is not
"did the sonar drop a ping" but "is this detection standing on real data", and
for that they are the same fact. Edge padding and an interior hole are still
distinguished in the wording, because an operator reads them differently.

### What the shadow work found, worth not re-learning

The obvious implementation -- "look just beyond the box, and if it is dark call
it a shadow" -- has ZERO discriminative power on this data. Measured over 561
wreck boxes against a matched control, `ratio < 0.55` fired on 42.2% of wrecks
and 42.1% of random patches. Any threshold chosen that way is noise.

What carries signal is the ASYMMETRY between an object's two flanks (median
0.384 against 0.255 for a random pair) -- so the test is paired, and needs
nadir to know which flank should be dark. That is why `shadow_context` returns
`not_evaluated` without geometry rather than guessing a nadir column.

Measured flank darkening by class, which matches the physics and is the reason
"absent" is never reported as doubt for a flat target:

    wreck      +0.263    stands proud, casts shadow
    ghost_pot  +0.058    small, low relief
    ghost_net  +0.023    lies flat, no shadow
    debris     +0.014    pipeline on or in the seabed, no shadow

---

# PART 2 — THE RULES

## Absolute rules — breaking these ruins the run

**1. Never change the test split.** `gv-yolo11s` and `gv2-yolo11s` are
comparable only because the test split is identical. Change it and every past
number becomes meaningless.

**2. Never train with `--workers` above 0 on this machine.** Worker processes
die at scale. It was fine on 1,335 images and broke at 7,147, so it fails
*late*, hours in, looking like a fluke.

**3. Never `--resume` onto a finished run, and never reuse a run name.** Resume
reads `last.pt`. Pointing it at pretrained weights silently restarts at epoch 1
and overwrites everything. New experiment = new `--name`.

**4. Never run two trainers at once.** 4 GB VRAM. Two trainers do not run half
as fast — throughput collapses to ~60 s/iteration and no epochs complete, while
`nvidia-smi` still shows 100% utilisation. `train_all.ps1` refuses to start
beside a live trainer; do not bypass that.

**5. Never hand-edit generated files.** `ai/data/processed/data.yaml`,
`contracts/*.schema.json`. Regenerate them.

**6. Never quote `raw_score` or validation metrics as results.** Calibrated
confidence and test metrics only.

**7. Never push to GitHub without asking the user.** Local commits are fine.

## Environment facts

- **GPU:** RTX 3050 Laptop, **4 GB VRAM**. This is the binding constraint.
- **Interpreter:** `E:\New folder\.venv\Scripts\python.exe` — always this one.
  Plain `python` may lack torch and silently fall back to CPU.
- `torch 2.13.0+cu126`, `ultralytics 8.4.134`. Do not change CUDA versions
  casually — it is a 2.6 GB download.
- **batch 4 fits at imgsz 640 with AMP. batch 8 does not.**
- If `SETTINGS.device` reports `cpu`, the torch install is broken. The GPU is
  fine.

## How to train

```powershell
cd "E:\New folder"
$PY = ".\.venv\Scripts\python.exe"

# whole pipeline, unattended: train -> calibrate -> false-alarm curve
powershell -ExecutionPolicy Bypass -File .\ai\scripts\train_all.ps1 -Name <new-name> -Epochs 40
```

~600–800 s/epoch, so 40 epochs is 6–9 hours. Before starting:

- `powercfg /change standby-timeout-ac 0` and stay plugged in. Windows sleeps on
  idle input, not idle CPU, and a sleeping laptop stops training.
- Do not close the PowerShell window; minimise it.
- Ordinary desktop work is fine. Games or video exports are not.

**To pause:** kill the *script*, not the trainer — the failure policy would
restart the trainer.

```powershell
$s = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
     Where-Object { $_.CommandLine -like "*train_all.ps1*" }
taskkill /F /T /PID $s.ProcessId
```

Resume with `-Resume` and the same `-Name` and `-Epochs`.

## Adding a new dataset

```powershell
# 1. convert to YOLO format (pick the importer that matches the annotation type)
& $PY ai\scripts\import_yolo.py --dataset SUBPIPE --dry-run
& $PY ai\scripts\import_yolo.py --dataset SUBPIPE

# 2. rebuild the merged dataset
& $PY ai\scripts\build_dataset.py --dry-run
& $PY ai\scripts\build_dataset.py

# 3. train
powershell -ExecutionPolicy Bypass -File .\ai\scripts\train_all.ps1 -Name <new-name>
```

Importers by annotation type: `voc_to_yolo.py` (VOC XML), `masks_to_yolo.py`
(pixel masks), `import_jsonl.py` (HuggingFace metadata.jsonl), `import_yolo.py`
(already YOLO), `import_classification.py` (folder-per-class, backgrounds only).

**Always `--dry-run` first.** Every importer supports it and writes nothing.

---

# PART 3 — TRAPS ALREADY HIT

Each of these cost real time. Do not rediscover them.

**Trap 1 — Progress is a new row in `results.csv`, never GPU utilisation.**
Three contending trainers once showed 100% utilisation and 3,569 MiB while
completing zero epochs for 92 minutes.

**Trap 2 — Count distinct epochs, not `results.csv` rows.** Two trainers
resuming from one checkpoint each append a row for the same epoch. One run had
41 rows for 40 epochs.

**Trap 3 — The `time` column resets at every `--resume`.** It is per-attempt
elapsed. Never sum it for total training time.

**Trap 4 — `taskkill /T`, never a bare kill.** `.venv\Scripts\python.exe` is a
shim that spawns a separate real python child. Killing the shim orphans the
child, which keeps holding the CUDA context.

**Trap 5 — Watchdogs keyed on log-write age are wrong.** A healthy slow epoch
looks dead and a second trainer gets launched beside the live one. Key liveness
on a new `results.csv` row.

**Trap 6 — "Background" tiles are NOT verified-empty seabed.** AI4Shipwrecks
annotates one target wreck per site, so lines that miss the target get a
completely blank mask even when the sonar imaged other structures. **100 of 261
waterfalls (38%) are blank this way**; 46% of train background tiles and 53% of
test background tiles come from such lines. Consequences: the model was trained
to ignore real structures; an empty label does not prove a tile is empty; and
the false-alarm rate is an upper bound.

**Trap 7 — The test split is 77% empty.** Hand-picking files from it gives
tiles with nothing in them, the model correctly reports nothing, and it looks
broken. Use `pick_samples.py`.

**Trap 8 — Write PowerShell in ASCII only.** PS 5.1 reads BOM-less UTF-8 as
cp1252, so an em dash becomes a curly quote, which PowerShell treats as a string
delimiter. One dash in a comment caused a parse error reported 54 lines away.

**Trap 9 — `Tee-Object` in PS 5.1 writes UTF-16LE.** Logs become unreadable to
grep. Pass `-Encoding ascii`. Old logs need decoding as `utf-16-le`.

**Trap 10 — Adding negatives costs recall.** Going from 30% to 47% background in
training tripled precision (0.140 → 0.451) and cut recall nearly in half (0.285
→ 0.178). Some of that is Trap 6 — the added negatives contain unannotated
objects. Do not add more negatives without a reason.

---

# PART 4 — IF MORE TRAINING HAPPENS

## Best use of the next run, in order

Items 1 and 2 below are **done** — gv5 is the run that carries them. Kept here
because the reasoning still applies to the next one.

**1. ~~Import SubPipeMini2~~ — done.** `debris` went 122 -> 1,556 training boxes.

The warning it came with proved half right: pipelines did swamp `debris`, but
they were not given their own class, because a live pipeline and a piece of
wreckage are both "artificial object on the seabed" within a closed four-value
contract. Watch for `debris` quietly becoming a pipeline detector — if the 14
independent sonar_detect boxes score far worse than the 615 SubPipe ones, that
is what has happened.

**2. ~~Annotate the fishing nets~~ — done.** 298 boxes on 73 chips, class
`ghost_net` at id 4. Note this reverses the old "no public dataset has nets"
finding, which was wrong.

**3. Annotate KLSG's 62 aircraft.** Staged at `ai/data/annotate/plane/`.
Re-assessed as WORTH doing, against the earlier note here: `plane` at 39 boxes
is the one class that detects nothing at all, and a per-class table with a
0.000 in it invites exactly one question. 62 images is two hours.

**4. Do not add more empty seabed.** See Trap 10. The China import took
negatives from 7,719 to 9,791 and that is enough — those were added for
DIFFICULTY (gullies, riprap) rather than volume, which is the only reason to
add negatives now.

## Things NOT worth doing

- Bigger models. 4 GB VRAM, and data is the limit, not capacity.
- Restratifying the split. It breaks comparability and does not fix the cause.
- Chasing datasets from the OpenSonarDatasets index. It was mined on 2026-09-03:
  BenthiCat has the right classes (cables, buoys, anchors, shipwrecks) but its
  Dataverse DOI is unpublished and it is CC BY-NC-SA; SWDD's 7,904 images are
  really 216 originals plus augmentation and video frames of one harbour wall;
  Seafloor Sediments is a 52 GB unsliceable archive of natural classes only.
  Recorded so nobody re-walks it.

**Longer training is no longer on this list.** It was, when gv2 early-stopped at
38 with best weights from 26. gv4 did not early-stop: its best epoch was its
LAST, epoch 40, with mAP50 still climbing. Check `results.csv` before assuming
convergence — the shape of the tail is the whole answer.

## Honest claims — what may and may not be said

**May be said:**
- "Detects derelict crab pots in side-scan sonar" — quote the per-class mAP50
  with its held-out box count beside it.
- "Flags 2.5% of unannotated seabed tiles at threshold 0.30 — an upper bound."
- "Reports position with an error radius, or no position at all when navigation
  data is missing."
- "Calibrated confidence: expected calibration error 0.063 after temperature
  scaling, down from 0.166."
- From gv5 on: "Detects derelict fishing net, on ground truth we annotated
  ourselves from a public classification dataset" — **always with the count**,
  298 boxes over 73 images, and a pointer to the convention in
  `ai/data/annotate/ghost_net/_guide/`.

**May NOT be said:**
- "Detects ghost nets" **without the count**. 215 training boxes is thin, the
  chips are one region of one survey, and the boxes are ours rather than an
  independent authority's. The claim is real; the qualifier is not optional.
- "Detects aircraft." 39 training boxes, recall 0.000, unchanged until the KLSG
  annotation lands.
- "2.5% false-alarm rate on verified-empty seabed." See Trap 6 — unannotated is
  not the same as verified empty.
- "Detects debris, validated on 629 held-out boxes." 615 of those are the same
  SubPipe survey. Say "one held-out survey track" or quote the 14 independent
  boxes.
- Any figure from the validation split.

**The scope boundary, stated plainly:** held-out test tiles come from the same
surveys as training — same sonar, same water, same gear. That is genuine
generalisation but within one domain. On a different sonar or different gear
type, expect a large drop. Say so before being asked; it is worth marks.

---

# PART 5 — WHERE THINGS ARE

| What | Where |
|---|---|
| Command reference | `docs/COMMANDS.md` |
| Testing walkthrough | `docs/TESTING_GUIDE.md` |
| Reading results / the UI | `docs/READING_RESULTS.md` |
| Dataset sourcing and licences | `docs/DATA.md`, `docs/DOWNLOAD_GUIDE.md` |
| Contract for Member 2 | `docs/HANDOFF.md` |
| Current model | `ai/experiments/gv2-yolo11s/weights/best.pt` |
| Per-run record | `ai/experiments/<run>/provenance.json` |
| Claims registry | `ai/data/provenance/dataset_candidates.csv` |

## Known gaps, not yet closed

- **Five PS requirements are unimplemented code** — shadow context, dropouts,
  speckle, XTF parsing, CSV export. See "The gap nobody has started" in Part 1.
  None need a GPU; four of the five can be done while a model trains.
- **No `test_geo.py`.** Geotagging is one of four named deliverables and has no
  automated test coverage.
- ~~`SETTINGS.model_version` reads `"v0-stub"`~~ **fixed.** It now names the run:
  from `models/trained/ghostnet.json` for the promoted model, else from the
  experiment directory. `"v0-stub"` survives only for the genuinely
  weightless case, which is a real state worth labelling.
- `review_floor_artificial` is 0.20 and has never been chosen against a measured
  recall-vs-threshold curve. It happens to be reasonable; it was not derived.
  `testbench.html` now has the slider that would let it be derived.
- **`debris` has no independent test data worth the name** — 14 boxes. Every
  other debris number is one SubPipe survey.
- **`check_annotations.py` thresholds are calibrated for nets in survey tiles**
  (35% per box, 75% union). For the plane chips they must be relaxed with
  `--max-cover 0.95 --max-union 0.95`, or almost everything false-alarms.
