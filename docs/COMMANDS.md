# Command reference

Every command you need, what it is for, and when you would run it.
Verified against the scripts on 2026-08-31 -- flags here match `--help`.

**Set this once per terminal.** All commands below assume it:

```powershell
cd "E:\New folder"
$PY = ".\.venv\Scripts\python.exe"
```

Why `$PY` and not plain `python`: the venv was built with
`--system-site-packages`, and calling the wrong interpreter is how a run ends up
on CPU without saying so. If anything ever reports `device=cpu` on this machine,
that is a broken torch install, not a missing GPU.

Almost every script takes `--dry-run`. **Use it first.** It reports what would
happen and writes nothing.

---

## 0. The one command that does everything

```powershell
powershell -ExecutionPolicy Bypass -File .\ai\scripts\train_all.ps1 -Name <run-name>
```

Trains, then fits calibration, then measures the false-positive rate, logging to
`ai/experiments/<run-name>.pipeline.log`. Runs unattended; close the scrollback
and read the log later.

| Flag | Meaning |
|---|---|
| `-Name` | required; experiment folder under `ai/experiments/` |
| `-Epochs` | default 40 |
| `-Patience` | default 12; early-stop after this many epochs with no gain |
| `-Batch` | default 4; 4 GB VRAM does not reliably hold 8 at 640 |
| `-Model` | default `yolo11s`; also `yolo11n` or a path to a `.pt` |
| `-Resume` | continue an interrupted run from `last.pt` |
| `-SkipTrain` | run only calibration + background eval on an existing run |

It refuses to start if another trainer is alive. That is deliberate: two
trainers sharing 4 GB do not run half as fast, they collapse to ~60 s/it and
complete no epochs.

---

## 1. Data: get it on disk and describe it

| Command | What it does |
|---|---|
| `& $PY ai\scripts\inventory.py --verbose` | Scan `ai/data/` and report what is ACTUALLY there. Writes `ai/data/provenance/data_inventory.csv`. Run after every download. |
| `& $PY ai\scripts\fetch_weights.py` | Download `yolo11n.pt` / `yolo11s.pt` into `ai/models/pretrained/`. Weights are build inputs, not source, so git does not carry them. |

Acquisition steps (logins, emails, archive URLs) are in `docs/DOWNLOAD_GUIDE.md`;
what each source is and why it was chosen is in `docs/DATA.md`.

## 2. Convert each source to YOLO format

One importer per annotation format. All write into `ai/data/interim/<ID>/`.

| Command | For |
|---|---|
| `& $PY ai\scripts\voc_to_yolo.py --dataset SCTD` | Pascal VOC XML boxes (SCTD) |
| `& $PY ai\scripts\masks_to_yolo.py --dataset AI4Shipwrecks` | Pixel masks; tiles full waterfalls into 640 px and derives boxes |
| `& $PY ai\scripts\import_jsonl.py --dataset GhostVision_DatasetAndModels --out ai\data\interim\GHOSTVISION` | HuggingFace-style `metadata.jsonl` (GhostVision) |
| `& $PY ai\scripts\import_yolo.py --dataset SONARDETECT --only-classes other` | Already-YOLO data; remaps classes, screens contaminated frames |
| `& $PY ai\scripts\import_classification.py --dataset MARINE-PULSE` | Folder-per-class sets, imported for their BACKGROUND images only |

Useful flags:
- `--collapse artificial` (voc_to_yolo) -- merge classes into one artificial class
- `--neg-ratio 2.0` (masks_to_yolo) -- how many empty tiles to keep per positive
- `--no-screen` -- skip the contamination screener; you almost never want this

## 3. Merge into one leakage-safe split

```powershell
& $PY ai\scripts\build_dataset.py --dry-run
& $PY ai\scripts\build_dataset.py
```

Writes `ai/data/processed/` plus `data.yaml` and `build_report.json`.

Splits by GROUP, never by file: exact duplicates are dropped and every tile of
one waterfall stays on the same side, so the model cannot see a near-copy of a
test image during training.

- `--sources SCTD AI4SHIPWRECKS` -- build from a subset
- `--ratios 0.70 0.15 0.15` -- train/val/test
- `--seed 0` -- keep this fixed or results stop being comparable

**Never hand-edit `data.yaml`.** It is generated.

## 4. Train

```powershell
& $PY ai\scripts\train.py --name <run> --epochs 40 --patience 12 --workers 0
& $PY ai\scripts\train.py --name <run> --dry-run
& $PY ai\scripts\train.py --name <run> --resume
```

`--workers 0` is load-bearing on this machine. Worker processes die at scale --
it was fine on 1,335 images and broke at 7,147, so it fails late and looks like
a fluke. On Linux, raise it.

Budget ~400-600 s/epoch, so a 40-epoch run is roughly 5-7 hours.

`--resume` continues from the CHECKPOINT, which holds the optimiser state, the
epoch counter and the LR schedule. Never point `--resume` at pretrained weights:
it silently restarts at epoch 1 and overwrites the run.

Training ends by evaluating `best.pt` on the held-out **test** split and writing
`test_metrics.json`. **Quote those numbers, never the validation ones.**

