# Training handoff — read this before touching the model

**For any AI assistant helping with GhostNet-AI training, and for the user.**

Everything here was learned the expensive way. Following it avoids repeating
mistakes that cost whole days. Last updated 2026-09-01.

---

# PART 1 — STATUS REPORT

## What the model is right now

**`gv2-yolo11s`** — YOLO11-S, trained 2026-09-01, 38 epochs (early-stopped from
40, best weights from epoch 26), 5h 57m.

`ai/experiments/gv2-yolo11s/weights/best.pt`

## What it was trained on

Five sources merged into one dataset, 14,116 images:

| Source | Images | What it contributes |
|---|---|---|
| AI4SHIPWRECKS | 6,976 | shipwrecks + most of the empty seabed |
| GHOSTVISION | 6,655 | derelict crab pots — the project's actual subject |
| SCTD | 327 | ships, aircraft, human objects |
| MARINE-PULSE | 88 | empty seabed only |
| SONARDETECT | 70 | mixed objects |

### What each source actually is, and what it contributes

| Source | Images | Empty | With objects | Boxes |
|---|---|---|---|---|
| AI4Shipwrecks | 6,976 | 6,062 (87%) | 914 | wreck 2,241 |
| GhostVision | 6,655 | 1,547 | 5,108 | ghost_pot 9,214 |
| SCTD | 327 | 22 | 305 | wreck 253, plane 57 |
| Marine-PULSE | 88 | 88 (all) | 0 | none |
| SonarDetect | 70 | 0 | 70 | debris 173 |

**GhostVision** is the only real dataset here: side-scan sonar of derelict crab
pots from a Delaware Bay survey, supplying 9,214 of the project's 11,885 boxes
-- three out of every four. The model is as good as GhostVision and no better.

**AI4Shipwrecks** is mostly empty water by design. It ships full waterfalls,
tiled here into 640 px squares, and a wreck occupies a tiny fraction of a survey
line. Its real contribution is negatives; the 2,241 wreck boxes are a side
effect. It is also the source of Trap 6.

**SCTD** is 327 hand-boxed academic images and the ONLY source of aircraft
anywhere: all 57 `plane` boxes. That is why `plane` recall is 0.000.

**Marine-PULSE** was imported deliberately with zero objects -- 88 hard
negatives. A detector trained only on images containing targets learns to always
find one.

**SonarDetect** is 70 images carrying an entire class: all 173 `debris` boxes.

**The whole class table falls out of this.** 9,214 boxes from a dedicated survey
gives a working class; 173 boxes from one small set gives a starved one; 57 gives
a class that detects nothing. There is one real dataset, one negative supply, and
three fragments.

Split (never change the test split — it is what makes results comparable):

| Split | Images | Empty seabed |
|---|---|---|
| train | 9,460 | 4,469 (47%) |
| val | 1,246 | 630 (51%) |
| test | 3,410 | 2,620 (77%) |

## The four classes and how much data each has

**This table explains every strength and weakness the model has.**

| Class | Train boxes | Test boxes | Test mAP50 | Honest verdict |
|---|---|---|---|---|
| `ghost_pot` | **7,434** | 567 | **0.297** | Works. Enough data. |
| `wreck` | 1,478 | 836 | 0.095 | Weak. Some data, noisy labels. |
| `debris` | **122** | 14 | 0.106 | Starved. Unmeasurable. |
| `plane` | **39** | 9 | 0.030 | Starved. **Recall 0.000 — detects none.** |

The pattern is exact: 7,434 boxes gives a working class; 39 boxes gives a class
that does nothing. There is no mystery here, only a data shortage.

## Overall test numbers (quote these, never validation figures)

```
precision 0.451    recall 0.178    mAP50 0.132    mAP50-95 0.052
```

Do not lead with mAP50 0.132. It is an **unweighted mean over four classes**, so
`plane` (9 boxes) and `debris` (14 boxes) count as much as `ghost_pot` (567).
Lead with **ghost_pot mAP50 0.297**.

## False alarms on empty seabed

| Threshold | Frames flagged |
|---|---|
| 0.10 | 11.5% |
| **0.20** (current setting) | **2.9%** |
| 0.50 | 0.3% |

**Say it with the caveat** (see Trap 6): *"On 2,620 held-out tiles carrying no
annotation, 2.9% were flagged at threshold 0.20. Roughly half come from survey
lines AI4Shipwrecks left entirely unannotated, so this is an upper bound."*

## Data downloaded but NOT yet used

**KLSG — 447 images sitting in `ai/data/raw/research/KLSG/`, never imported.**
385 ships + 62 aircraft. **Classification-only: whole-image labels, no boxes.**
It cannot be used for detection training without drawing boxes first. The 62
aircraft are the only aircraft data available anywhere, and `plane` is the
worst class — but 62 images need manual annotation to be usable.

**A partial download:** `ai/data/raw/research/Unconfirmed 126530.crdownload`,
1.49 GB. Almost certainly an interrupted SubPipeMini2. Delete or resume it.

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
| Detect ghost gear | **Works** — 0.297 on crab pots | Nets, not just pots. No public SSS net data exists. |
| Artificial vs natural | **Works** — 2.9% false alarms | Cleaner negatives (Trap 6) |
| Geotagging | **Done** — coordinates + error radius | Real survey metadata from Member 2 |
| Confidence / noise filtering | **Done** — calibrated, T=1.619 | nothing |
| Detect general debris | **Weakest** — 122 train boxes | This is where more data helps most |

**Priority if more training happens: the `debris` class.** It is the closest
thing to the problem statement's own wording and has almost no data.

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

**1. Import SubPipeMini2 and retrain.** It brings 6,335 YOLO boxes to a dataset
whose `debris` class has 122. It is the single biggest data gain available.

**Watch for:** pipelines are long linear structures, unlike compact crab pots,
and 6,335 boxes would swamp `debris` (122). Consider giving pipelines **their
own class** rather than merging into `debris`, so `debris` does not silently
become "pipeline detector". Map to `debris` in the contract, **never**
`ghost_net`.

**2. Annotate KLSG's 62 aircraft**, if `plane` matters. Manual box-drawing on 62
images. Probably not worth it — `plane` is not what the problem statement asks
for.

**3. Do not add more empty seabed.** See Trap 10.

## Things NOT worth doing

- Longer training on the current data. It early-stopped at epoch 38 with the
  best weights from 26 — it had stopped improving, so more epochs add nothing.
- Bigger models. 4 GB VRAM, and data is the limit, not capacity.
- Restratifying the split. It breaks comparability and does not fix the cause.

## Honest claims — what may and may not be said

**May be said:**
- "Detects derelict crab pots in side-scan sonar, mAP50 0.297 on 567 held-out
  boxes the model never saw."
- "Flags 2.9% of unannotated seabed tiles at threshold 0.20 — an upper bound."
- "Reports position with an error radius, or no position at all when navigation
  data is missing."

**May NOT be said:**
- "Detects ghost nets." It was trained on crab **pots**. No public side-scan
  dataset contains nets. A pot is fishing gear; it is not a net.
- "Detects aircraft or general debris." Recall 0.000 and 122 training boxes.
- "2.9% false-alarm rate on verified-empty seabed." See Trap 6.
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

- **No `test_geo.py`.** Geotagging is one of four named deliverables and has no
  automated test coverage.
- `SETTINGS.model_version` still reads `"v0-stub"` in payload provenance rather
  than the actual run name.
- `review_floor_artificial` is 0.20 and has never been chosen against a measured
  recall-vs-threshold curve. It happens to be reasonable; it was not derived.
