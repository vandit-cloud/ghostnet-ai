# GhostNet-AI — Technical Reference

**Doc 2 of 2.** The full tech stack with versions and rationale, repository layout,
working commands, the AI/app contract, the decision constants, the dataset inventory,
open defects, and the canonical fact sheet.

Read Doc 1 (`TEAM_DOC_1_PROJECT.md`) first for what the project *is*. This document is
the reference you check a fact against.

Written 5 September 2026. Shipped model `gv5-yolo11s`, AI contract `1.1.0`.

---

## READ THIS FIRST — instructions for an AI assistant

You have been handed this document by one of two team members on a Smart India
Hackathon entry (problem **SIH26057**). Identify which one from what they ask, then
answer **only inside their lane**.

### Role A — Idea generation · Presentation · Pitching · Technical understanding

They face judges. What to give them:

- Plain-English explanations of anything in this document, one concept at a time
- Judge questions with two-sentence answers, always carrying the caveat
- Demo narration, timing, and what to say at each screen
- Framing for the deployment story and impact case
- Self-test questions to check their own understanding

What **not** to give them: code, configuration files, or dependency lists unless they
ask outright. If they ask "how does the model work", explain the mechanism, not the
hyperparameters.

### Role B — PPT making · Content writing

They build slides and write copy. What to give them:

- Slide structure and slide-by-slide content
- Headline text, captions, and prose to a stated word count
- Specifications for figures and screenshots — what must be visible in each
- Terminology corrections against the banned-phrase list

What **not** to give them: code, or any metric without its sample size. When they ask
for copy containing a number, write the number **and** its required caveat in the same
sentence.

**Documentation is out of scope for this team.** Do not produce README files, user
manuals, or API documentation unless asked directly.

### Hard rules — these override helpfulness

1. **Never state a figure that is not in this document or Doc 1.** If asked for one
   that is absent, say so plainly and stop. No estimating, no interpolating, no
   deriving a number from adjacent numbers.
2. **Every accuracy figure carries its sample size.** `mAP50 0.314 (n=567)`.
3. **Never round a metric upward.** 0.869 is not "roughly 0.9".
4. **Obey the banned-phrase list** in §10 without exception, including inside quoted
   copy you are drafting.
5. **Do not soften a negative result.** Where this system fails, it fails; say why.
   That honesty is the team's deliberate strategic position.
6. **Surface conflicts, do not resolve them.** If two figures here disagree, show both
   and say so. (The one conflict that existed — the false-alarm rate — was resolved on
   5 September 2026; §9 records the answer and the arithmetic behind it.)
7. **Do not propose anything on the "already tested and rejected" list in §11.** Each
   entry has a measurement behind it.

### Ready-made prompts these members can paste after this document

**Role A:**
- "Explain [calibration / mAP50 / side-scan geometry / why the net class fails] to me as if I have no ML background, then give me the two-sentence version I would say to a judge."
- "Give me ten questions a technical judge would ask about this project, each with the answer and the caveat it must carry."
- "Walk me through narrating the seven-screen demo, with what to say and roughly how long to spend on each."
- "Quiz me. Ask one question at a time about this project and tell me what I got wrong."

**Role B:**
- "Draft the six slides for the SIH idea-submission template using only facts from this document. Mark any slide I cannot complete without more input."
- "Write a 100-word abstract. Every number must carry its sample size."
- "Here is my slide text: [paste]. Check every number against this document and flag every banned phrase."
- "List the screenshots we need, and for each one say exactly what must be visible in the frame."

---

## 1 · The AI stack, pinned

From `ai/requirements.txt` — the exact set verified working on Member 1's machine.

| Package | Version | Note |
|---|---|---|
| `torch` | **2.13.0+cu126** | cu126 is deliberate — cu128 caps out at torch 2.11 |
| `torchvision` | 0.28.0+cu126 | |
| `ultralytics` | 8.4.134 | YOLO11 training and inference |
| `opencv-python-headless` | 5.0.0.93 | Headless: no libGL dependency, so one pin works on Windows, Linux and Docker |
| `numpy` | 2.5.1 | |
| `pandas` | 3.0.5 | |
| `scikit-learn` | 1.9.0 | |
| `scipy` | 1.18.1 | |
| `matplotlib` | 3.11.1 | |
| `pillow` | 12.3.0 | |
| `pyyaml` | 6.0.3 | |
| `pyproj` | **3.7.2** | Across-track → lat/lon on the **WGS84 ellipsoid**, not flat trigonometry |
| `pytest` | 9.1.1 | |
| `jsonschema` | 4.26.0 | Contract schema validation, dev/test only |

