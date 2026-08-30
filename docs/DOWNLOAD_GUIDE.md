# Download guide

Every link and file size below was checked against the source on **2026-08-30**.
Sizes are real, not guessed.

**Already on disk — nothing to do:**

| Dataset | Images | What it gives |
|---|---|---|
| SCTD | 357 | 271 wreck + 57 plane boxes, clean |
| AI4Shipwrecks | 286 | full waterfalls, 125 empty-seabed frames → 4,200 tiles |
| SONARDETECT | 581 | 173 debris boxes (screened) |
| KLSG | 447 | classification only, no boxes |

**Cancelled:** the Zenodo seafloor-sediments record. It is one 52.3 GB split
archive, all parts required, no way to take a slice — and AI4Shipwrecks already
solved the hard-negative problem.

---

# What to download now, in priority order

## 1. GhostVision — derelict crab pots ⏱️ 5 min 🔴 do this first

**899 MB.** The highest problem-statement relevance of anything found: real
side-scan sonar of **derelict fishing gear** on the seabed, with detection
annotations and a permissive licence.

**Link:** <https://zenodo.org/records/20056679>

Download **`GhostVision_DatasetAndModels.zip`** (898.8 MB). No account needed.

Extract to:

```
E:\New folder\ai\data\raw\research\GHOSTVISION\
```

Licence CC-BY-SA 4.0 — **share-alike**, so cite it and note the licence in your
report. It is the only share-alike dataset in the stack.

> **The boundary that matters.** A derelict crab pot is fishing *gear*. It is
> **not a net**. It gets its own class and reports as `debris`. Relabelling it
> `ghost_net` would be inventing ground truth, which is the one thing both build
> plans forbid outright. Detecting real derelict gear and saying so plainly is a
> stronger claim than a fabricated net label.

## 2. SubPipe — the volume ⏱️ 25 min 🟡

**Download `SubPipeMini2.zip` — 4.9 GB. Not `SubPipeMini.zip`.**

**Link:** <https://zenodo.org/records/12666132>

| File | Size | Contents |
|---|---|---|
| `SubPipe.zip` | 28.0 GB → ~80 GB unzipped | everything; far more than needed |
| `SubPipeMini.zip` | 6.1 GB | **camera imagery**, not sonar — wrong data |
| **`SubPipeMini2.zip`** | **4.9 GB → ~16 GB** | **side-scan sonar + YOLO detection boxes** ✅ |

The sources document says "start with a smaller archive", which is right, but the
smaller archive to start with is **Mini2**. Mini is optical camera data for
segmentation and is no use to a sonar detector.

Extract to:

```
E:\New folder\ai\data\raw\research\SUBPIPE\
```

Licence CC BY 4.0. Pipelines are artificial seabed objects, so they map to
`debris` — never to `ghost_net`.

## 3. Marine-PULSE — cheap and useful ⏱️ 2 min 🟢

**Only 64 MB.** Worth taking purely for what it costs.

**Link:** <https://zenodo.org/records/7922705>

Download **`Marine_PULSE.zip`** (64.0 MB). 627 images:

- 323 pipeline or cable
- 134 underwater residual mound
- **88 seabed surface** ← more natural-seabed variety, from different instruments
- 82 engineering platform

Extract to:

```
E:\New folder\ai\data\raw\research\MARINE-PULSE\
```

Recorded across **five different sonars** (EdgeTech 4200FS, Benthos SIS-1624,
EdgeTech 4200MP, Klein 2000, Klein 3000). That instrument diversity is worth
more than the image count — a model that has only seen one sonar's texture is
brittle, and this is the cheapest way to test that.

Expect **classification labels, not boxes.** Useful as class variety and hard
negatives, not as a detection source. `inventory.py` will confirm which on disk.

---

# Optional, only if the first three land easily

| Dataset | Link | Why |
|---|---|---|
| AquaScan-1K | <https://zenodo.org/records/17628597> | general SSS robustness |
| Healy submarine volcano | <https://zenodo.org/records/19000370> | natural geological seabed |

Do not download these before the three above are inventoried and training.

---

# After every download

```bash
.venv/Scripts/python ai/scripts/inventory.py --verbose
```

Check the block for the dataset you just added:

- **`classes`** — the folder or label breakdown actually present
- **`annotation_type`** — boxes, masks, or classification-only
- **a `MISMATCH` warning** is the tool working, not failing. It means the claim
  and the disk disagree, and it is the line that caught leftover test data
  masquerading as a real dataset.

**Send me that output** and I will write the importer for whatever format it
turns out to be.

---

# Folder names matter

The inventory tool matches the folder name against the dataset registry. Use
these exactly, or it reports `provenance unrecorded` and cannot check the data
against what was promised:

```
ai\data\raw\research\GHOSTVISION\
ai\data\raw\research\SUBPIPE\
ai\data\raw\research\MARINE-PULSE\
```

---

# Do NOT download these

**MDT** and **UATD** contain real underwater rubbish — tyres, cans, chains — and
look perfect for a marine-debris problem. They are **forward-looking sonar**, not
side-scan, and MDT was recorded in a water tank. Acoustic shadow, the main clue
that something stands proud of the seabed, does not form the same way. Training
on them and reporting the score as side-scan performance would not survive a
knowledgeable question.

The **`fish` class inside SONARDETECT** is already excluded for the same reason:
those frames are fish-finder screenshots, and several have the annotator's red
circle burned into the pixels.

---

# Troubleshooting

| Problem | Fix |
|---|---|
| `inventory.py` says `ai/data/raw/ is empty` | Images nested too deep, or the folder name is wrong |
| `not in dataset_candidates.csv` | Folder name mismatch — rename to the exact name above |
| `MISMATCH … probably NOT the real dataset` | Download incomplete, or test data left in the folder |
| Zenodo download stalls | Zenodo is slow at peak; resume works, or use the DOI mirror |
| A `.zip` will not open | Use 7-Zip. Split archives need every part present |