## 5. After training -- both of these are required

```powershell
& $PY ai\scripts\fit_calibration.py --weights ai\experiments\<run>\weights\best.pt --device 0
```

Fits the temperature that turns detector scores into honest probabilities.
Writes `ai/models/calibrator/temperature.json`. **Until this matches the current
weights the pipeline refuses to report `low` uncertainty** and caps at `medium`.
Fitted on val, never on test.

```powershell
& $PY ai\scripts\evaluate_background.py --weights ai\experiments\<run>\weights\best.pt --split test --batch 8
```

The artificial-vs-natural number: how often the detector cries wolf on seabed
verified to be empty. This is the headline metric for the problem statement.
Use `--batch 8`, not the default 32 -- 4 GB will not hold 32 at 640.

## 6. Demo and contract

| Command | What it does |
|---|---|
| `& $PY ai\scripts\make_demo.py --weights ai\experiments\<run>\weights\best.pt` | Real model output on real test tiles -> `demo_data.json`. Picks hits, misses, clean seabed and false alarms, so the demo is honest. Full workflow in section 8. |
| `& $PY ai\scripts\export_schemas.py` | Regenerate `contracts/*.schema.json` from `ai/ghostnet/contract.py` |
| `& $PY ai\scripts\export_schemas.py --check` | Fail if the schemas are stale. Runs in the test suite. |
| `& $PY ai\scripts\make_fixtures.py` | Rewrite `ai/fixtures/*.json`, the example payloads Member 2 builds against |

**Never hand-edit `contracts/*.schema.json`.** They are generated from the
Python contract; editing them makes the code and the schema disagree silently.

## 7. Checks

```powershell
& $PY -m pytest ai\tests -q
$env:GHOSTNET_WEIGHTS = "E:\New folder\ai\experiments\<run>\weights\best.pt"
```

`detect()` returns empty detections until `GHOSTNET_WEIGHTS` points at a model.
That is not a bug -- it is the documented behaviour Member 2 builds against.

---

## 8. Test the trained model by hand

Full step-by-step walkthrough, including image requirements and troubleshooting: **`docs/TESTING_GUIDE.md`**. How to read the output, and
every part of the test bench page explained: **`docs/READING_RESULTS.md`**.
Quick reference below.

Both of these go through `ghostnet.detect()`, the same function the application
imports. Loading the `.pt` with ultralytics directly would skip calibration, the
review policy and contract validation -- you would be testing a code path
nothing actually runs.

**Run it on your own images:**

```powershell
& $PY ai\scripts\try_model.py --images "C:\path\to\folder"
& $PY ai\scripts\try_model.py --images pic.png --conf 0.10
& $PY ai\scripts\try_model.py --images folder --weights ai\experiments\<run>\weights\best.pt
```

Takes a single image or a folder (recursive). Writes an annotated JPG plus the
full JSON payload per image into `ai/experiments/tryout/`.

- **Amber box** = reported to a reviewer. **Blue box** = found, but held below
  the review floor. Seeing what the floor hides is the point.
- Confidence drawn is CALIBRATED, never `raw_score`. Both are in the JSON.
- With no `--weights` and no `$GHOSTNET_WEIGHTS`, it picks the newest run's
  `best.pt` and says so.
- `--json-only` skips the images; `--conf` changes only the floor it draws at.

**Build the visual test bench** (a self-contained page with a live threshold
slider, real tiles, and the measured false-alarm curve):

```powershell
& $PY ai\scripts\make_demo.py --weights ai\experiments\<run>\weights\best.pt --conf 0.10 --hits 8 --misses 5 --clean 5 --false-alarms 5
& $PY ai\scripts\build_testbench.py --run <run>
```

Writes `ai/experiments/<run>/testbench.html`. Open it in a browser. Neither it
nor `demo_data.json` is committed -- they are ~2.3 MB each and regenerate from
the weights.

The slider exists because the review floor is the one setting you cannot pick
from a metrics table: raising it removes false alarms and real detections
together. The page reports the nearest threshold ACTUALLY measured on the 2,620
empty tiles rather than interpolating a number nobody observed.

**Known-good samples for a smoke test** (gv2-yolo11s, verified 2026-09-01):

| frame | expected |
|---|---|
| `AI4SHIPWRECKS__Artificial_Reef_06__x0_y960.png` | 1 detection, top 0.490 |
| `AI4SHIPWRECKS__Artificial_Reef_06__x480_y960.png` | 2 detections, top 0.517 |
| `AI4SHIPWRECKS__Barge_No_1_03__x1088_y1440.png` | 2 detections, top 0.227 |
| `AI4SHIPWRECKS__Artificial_Reef_01__x0_y0.png` | 0 detections (empty seabed) |

All live in `ai\data\processed\test\images\`. Test both directions: a model that
finds everything and a model that finds nothing each pass half of these.

**`localization: "none"` and a geometry warning on every payload is correct.**
These tiles carry no navigation metadata, so the pipeline reports the detection
WITHOUT a position rather than inventing one.

## Pausing and resuming a run

Ultralytics writes `last.pt` at the END of every epoch, so a pause costs you at
most the epoch in progress -- up to ~11 minutes. If you can, wait for a new row
to appear in `results.csv`, then stop immediately after it.

**Stop it.** One command, because it kills the script AND the trainer together:

```powershell
$s = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
     Where-Object { $_.CommandLine -like "*train_all.ps1*" }