Python **3.12.10**. Extra index: `https://download.pytorch.org/whl/cu126`.

### What Member 2 installs instead

`ai/pyproject.toml` declares **deliberately loose, non-CUDA** pins: `torch>=2.6`,
`torchvision>=0.21`, `ultralytics>=8.3`, `opencv-python-headless>=4.10`,
`numpy>=1.26`, `pyproj>=3.6`.

The reasoning is in the file: Member 2's machine may have no GPU, and pinning a
CUDA-local build there would either fail to resolve or drag a 2.6 GB CUDA wheel onto a
laptop that cannot use it. The package runs on CPU by design.

### Hardware

**NVIDIA RTX 3050 Laptop, 4 GB VRAM, compute capability 8.6, bf16 supported.**

**The 4 GB VRAM is the binding constraint on this project — more than the timeline.**
It is why batch size is 4, why the model is YOLO11-**S** rather than anything larger,
why `cache=False`, and why AMP is mandatory rather than optional.

---

## 2 · The application stack, pinned

### Backend — `app/backend/requirements.txt`

| Package | Version | Role |
|---|---|---|
| `fastapi` | 0.115.6 | API framework |
| `uvicorn[standard]` | 0.34.0 | ASGI server |
| `sqlalchemy` | 2.0.36 | ORM |
| `alembic` | 1.14.0 | Migrations |
| `psycopg[binary]` | 3.2.3 | PostgreSQL driver |
| `geoalchemy2` | 0.16.0 | PostGIS geometry types in the ORM |
| `pydantic` | 2.10.4 | Request/response schemas |
| `pydantic-settings` | 2.7.1 | Config from environment |
| `python-jose[cryptography]` | 3.3.0 | JWT signing and verification |
| `bcrypt` | 4.2.1 | Password hashing |
| `python-multipart` | 0.0.20 | File upload parsing |
| `websockets` | 14.1 | Live progress channel |
| `pytest` / `pytest-asyncio` / `httpx` | 8.3.4 / 0.25.1 / 0.28.1 | Test stack |

### Frontend — `app/frontend/package.json`

| Package | Version | Role |
|---|---|---|
| `next` | 14.2.35 | Framework, App Router |
| `react` / `react-dom` | 18.3.1 | |
| `typescript` | 5.5.4 | |
| `tailwindcss` | 3.4.10 | Styling |
| `@tanstack/react-query` | 5.59.0 | Server state, caching, refetching |
| `zustand` | 4.5.5 | Client state |
| `leaflet` | 1.9.4 | 2D map engine |
| `react-leaflet` | 4.2.1 | React bindings for Leaflet |
| `react-leaflet-cluster` | 3.0.0 | Marker clustering |
| `three` | 0.185.1 | 3D engine |
| `@react-three/fiber` | 8.18.0 | React renderer for three.js |
| `@react-three/drei` | 9.122.0 | three.js helpers (camera, controls) |
| `react-hook-form` | 7.53.0 | Forms |
| `zod` | 3.23.8 | Schema validation |
| `@hookform/resolvers` | 3.9.0 | Bridges the two |
| `clsx` | 2.1.1 | Conditional class names |
| `vitest` | 2.0.5 | Test runner |
| `@testing-library/react` | 16.0.1 | Component tests |
| `jsdom` | 25.0.0 | DOM for tests |

### Database

**PostgreSQL with the PostGIS extension**, run from a portable install on Member 1's
machine, listening on `127.0.0.1:5432`.

---

## 3 · Repository layout

