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
| `& $PY ai\scripts\make_demo.py --weights ai\experiments\<run>\weights\best.pt` | Real model output on real test tiles -> `demo_data.json`. Picks hits, misses, clean seabed and false alarms, so the demo is honest. |
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