taskkill /F /T /PID $s.ProcessId
```

`/T` kills the whole tree. It matters twice over: `.venv\Scripts\python.exe` is
a shim that spawns a separate real python child, and killing the shim alone
leaves that child running and holding the CUDA context.

**Kill the script FIRST, never the trainer alone.** `train_all.ps1` cannot tell a
deliberate kill from a crash: it sees a non-zero exit with progress made, and
its failure policy relaunches the trainer. Taking down the script first removes
the thing that would restart it.

**Confirm nothing survived** before you use the GPU for anything else:

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -like "*train.py*" }
```

Empty output means the GPU is yours. If a process is still listed, kill it with
`taskkill /F /T /PID <its id>`.

**Resume where you left off:**

```powershell
powershell -ExecutionPolicy Bypass -File ./ai/scripts/train_all.ps1 -Name gv2-yolo11s -Epochs 40 -Resume
```

`-Resume` continues from `last.pt`, which carries the optimiser state, the epoch
counter and the LR schedule -- so epoch 23 picks up as epoch 23, not as a fresh
run at a restarted learning rate. Keep `-Epochs` the same as the original run;
it is the TOTAL, not a number to add.

Pausing is cheap but not free: each stop loses a partial epoch, so five pauses
costs roughly an hour. A run left alone finishes sooner than one you babysit.

## When something goes wrong

**Is a trainer actually running?**

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*train.py*" } | Select-Object ProcessId, CreationDate
```

**Kill one properly.**

```powershell
taskkill /F /T /PID <pid>
```

`/T` matters. `.venv\Scripts\python.exe` is a shim that spawns a separate real
python child; killing the shim alone leaves the child holding the CUDA context.
To stop a supervisor while KEEPING its trainer alive, use `/F` without `/T`.

**Is it making progress?**

```powershell
Get-Content ai\experiments\<run>\results.csv -Tail 3
nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv
```

Progress is a **new row in `results.csv`**, never GPU utilisation. Three
contending trainers showed 100% util and 3569 MiB while completing zero epochs.

**Count epochs correctly.**

```powershell
(Get-Content ai\experiments\<run>\results.csv | Where-Object { $_ -match '^\d' } | ForEach-Object { ($_ -split ',')[0] } | Sort-Object -Unique).Count
```

Distinct epoch numbers, not row count: two trainers resuming from one checkpoint
each append a row for the same epoch.

**Do not sum the `time` column.** It resets to zero at every `--resume`, so it is
per-attempt elapsed, not cumulative. Use the pipeline log timestamps instead.

**Out of memory:** lower `-Batch` (4 -> 2 -> 1) before touching `--imgsz`.
Changing image size changes the results; changing batch size mostly does not.

**Pushing to GitHub:** ask first. Agreed protocol, because the repo is shared
with Member 2 and a push is not undoable the way a local commit is.

---

## Annotating a class by hand

```powershell
python ai\scripts\stage_annotations.py --list          # how far each class has got
labelImg "<repo>\ai\data\annotate\<class>\images" `
         "<repo>\ai\data\annotate\<class>\predefined_classes.txt" `
         "<repo>\ai\data\annotate\<class>\labels"
python ai\scripts\check_annotations.py --dir ai\data\annotate\<class>
```

**Press `Y` in labelImg until the bottom-left button reads YOLO.** PascalVOC
writes `.xml` the importer cannot read, and worse: labelImg reloads an existing
`.xml` in preference to a `.txt` and silently flips the format back every time
you open that image. If a file refuses to save as YOLO, delete its `.xml`.

The checker's thresholds are calibrated for nets in wide survey tiles. For
tightly cropped chips such as the KLSG aircraft, relax them or almost
everything false-alarms:

```powershell
python ai\scripts\check_annotations.py --dir ai\data\annotate\plane --max-cover 0.95 --max-union 0.95
```

Then stage, import and rebuild — **never while a trainer is running**, because
`build_dataset.py` rewrites `ai/data/processed/` in place and the trainer is
reading images out of it:

```powershell
python ai\scripts\stage_annotations.py --class <class>
python ai\scripts\import_yolo.py --dataset <CLASS>-HAND
python ai\scripts\build_dataset.py
```

## Running a real survey file

```powershell
python ai\scripts\xtf_to_frames.py --xtf <survey>.xtf --out E:\xtf-run --detect
```

Frames, a metadata sidecar per frame, geotagged detections and `report.csv`.
This is the problem statement end to end in one command.

## Choosing the review floor

```powershell
python ai\scripts\derive_review_floor.py
```

Recall against false alarms on **calibrated** confidence. Note the scale trap:
`evaluate_background.py` sweeps RAW detector scores, and the two are far apart
(the 0.20 floor is a raw score of 0.0225). Never read a false-alarm rate off
the raw table and quote it as the deployed one.