```
E:\New folder\
├── ai/                     Member 1 — the AI half
│   ├── ghostnet/           The shipping package (3,272 lines, 13 modules)
│   ├── scripts/            Data import, dataset build, training, calibration, evaluation
│   ├── data/
│   │   ├── raw/            Downloaded sources, untouched
│   │   ├── interim/        One folder per source, converted to YOLO format
│   │   ├── processed/      The merged, split, leakage-safe dataset + data.yaml
│   │   ├── annotate/       Our own hand-annotation work and its guide
│   │   └── provenance/     Inventory CSVs — what is actually on disk
│   ├── models/
│   │   ├── pretrained/     yolo11n.pt, yolo11s.pt
│   │   ├── trained/        ghostnet.pt — the promoted model
│   │   └── calibrator/      temperature.json
│   ├── experiments/        One folder per run: gv, gv2 … gv6, plus logs and metrics
│   ├── fixtures/           Test images
│   └── tests/              246 tests
├── app/
│   ├── backend/            FastAPI, SQLAlchemy, Alembic, 61 tests
│   └── frontend/           Next.js, React, Tailwind, Vitest
├── contracts/              *.schema.json — GENERATED, never hand-edited
├── demo/
│   ├── xtf/                Four per-class demo sonar files
│   ├── reports/            Generated CSV and JSON from a real survey
│   └── showcase/           Prepared demo material
├── docs/                   This document and everything else
└── scripts/                Demo seeding, demo XTF construction
```

### The 13 AI modules

| Module | Lines | Responsibility |
|---|---|---|
| `infer.py` | 546 | Detection entry point — `detect()`, model loading, tiling |
| `survey.py` | 388 | `detect_survey()` / `iter_survey_frames()` — whole-file processing |
| `xtf.py` | 399 | XTF container parsing, per-channel ping reading, waterfall assembly |
| `decision.py` | 374 | Calibration, review floor, uncertainty band, edge-sliver suppression |
| `report.py` | 308 | CSV and GeoJSON output, `write_geojson()` |
| `taxonomy.py` | 299 | The three class vocabularies and the mapping between them |
| `config.py` | 228 | Settings, device resolution, provenance stamping |
| `contract.py` | 170 | The frozen output dataclasses — dependency-free by design |
| `shadow.py` | 149 | Acoustic shadow context evaluation |
| `geo.py` | 126 | Slant-range correction, across-track → lat/lon via pyproj |
| `dropout.py` | 122 | Uncertainty support |
| `preprocess.py` | 119 | Image preparation |
| `__init__.py` | 44 | Public surface — `detect`, `warmup` |

### The three class vocabularies — do not conflate them

Maintained separately in `taxonomy.py` **on purpose**:

1. **Source aliases** — what each public dataset calls its classes
2. **Training classes** — `wreck, plane, debris, ghost_pot, ghost_net`; index order is
   a wire format
3. **The frozen contract vocabulary** Member 2 sees — `ghost_net | debris | natural |
   unknown`

The contract vocabulary is coarser than the training classes deliberately: it is what
the application and its users need, and it is frozen so the app never breaks when
training classes change.

---

## 4 · Running the system

### Order matters — database, backend, frontend

```bash
# 1 · Database
"/e/SIH-Debries-rudra/pgportable/pgsql/bin/pg_ctl.exe" \
  -D "E:/SIH-Debries-rudra/pgportable/data" \
  -l "E:/SIH-Debries-rudra/pgportable/pg.log" start

# 2 · Backend  (from app/backend)
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 3 · Frontend (from app/frontend)  — port 3000 MUST be free
npm run dev
```

Log in as `operator` / `operator123`. Health check:
`curl -s http://localhost:8000/api/v1/health` → `{"status":"ok"}`.

**Port 3000 must be free.** If Next.js finds it taken it silently moves to 3001, and
the backend's CORS origin list does not include 3001 — so every API call fails and the
UI shows "Unable to reach the server". That symptom is almost always this cause.

**Never demo from Docker.** `docker compose up` starts, but the backend image cannot
reach the `ai/` package, so detections are not real.

### AI commands

```powershell
$PY = ".\.venv\Scripts\python.exe"

# Run the model on your own images
& $PY -m ghostnet.infer <path>

# The full training pipeline: train → calibrate → false-alarm curve, unattended
powershell -ExecutionPolicy Bypass -File .\ai\scripts\train_all.ps1 -Name <run-name>

# Tests
& $PY -m pytest

# Check the generated contract schemas have not drifted
& $PY ai\scripts\export_schemas.py --check
```

Almost every script takes `--dry-run`. **Use it first** — it reports what would happen
and writes nothing.

`train_all.ps1` refuses to start if another trainer is alive. That is deliberate: two
trainers sharing 4 GB do not run half as fast, they collapse to roughly 60 s/iteration
and complete no epochs.

---

## 5 · The AI ↔ app contract

`CONTRACT_VERSION = "1.1.0"`. Plain Python dataclasses, **no pydantic, no FastAPI** —
intentionally dependency-free so the contract never drags a framework into either half.

