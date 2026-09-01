# Testing the model on your own images

A step-by-step walkthrough. Everything here runs offline on this machine — no
login, no internet, no Claude credits.

Current model: **`gv2-yolo11s`**, trained 2026-09-01.
Quick reference for all other commands: `docs/COMMANDS.md`.
How to interpret what comes back: **`docs/READING_RESULTS.md`**.

---

## Before you start (once per terminal)

Open **PowerShell** — a normal window, not the one running a training job.

```powershell
cd "E:\New folder"
$PY = ".\.venv\Scripts\python.exe"
```

That is the whole setup. `$PY` matters: plain `python` may be a different
interpreter without torch, and the failure is silent — it falls back to CPU
instead of erroring.

---

## Step 1 — Put your images in one folder

Make a folder anywhere and drop the images in. For example:

```powershell
mkdir "E:\sonar-test"
```

**Formats accepted:** `.png` `.jpg` `.jpeg` `.bmp` `.tif` `.tiff`

Subfolders are searched too, so a folder of folders is fine.

### What the model can actually read

It was trained on **side-scan sonar** tiles, 640 x 640 pixels, greyscale. It
knows acoustic shadow and seabed texture. It knows nothing about photographs,
forward-looking sonar, or bathymetry maps, and will either report nothing or
report nonsense on them.

**Image size is the trap.** If you feed a full waterfall — say 2000 x 6000 — it
gets squeezed down to 640 before the model sees it, and a crab pot that was 40
pixels across becomes 4 pixels and vanishes. Objects a few pixels wide cannot be
detected at this resolution.

So: **crop large waterfalls into roughly 640 x 640 pieces first.** A 640-px crop
around the area you care about will work far better than the whole sheet.
Anything from about 320 to 1280 px square is fine; past that, crop.

---

## Step 2 — Run it

```powershell
& $PY ai\scripts\try_model.py --images "E:\sonar-test"
```

A single image works too:

```powershell
& $PY ai\scripts\try_model.py --images "E:\sonar-test\my_tile.png"
```

First run takes ~15 seconds to load the model, then well under a second per
image.

### What you will see

```
  weights  E:\New folder\ai\experiments\gv2-yolo11s\weights\best.pt
  images   3 from E:\sonar-test
  floor    0.2 on CALIBRATED confidence
  output   ai\experiments\tryout

  my_tile.png                    reported=1  below_floor=0  top=0.490
  empty_patch.png                reported=0  below_floor=0  top=0.000

  1 of 2 images had at least one detection at or above 0.2
```

- **reported** — detections a human reviewer would be shown
- **below_floor** — found, but too uncertain to report
- **top** — highest calibrated confidence on that image

---

## Step 3 — Look at the results

```powershell
explorer ai\experiments\tryout
```

Two files per input image:

| File | What it is |
|---|---|
| `<name>_annotated.jpg` | Your image with boxes drawn on it |
| `<name>.json` | The full payload, exactly what the application receives |

### Reading the boxes

- **Amber box** — reported. This is what a reviewer sees.
- **Blue box** — the model found something but held it below the review floor.

The blue boxes are the useful part. They show you what the threshold is hiding,
which is the whole argument for where to set it.

Each label reads like `debris 0.49` — the class, then the **calibrated**
confidence. That is a real probability estimate, not the raw detector score.
Never quote the raw score to anyone; it is in the JSON for debugging only.

---

## Step 4 — Try a different threshold

The default floor is 0.20. To see more (including weaker, less reliable finds):

```powershell
& $PY ai\scripts\try_model.py --images "E:\sonar-test" --conf 0.10
```

To see only high-confidence detections:

```powershell
& $PY ai\scripts\try_model.py --images "E:\sonar-test" --conf 0.50
```

Measured on 2,620 verified-empty seabed tiles, so you know what you are buying:

| floor | empty tiles wrongly flagged |
|---|---|
| 0.10 | 11.5% |
| **0.20** | **2.9%** |
| 0.30 | 1.3% |
| 0.50 | 0.3% |

Lower catches more real objects and more false alarms. There is no free setting.

---

## Check it works before trusting it

Run these four known frames. They are already on disk in
`ai\data\processed\test\images\`, and their answers were verified on 2026-09-01.

```powershell
& $PY ai\scripts\try_model.py --images ai\data\processed\test\images\AI4SHIPWRECKS__Artificial_Reef_06__x0_y960.png
```

| frame | should give |
|---|---|
| `AI4SHIPWRECKS__Artificial_Reef_06__x0_y960.png` | 1 detection, top ≈ 0.49 |
| `AI4SHIPWRECKS__Artificial_Reef_06__x480_y960.png` | 2 detections, top ≈ 0.52 |
| `AI4SHIPWRECKS__Barge_No_1_03__x1088_y1440.png` | 2 detections, top ≈ 0.23 |
| `AI4SHIPWRECKS__Artificial_Reef_01__x0_y0.png` | **0 detections** (empty seabed) |

Test both directions. A broken model that detects everything passes the first
three; one that detects nothing passes the last. Only all four together tell you
it works.

---

## The visual test bench

A page with 23 pre-run examples and a live threshold slider:

```powershell
start "E:\New folder\ai\experiments\gv2-yolo11s\testbench.html"
```

Opens in your browser straight from disk. No login. It shows finds, misses,
correctly-ignored seabed and false alarms side by side, and the slider moves
every box at once so you can watch the trade-off.

To rebuild it after a new training run:

```powershell
& $PY ai\scripts\make_demo.py --weights ai\experiments\<run>\weights\best.pt --conf 0.10 --hits 8 --misses 5 --clean 5 --false-alarms 5
& $PY ai\scripts\build_testbench.py --run <run>
```

---

## Troubleshooting

**"no images under ..."** — wrong path, or the files are not a format in the
list above. Check with `ls "E:\sonar-test"`.

**Every image reports 0 detections** — normally correct on empty seabed. Run the
four known frames above; if those pass, the model is fine and your images
genuinely have nothing it recognises. If those also give 0, the weights did not
load — check the `weights` line printed at the top.

**"no model loaded"** — pass the path explicitly:

```powershell
& $PY ai\scripts\try_model.py --images "E:\sonar-test" --weights ai\experiments\gv2-yolo11s\weights\best.pt
```

**Every payload says `localization: "none"` and warns about geometry** — this is
correct, not a bug. Your images carry no navigation metadata, so no latitude or
longitude can be derived. The pipeline reports the detection **without** a
position rather than inventing one.

**Detections on obvious junk, or none on an obvious wreck** — check the image
size first. See the cropping note in Step 1; it explains most surprises.

**It is slow / the GPU is busy** — a training run may be using the card. Check:

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*train.py*" }
```

---

## What this actually tests

`try_model.py` calls `ghostnet.detect()` — the same function the application
imports. So you are testing the real delivered path: calibrated confidence, the
review policy, the contract payload and its warnings.

Loading the `.pt` file directly with ultralytics would skip all of that and test
a code path nothing runs. Do not benchmark that way.

---

## Comparing two models

```powershell
& $PY ai\scripts\try_model.py --images "E:\sonar-test" --weights ai\experiments\gv-yolo11s\weights\best.pt  --out ai\experiments\cmp-old
& $PY ai\scripts\try_model.py --images "E:\sonar-test" --weights ai\experiments\gv2-yolo11s\weights\best.pt --out ai\experiments\cmp-new
```

Then open both folders side by side. Expect `gv2` to draw far fewer boxes on
empty seabed — that was the point of retraining it — and to miss a few things
`gv` caught.