### How the halves connect

```python
from ghostnet import detect, warmup
result = detect(image_path, survey_meta)
```

The backend does `pip install -e ai/` and calls this **in-process**. No HTTP service,
by agreement, because the demo runs on one machine.

*If an HTTP wrapper is ever added it must take a multipart upload or a URL, **never**
`image_path` — a path from one member's PC does not resolve on the other's.*

### The frozen vocabularies

```
CLASS_VALUES        = ("ghost_net", "debris", "natural", "unknown")
UNCERTAINTY_VALUES  = ("low", "medium", "high")
```

### `FrameResult` — the top-level response

| Field | Type | Meaning |
|---|---|---|
| `survey_id` | str | |
| `frame_id` | str | |
| `detections` | list[Detection] | |
| `provenance` | dict[str, str] | `model_id`, `model_version`, `dataset_version`, `preprocessing_version`, `calibration_version` |
| `warnings` | list[str] | Everything odd that happened, in plain language |
| `contract_version` | str | |
| `frame_position` | FramePosition \| None | **None** for a bare image with no metadata; never None for a frame cut out of an XTF |

### `Detection`

| Field | Type | Meaning |
|---|---|---|
| `detection_id` | str | |
| `cls` | one of `CLASS_VALUES` | Serialised as `class` |
| `raw_score` | float | Uncalibrated detector output, 0–1 |
| `calibrated_confidence` | float | Temperature-scaled. **This is the one to show a user** |
| `uncertainty` | `low` \| `medium` \| `high` | |
| `bbox` | list[int] | `[x, y, w, h]` in pixels, top-left origin |
| `mask` | list[list[int]] \| None | Not produced — segmentation was cut |
| `latitude`, `longitude` | float \| None | **None rather than guessed** when geometry is missing |
| `position_error_m` | float \| None | Radius of the error circle |
| `localization` | str | `"none"` when no position could be derived |
| `dimensions` | Dimensions | `width`, `length`, `status` |
| `review_status` | str | Defaults to `pending` |
| `model_version` | str | |
| `evidence_summary` | EvidenceSummary | `artificial_verification`, `shadow_context`, `notes` |

`FramePosition` carries `latitude`, `longitude`, `heading_deg`, `timestamp`.

### Versioning rules

- `contracts/*.schema.json` are **generated** from `contract.py` by
  `ai/scripts/export_schemas.py`. **Never hand-edit them.** `--check` fails if they are
  stale, and the test suite runs it.
- An additive, optional field is a **MINOR** bump — a consumer pinned to major 1 keeps
  working and ignores it. That is exactly what 1.1.0 was.
- Anything that removes or changes a field is a MAJOR bump and needs both members to
  agree.

---

## 6 · Decision policy — the constants that govern behaviour

From `ai/ghostnet/config.py`. **A user interface must key off the `uncertainty` band,
never a hardcoded number.**

| Setting | Value | Meaning |
|---|---|---|
| `imgsz` | 640 | Tile size |
| `batch` | 4 | Inference batch; VRAM-bound |
| `half` | True | FP16 |
| `raw_conf_threshold` | **0.10** | Raw detector gate — below this, nothing is emitted |
| `iou_threshold` | 0.50 | Non-max suppression |
| `max_detections` | 300 | Per frame |
| `review_floor_artificial` | **0.20** | Calibrated confidence below which an artificial detection is not surfaced |
| `review_floor_natural` | **0.45** | Higher on purpose: a low-confidence `natural` is neither actionable nor evidential |
| `uncertainty_low_edge` | **0.75** | Above this → `low` uncertainty |
| `uncertainty_medium_edge` | **0.45** | Above this → `medium`; below → `high` |
| `suppress_edge_slivers` | True | Shape-based suppression of tile-edge artefacts |
| `edge_touch_px` | 2 | How close to the edge counts as touching |
| `edge_sliver_max_thickness` | 0.08 | Fraction of frame |
| `edge_sliver_min_extent` | 0.40 | Fraction of frame |

### The single most important consequence

The **maximum calibrated confidence this model has ever produced is 0.728**, and
`uncertainty_low_edge` is 0.75.

**Therefore `low` uncertainty is unreachable — not rare, unreachable.** And any
threshold set at 0.80 or above selects *nothing at all*. The useful range is roughly
**0.30 to 0.73**. This fact broke three separate pieces of code before it was written
down.

### The review floor's derivation

From `ai/experiments/review_floor.json`, rule: *"highest threshold retaining ≥ 95% of
recall at 0.05"*, measured over 2,077 labelled objects and 2,930 empty frames.

| Calibrated threshold | Recall | Recall retained | Frames flagged |
|---|---|---|---|
| 0.05 | 0.6774 | 1.000 | 508 |
| **0.20 (chosen)** | **0.6702** | **0.9893** | **483** |
| 0.25 | 0.6057 | 0.8941 | 346 |
| 0.30 | 0.5339 | 0.7882 | 243 |
| 0.40 | 0.4083 | 0.6027 | 86 |
| 0.50 | 0.2884 | 0.4257 | 22 |
| 0.65 | 0.1151 | 0.1699 | 0 |
| 0.75 | 0.0000 | 0.0000 | 0 |

Read the last two rows: at 0.75 the system detects **nothing**. That is the ceiling
made visible.

---

## 7 · Dataset inventory

Five classes: `wreck, plane, debris, ghost_pot, ghost_net` — index order is a wire
format. Built by `ai/scripts/build_dataset.py`; `data.yaml` is generated, never
hand-edited.

**Test split, held byte-identical from gv5 onward: 4,346 frames.**

| Class | Test boxes |
|---|---|
| `wreck` | 836 |
| `debris` | 629 |
| `ghost_pot` | 567 |
| `ghost_net` | 36 |
| `plane` | 9 |

### Sources

| Source | Contribution | Note |
|---|---|---|
| AI4Shipwrecks | ~4,200 images | Pixel masks tiled to 640 px; **published test split preserved** so results stay comparable to the paper |
| GhostVision | 6,655 images | HuggingFace-style `metadata.jsonl` |
| SubPipe | ~2,049 images | Pipeline survey — the origin of `debris` 0.869 |
| China-Offshore-SSS-AI | ~2,072 images | **Contains 73 chips of real side-scan fishing net**, filed under a clutter class because that survey hunts pipelines and treats a net as noise |
| SCTD | 327 images | Pascal VOC XML boxes |
| Marine-PULSE | 88 images | Imported for **background only** |
| SonarDetect | 70 images | Already YOLO; classes remapped, contaminated frames screened out |
| GHOSTNET-HAND (ours) | 73 images | **The only class whose ground truth we produced.** Boxes hand-drawn, one per net panel, screened by `check_annotations.py`, convention documented |
| GHOSTNET-SYNTH (ours) | 1,364 images | Real net returns composited onto real seabed. Built for gv6; **did not work** |
| PLANE-HAND (ours) | 60 images | Pinned **train-only** |

### Two rules learned the hard way

**Split by group, never by file.** Exact duplicates dropped; near-duplicates and all
tiles of one waterfall kept together. Otherwise a tile in training and its neighbour in
test leak the answer.

**Every new source gets an explicit split policy before it is built into a dataset.**
A source with no policy falls through to the random pool, and adding a member to that
pool **re-draws every other member**. This silently moved `ghost_net`'s test boxes from
36 to 38 and `wreck`'s from 836 to 837 — *different* boxes, not merely more — destroying
the comparison the run existed for.

---

## 8 · Known defects

From `docs/KNOWN_ISSUES.md`, status 5 September 2026. Everything blocking a demo is
fixed and verified against the running stack.

### Fixed and verified

| | Was | Fix |
|---|---|---|
| A1 | A finished job vanished and the page said nothing ran | `GET /surveys/{id}/jobs/latest`, and the page reads only that |
| A2 | No completion state | Counts plus Detections / Map / Report links when a run ends |
| A3 | Progress bar jumped forward and backward | One source of truth; the stepper handles QUEUED and DONE |
| A4 | No way to delete a survey | `DELETE /surveys/{id}`, hard, behind a typed-name confirm |
| B1 | Dashboard named one survey and counted all of them | Every stat scoped to the survey the card names |
| B2 | Detections table did not say which survey a row belonged to | Survey column plus a Survey filter |
| D1 | Frontend called a hostname the backend only half-answered | Frontend addresses `127.0.0.1` |
| **F1** | **The starboard half of every frame was mirrored** | Sample order detected per channel; nadir now lands at the centre |
| F2 | An uploaded image could never produce a detection | The frame stored a storage key where the detector needed a path |
| F3 | The detector boxed the tile edge | Shape-based suppression in the decision layer — reported, not silent |

**Verified end to end after the fixes:** the bar moves 0 → 100 without ever moving
backward, all eight stepper nodes light at DONE, and the completed job is still on
screen after a reload. 61 backend tests pass, including ten new regressions.

**Correction, 5 September 2026.** `KNOWN_ISSUES.md` and `DEMO_RUNBOOK.md` §4 both still
say this run produces **5 detections**. That figure pre-dates the F3 tile-edge fix. The
current pipeline produces **2** on `NBP0505_line01B_demo.xtf`, confirmed three ways: a
standalone `detect_survey()` run, the app's own database rows from a post-fix run, and
the fact that the four disappeared boxes were all thin slivers at x ≈ 601–605 on a
640-wide frame — exactly what F3 suppresses. `DEMO_RUNBOOK.md` §5b already says 2. **The
two documents contradict each other and should be corrected to 2.**

### Still open

| | Issue |
|---|---|
| B3 | A "selected detection" report contains the whole survey — needs a `reports.detection_id` migration |
| B4 | "Filtered detections" reports are also unfiltered — the page never sends `filters` |
| B5 | A bounding box that excludes every marker still zooms to the whole survey |
| C1–C7 | API robustness — lenient rather than broken, except C1 |

**If a judge asks about defects, these are the answers.** Naming your own open issues
before someone finds them is a credibility gain, not a loss.

---

## 9 · The false-alarm figure — resolved

The most misquotable number in the project. Two files measure it on **different
scales**; the apparent disagreement was investigated on 5 September 2026 and settled.

| Source | Scale | Threshold | Flagged | Rate |
|---|---|---|---|---|
| `gv5-yolo11s/background_metrics.json` | **raw** detector score | 0.10 | 229 / 2,930 | **7.82% ← deployed** |
| `review_floor.json` | **calibrated** confidence | 0.20 | 483 / 2,930 | 16.48% (not the shipped gate) |

### Which one is deployed, and why

The shipped pipeline has two gates in series:

| Gate | Setting | Value |
|---|---|---|
| Detector | `config.raw_conf_threshold` | 0.10 **raw** |
| Review floor | `config.review_floor_artificial` | 0.20 **calibrated** |

Measured at the shipped temperature T = 2.722:

```
calibrate(0.02) = 0.1931       ← the 0.20 floor ≈ raw 0.02
calibrate(0.05) = 0.2532
calibrate(0.10) = 0.3085       ← everything through the raw gate already exceeds 0.20
```

Since 0.02 < 0.10, **the raw gate binds first and the review floor rejects nothing that
survived it.** The floor is *inert* in the shipped configuration. Therefore the deployed
false-alarm rate is the row measured at raw 0.10: **7.82%**.

`review_floor.json`'s 16.48% was produced with the detector deliberately opened to raw
0.02 (`derive_review_floor.py --raw-conf`, default 0.02) so the calibrated sweep would
not be truncated at the bottom. Correct method for deriving a floor; wrong number to
quote as deployed.

### Two source files were corrected

- The `note` in every `background_metrics.json` described its tiles as *"real side-scan
  seabed verified to contain no object"* — the banned phrasing, and factually wrong.
  Now reads "tiles CARRYING NO ANNOTATION", with the upper-bound caveat.
- The `scale_warning` claimed that quoting a row from that file "overstates the model".
  That is backwards: it assumed the calibrated floor was binding. Now states the
  arithmetic above and names the deployed row.
- `ai/scripts/evaluate_background.py` was fixed at the source so re-running it does not
  regenerate the old text. **Measurements were not touched** — only descriptive fields.

### A consequence worth knowing

**The review floor of 0.20 currently does nothing.** If anyone wants it to actually
gate, it has to rise above `calibrate(raw_conf_threshold)` = 0.3085 — or the raw gate
has to come down. Right now the two settings are not independent controls; only the raw
one is live.

The full raw-score curve, for reference:

| Raw threshold | Frames flagged | Rate | Total boxes |
|---|---|---|---|
| 0.10 | 229 | 7.82% | 385 |
| 0.20 | 119 | 4.06% | 229 |
| 0.25 | 86 | 2.94% | 152 |
| 0.30 | 63 | 2.15% | 111 |
| 0.40 | 37 | 1.26% | 60 |
| 0.50 | 22 | 0.75% | 35 |
| 0.60 | 13 | 0.44% | 21 |
| 0.70 | 9 | 0.31% | 15 |

**What to say.** *"On 2,930 held-out tiles carrying no annotation, 7.8% show a reviewer
at least one box, at the deployed operating point. Roughly half those tiles come from
survey lines the source dataset left entirely unannotated, so it is an upper bound."*

The rate and "deployed operating point" are both correct. The part that still needs
care is **"carrying no annotation"** — never "verified-empty seabed" — and the
upper-bound caveat.

---

## 10 · Language rules

| Never write | Write instead |
|---|---|
| "ghost net" for a crab pot | "derelict crab pot", or "ghost gear" |
| "verified-empty seabed" | "tiles carrying no annotation" |
| `debris` 0.869 with no caveat | "…on 615 held-out boxes, 615 of 629 from one pipeline survey" |
| any `plane` figure | omit the class |
| a threshold with no scale | "raw score 0.10" or "calibrated confidence 0.20" |
| "7.8% of verified-empty seabed" | "7.8% of tiles carrying no annotation — an upper bound" (the rate is correct at the deployed gate; §9) |
| "99% accurate", "real-time AI", "fully automated" | the per-class table |
| "a limitation we plan to overcome" | "we tested it, it failed, here is why" |
| "accuracy" for confidence | "calibrated confidence" |
| "exact location", "pinpoint" | "error radius" / "error circle" |
| "test images" | "held-out frames" |

Two style rules for all copy: **active voice with a named actor** ("the system reports
no position" beats "no position is reported"), and **no adjective doing a number's
job** — "highly accurate" means nothing beside "0.869 on 615 held-out boxes".

---

## 11 · Already tested and rejected — do not propose these

Each has a measurement behind it. Proposing one again costs the team a week and ends
where it started.

| Idea | Why it is closed |
|---|---|
| More synthetic ghost nets | gv6 tested it with 2,031 boxes of perfect ground truth. Recall stayed at **exactly 0.000** |
| Speckle filtering at inference | Built and measured at **−13%**. Ships in the OFF position deliberately |
| Detection by elimination ("if it isn't natural, it's debris") | Destroys the false-alarm number. The honest version is the `unknown` class we already have |
| A bigger model | Data is the limit, not capacity |
| TensorRT / export | 4 GB VRAM, and inference is already ~1,000× faster than collection |
| Segmentation masks | Cut for time; boxes suffice |
| RBAC, audit infrastructure, disaster recovery, 26 tables | Weeks of work, no marks |
| An HTTP microservice for the AI | Agreed against: one machine, so it adds failure modes for nothing |

**The one remaining candidate with evidence behind it:** a model **trained** on
despeckled data — as distinct from despeckling at inference, which was tested and
rejected. It survives because of the **transform-symmetry rule**: a transform must be
applied to training *and* inference, or to neither. This is the correct answer to
"what would you do next?".

---

## 12 · Environment traps

Worth knowing before anyone touches the machine.

| Trap | What happens |
|---|---|
| **Silent CPU fallback** | `config.resolve_device()` catches a torch failure and returns `"cpu"`. A half-installed torch therefore looks fine while running on CPU. **If the device ever reports `cpu` on the RTX 3050, suspect a broken torch install, not a missing GPU** |
| **The venv must use `--system-site-packages`** | An isolated venv here once died mid-download and left a torch that could not load `c10_cuda.dll` |
| **Tests during a live training run** | Run them with `GHOSTNET_DEVICE=cpu`. The 4 GB is shared, and a test that loads the model onto CUDA can OOM the trainer |
| **Calibrator / weights mismatch** | `temperature.json` was once left refitted against gv6 while the shipped weights were gv5 — the model would have been scored with another model's temperature. **After any run, check that the calibrator and `ghostnet.pt` name the same `model_version`** |
| **Port 3000 taken** | Next.js moves to 3001, CORS blocks every call, the UI says "Unable to reach the server" |
| **Killing a trainer on Windows** | `.venv/Scripts/python.exe` is a shim that spawns a separate child. POSIX `kill` reaps the shim and orphans the child, which keeps its CUDA context. Use `taskkill /T` |
| **Liveness by log age is wrong** | A healthy slow epoch can exceed a stale-log timeout, so a watchdog launches a *second* trainer beside the live one. Key liveness on a new `results.csv` row |
| **High GPU utilisation is not progress** | Three trainers sharing 4 GB showed 100% utilisation and completed zero epochs. Verify a new `results.csv` row |

---

## 13 · Canonical fact sheet

**Every number a slide, script or pitch may contain. If it is not here or in Doc 1, it
does not get said.**

### Per-class results — `gv5-yolo11s`, 4,346 held-out frames

| Class | n | Precision | Recall | mAP50 | mAP50-95 |
|---|---|---|---|---|---|
| `debris` | 629 | 0.798 | 0.855 | 0.869 | 0.516 |
| `ghost_pot` | 567 | 0.377 | 0.295 | 0.314 | 0.126 |
| `wreck` | 836 | 0.423 | 0.315 | 0.279 | 0.142 |
| `plane` | 9 | — | — | — | *do not quote* |
| `ghost_net` | 36 | 1.000 | 0.000 | 0.009 | 0.003 |
| all | 1,426 | 0.580 | 0.361 | 0.352 | *misleading — see Doc 1 §4* |

### Everything else

| Figure | Value |
|---|---|
| Held-out test frames | 4,346 |
| Calibration temperature | 2.722031, fitted on validation |
| ECE | 0.2178 → 0.0891 |
| Calibration fitted over | 1,604 predictions, 611 correct |
| Median calibrated confidence | 0.422 |
| 90th percentile | 0.664 |
| **Maximum calibrated confidence** | **0.728** |
| Useful confidence range | ~0.30 – 0.73 |
| Review floor, artificial | 0.20 calibrated |
| Review floor, natural | 0.45 calibrated |
| Raw detector gate | 0.10 |
| False alarms, raw 0.10 | 229 / 2,930 tiles = **7.82%** (see §9) |
| Tiles measured on | 2,930, carrying no annotation |
| Throughput | 17.3 frames/second |
| Demo survey (`NBP0505_line01B_demo.xtf`) | 40 frames, 6,039 pings, **2 detections**, 40 track points |
| — verified 5 Sep 2026 | Standalone `detect_survey()` reproduces the app's stored rows exactly, box for box |
| — the older "5 detections" figure | **Stale.** Pre-dates the F3 tile-edge fix; 4 of those 5 were edge slivers, now correctly suppressed |
| Position error, demo survey | 4.3 – 4.5 m |
| gv6 `ghost_net` recall | 0.000 (unchanged from gv5) |
| gv6 synthetic training boxes | 2,031, from 1,364 frames |
| API route handlers | 29, across 11 routers |
| Frontend pages | 16 |
| Database models | 8 |
| AI package | 3,272 lines, 13 modules |
| Tests | 246 AI, 61 backend, plus frontend Vitest |
| Training runs completed | 6 (`gv` … `gv6`); gv5 shipped |
| VRAM | 4 GB — the binding constraint |
| Contract version | 1.1.0 |

### The four demo sonar files — `demo/xtf/`

| File | Contents | Detections |
|---|---|---|
| `wrecks_demo_fixture.xtf` | 4 shipwrecks + 2 clean seabed | 6 |
| `aircraft_demo_fixture.xtf` | 4 aircraft + 2 clean seabed | 7 |
| `debris_demo_fixture.xtf` | 4 pipeline frames + 2 clean seabed | 4 |
| `ghost_gear_demo_fixture.xtf` | 1 ghost net + 3 crab pots + 2 clean seabed | 13 |

The headline survey — `demo/NBP0505_line01B_demo.xtf` — is a real, unedited slice of a
2005 side-scan line. Honest, and undramatic: real seabed is mostly speckle.

---

## 14 · Where to look for more

| Document | Contains |
|---|---|
| `PROJECT_PRIMER.md` | The from-zero explainer. Part 8 is the honest results, Part 13 the say/don't-say list |
| `docs/EXPERIMENT_GV6.md` | The failed synthetic-net experiment in full |
| `docs/DEMO_RUNBOOK.md` | The demo route and the troubleshooting table |
| `docs/KNOWN_ISSUES.md` | Every defect found in the full walkthrough |
| `docs/COMMANDS.md` | Every command, what it is for, when to run it |
| `docs/DATA.md` | What each dataset is and why it was chosen |
| `docs/HANDOFF.md` | The contract versioning rules |
| `docs/OPERATOR_MANUAL.md` | The application, click by click |
| `docs/MODEL_CAPABILITY_EVIDENCE.md` | Evidence behind the capability claims |
