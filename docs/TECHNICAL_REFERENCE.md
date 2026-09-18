# GhostNet-AI — Technical Reference

Facts, versions, schemas and hard-won knowledge, in lookup order.
Companion to `PROJECT_WALKTHROUGH.md`, which tells the same system as a story.

Everything here was read from the running system on **19 September 2026**.

---

## 1. Tech stack

### Frontend

| Package | Version | Role |
|---|---|---|
| `next` | 14.2.35 | App Router, production build |
| `react` / `react-dom` | 18.3.1 | |
| `typescript` | 5.5.4 | strict |
| `tailwindcss` | 3.4.10 | the Atlantic theme lives in `tailwind.config.ts` |
| `@tanstack/react-query` | 5.59.0 | server cache, polling, invalidation |
| `zustand` | 4.5.5 | auth session only |
| `react-hook-form` + `zod` | 7.53.0 / 3.23.8 | form validation |
| `leaflet` / `react-leaflet` | 1.9.4 / 4.2.1 | GIS map |
| `react-leaflet-cluster` | 3.0.0 | marker clustering |
| `three` | 0.185.1 | ocean shader, hero scene |
| `@react-three/fiber` / `drei` | 8.18.0 / 9.122.0 | |
| `vitest` + Testing Library | 2.0.5 | |

### Backend

| Package | Version | Role |
|---|---|---|
| `fastapi` | 0.115.6 | |
| `uvicorn[standard]` | 0.34.0 | **one worker only** — see §8 |
| `sqlalchemy` | 2.0.36 | 2.0 typed ORM |
| `alembic` | 1.14.0 | migrations |
| `psycopg[binary]` | 3.2.3 | Postgres driver |
| `geoalchemy2` | 0.16.0 | one PostGIS column |
| `pydantic` / `pydantic-settings` | 2.10.4 / 2.7.1 | |
| `python-jose[cryptography]` | 3.3.0 | JWT |
| `bcrypt` | 4.2.1 | password hashing |
| `slowapi` | 0.1.9 | rate limiting, **in-memory** |
| `websockets` | 14.1 | realtime job events |
| `pytest` / `httpx` | 8.3.4 / 0.28.1 | 74 tests |

### AI

| | |
|---|---|
| Framework | Ultralytics YOLO11s |
| Torch | `2.13.0+cu126` (training) / `2.13.0+cpu` (serving) |
| Also | opencv-python-headless, numpy, pyproj |
| Training GPU | RTX 3050 Laptop, **4 GB** — batch size 4 is a VRAM ceiling, not a choice |

### Infrastructure

PostgreSQL **16.15** + PostGIS **3.6.2**. Python 3.12 / 3.11. Node 20+.
Docker Compose exists (`app/docker-compose.yml`) but the demo runs natively.

---

## 2. Database

14 tables (plus PostGIS's own). `ondelete="CASCADE"` throughout, so deleting a
survey removes files → frames → detections → reviews in one statement.

| Table | Cols | Notes |
|---|---|---|
| `users` | 7 | bcrypt hash, role |
| `surveys` | 8 | `status`, `created_by_user_id` |
| `survey_files` | 11 | SHA-256 `checksum`, two independent status fields |
| `sonar_frames` | 22 | the geometry carrier — see below |
| `detections` | 30 | the widest table; includes a PostGIS `location` |
| `detection_reviews` | 6 | append-only verdicts |
| `processing_jobs` | 15 | status + stage + counters |
| `reports` | 10 | CSV / JSON exports |
| `audit_logs` | 10 | append-only |
| `refresh_tokens`, `password_reset_tokens` | 6 / 7 | |

### `sonar_frames` — the four that matter

```
nadir_col            column directly beneath the towfish
range_resolution_m   metres per PIXEL   (not swath width)
altitude_m           height ABOVE THE SEABED   (not water depth)
heading              tow direction, degrees
```

**All-or-nothing.** With all four plus a lat/lon fix you get a position and
metric dimensions; with any one missing you get neither, and the reason lands in
`warnings`. Also present but optional: `along_track_res_m`, `layback_m`,
`nadir_row`.

Two traps the column names invite:

- `depth` is **water depth**, not altitude. Substituting it corrupts every
  position, worst near nadir.
- `range` is **swath width in metres**, not metres-per-pixel. They differ by
  roughly the image width.

### `detections` — shape

Identity `detection_ref` (`D-XXXXXXXX`) · scores `raw_score`,
`calibrated_confidence`, `uncertainty` · box `bbox_x/y/w/h`, `mask_reference` ·
position `latitude`, `longitude`, `location` (PostGIS POINT, SRID 4326, GIST
index), `position_error_m`, `localization_method` · size `width`, `length`,
`area`, `dimension_status` · triage `priority`, `review_status` · provenance
`model_version`, `evidence_summary` (JSON).

**PostGIS is used for exactly one nullable column.** That is the entire spatial
dependency — but `CREATE EXTENSION postgis` and a GIST index are in migration
`0001`, so SQLite is not a drop-in substitute.

### Enums

| Enum | Values |
|---|---|
| `JobStatus` | QUEUED, VALIDATING, PROCESSING, PARTIAL, COMPLETED, FAILED, CANCELLED |
| `JobStage` | QUEUED, VALIDATING, DECODING, PREPROCESSING, DETECTION, VERIFICATION, CALIBRATION, GEOTAGGING, SAVING, DONE |
| `Priority` | low, medium, high, critical |
| `ReviewStatus` | pending, unknown, accepted_artificial, rejected_natural |
| `Uncertainty` | low, medium, high |
| `FileValidationStatus` | PENDING, VALID, INVALID |

### Migrations

```
0001_initial_schema              PostGIS extension + GIST index
0002_sonar_frame_geometry        the four geometry columns
0003_detection_ref_unique_per_frame
0004_rbac_audit_rate_limit
```

---

## 3. API

Base `/api/v1`. Bearer JWT except `/auth/login` and `/health/*`.

| Method | Path |
|---|---|
| POST | `/auth/login` · `/auth/refresh` · `/auth/logout` · `/auth/change-password` · `/auth/reset-password` |
| GET | `/auth/me` |
| POST GET | `/surveys` |
| GET PATCH DELETE | `/surveys/{id}` |
| POST GET | `/surveys/{id}/files` |
| **DELETE** | `/surveys/{id}/files/{file_id}` |
| POST | `/surveys/{id}/process` |
| GET | `/surveys/{id}/jobs` · `/jobs/active` · `/jobs/latest` |
| GET POST | `/jobs/{id}` · `/jobs/{id}/cancel` |
| GET | `/detections` · `/detections/{id}` |
| POST GET | `/detections/{id}/review` · `/detections/{id}/reviews` |
| GET | `/frames/{id}/image` |
| GET | `/maps/surveys/{id}/detections` |
| POST GET | `/reports` · `/reports/{id}` · `/reports/{id}/download` |
| GET | `/dashboard/summary` · `/analytics/summary` |
| GET | `/health` · `/health/liveness` · `/health/readiness` |
| WS | `/ws/surveys/{survey_id}?token=…` |

**WebSocket events:** `job.updated` (status + stage on every transition) and
`detection.created` (as each one is saved, while the job still runs).

**Errors** are uniform: `{"error": {"code", "message", "request_id"}}`.
Notable codes — `FILE_NOT_FOUND` (404, also returned for a file in *another*
survey, so existence never leaks), `SURVEY_PROCESSING` (409, delete refused
while a job runs).

**Rate limits:** 60/min general, 5/min on login. Five failed logins for one
username in 15 minutes locks further attempts, derived from `audit_logs`.

---

## 4. Frontend

21 routes. `○` prerendered, `ƒ` server-rendered on demand.

```
/                              landing
/auth/login
/app/dashboard                 KPIs, latest alert, survey panel
/app/surveys                   list
/app/surveys/new               create + upload
/app/surveys/[id]              detail, files, per-file delete
/app/surveys/[id]/process      live job progress (WS)
/app/detections                queue
/app/detections/[id]           full detail + sonar evidence
/app/review · /app/review/[id] review workflow
/app/sonar · /app/sonar/[id]   frame viewer
/app/map                       Leaflet + clustering
/app/reports · /app/reports/[id]
/app/analytics · /app/settings
/lab/hero · /lab/map · /lab/seabed    design labs
```

**Feature folders:** `analytics, auth, dashboard, detections, landing, map, maplab, processing, reports, seabedlab, sonar, surveys, upload`.

**Caching.** `staleTime` 10s, `refetchOnWindowFocus` false, retry 1.
Polling: dashboard 15s, analytics 30s; processing and reports poll adaptively
while a job is live and stop when it ends.

**Cache keys to know:** `["survey-files", id]`, `["survey", id]`,
`["detections"]`, `["survey-map", id]`, `["dashboard-summary"]`. The map is a
**separate** key with its own endpoint — a mutation that changes detections must
invalidate it too, or the map keeps asserting gear at a position with no
evidence behind it.

**`SonarViewer`** is the single bbox render site (detections, review, sonar,
map all use it). Zoom/pan, green box, and the client-side despeckle toggle.

---

## 5. The AI package

`ai/ghostnet/` — 13 modules:

| Module | Does |
|---|---|
| `infer` | detection entry point; `detect_batch` is ~10× `detect` in a loop |
| `decision` | temperature calibration, floors, uncertainty bands, class normalisation |
| `taxonomy` | training classes ↔ contract classes, source aliases, exclusions |
| `shadow` | acoustic-shadow verification of raised objects |
| `geo` | slant-range correction, pixel → coordinate |
| `xtf` | reads XTF containers, derives nav + geometry from ping headers |
| `survey` | tiles a container into frames |
| `preprocess` | speckle filters — **defined but never called at inference** (§8) |
| `contract` | payload shape + version check |
| `config` | `Settings`, `resolve_device()` (falls back to CPU) |
| `report`, `dropout` | export helpers, MC-dropout scaffolding |

**Contract:** `contracts/ai-input.schema.json`, `ai-output.schema.json`,
`ai-error.schema.json`. Current **1.2.0 (MAJOR 1)**; a major bump makes the
backend refuse the payload rather than misread it.

### Decision policy numbers

```
temperature T            2.72
raw_conf_threshold       0.10   (lowered so weak net boxes exist at all)
review_floor artificial  0.20   ← inert since calibration: min calibrated ≈ 0.309
review_floor natural     0.45
REVIEW_ONLY_CLASSES      {ghost_net}
```

Floors are **asymmetric on purpose**: a missed ghost net keeps fishing for
years, so artificial classes clear a low bar; a low-confidence `natural` is
neither actionable nor evidential, so it clears a higher one. `natural` is
**reported, not discarded** — it is the evidence that artificial-vs-natural
separation works, which is the headline metric.

### Class mapping

| Training class | Reported as | Note |
|---|---|---|
| `wreck`, `plane`, `debris` | `debris` | original preserved in `evidence_summary.notes` |
| `ghost_pot` | `debris` | a crab pot is **gear, not a net** — see below |
| `ghost_net` | `ghost_net` | real, hand-annotated |
| `natural` | `natural` | |

Mapping `ghost_pot → ghost_net` would be the single most tempting lie available:
it would make the headline metric look like it measures the problem statement's
exact words. It would also be inventing ground truth. So it reports as `debris`
and `"detector class: ghost_pot"` travels in the notes.

---

## 6. Model runs

Promoted: **`gv5-yolo11s`**, 3 Sep 2026, 60 epochs, 8 sources, 18,310 images,
`dataset_version 8src-12472/1492/4346-ee2f4b940bc1`.

| Run | Classes | Val best mAP50 | @epoch | Note |
|---|---|---|---|---|
| `baseline-yolo11s` | 2 srcs | 0.5527 | 94 | **not comparable** — 2 sources, easier data |
| `gv-yolo11s` | 4 | 0.2288 | 28 | |
| `gv2` | 4 | 0.2282 | 33 | flat |
| `gv3` | 4 | 0.1434 | 9 | regression |
| `gv4` | 4 | 0.3024 | 40 | no `ghost_net` class |
| **`gv5`** | **5** | **0.3097** | **52** | **promoted** |
| `gv6` | 5 | 0.2936 | 50 | +synthetic nets +PLANE-HAND |
| `gv7d` | 5 | 0.2449 | 34 | |
| `gv7d2b-netseg` | 1 | 0.6662 | 549 | **different task** — net segmentation |

### Test-split results (4,346 held-out images)

| Class | gv5 | gv6 |
|---|---|---|
| debris | 0.8695 | 0.8789 |
| ghost_pot | 0.3143 | 0.3451 |
| plane | 0.2923 | 0.3784 |
| wreck | **0.2787** | 0.2380 |
| ghost_net | 0.0093 | 0.0229 |
| **overall** | 0.3528 | **0.3727** |

**gv6 outscores gv5 on the test split and was never promoted.** It was judged on
its own goal — rescuing `ghost_net` — and 0.0229 is still unusable, which is what
"gv6 disproved synthetic volume" means. Worth revisiting properly.

Two numbers that will mislead a reader: `baseline` 0.5527 is 2 sources on easier
data, and `gv7d2b` 0.6662 is single-class **segmentation** on 73 images. Neither
is comparable to a 5-class detector.

### Experiments that failed (and why that is useful)

**Model soup, gv5 + gv6 → mAP50 0.0010.** Heads matched (499 tensors, 0
mismatches) so it was mechanically possible, but the two were trained
independently on different data — different loss basins, and neural nets have
permutation symmetry, so averaging lands nowhere useful. Soups need ingredients
that share a trajectory.

**Test-time augmentation → 0.3528 → 0.3527, 1.93× slower.** No gain. `ghost_net`
moved 0.0093 → 0.0596 and `plane` fell 0.2923 → 0.2463 — two tiny classes
wobbling in opposite directions while the total sits still is what noise looks
like.

**Despeckling before inference → mAP 0.3066 → 0.1644.** Domain mismatch: gv5 was
trained on speckled chips, so a cleaned frame is out of distribution.

---

## 7. Dataset sources

Trained on (one line each):

| Source | Images | One-liner |
|---|---|---|
| **AI4Shipwrecks** | 6,976 | Full waterfalls, 28 wrecks, Lake Huron — 125 empty masks are the only real in-domain hard negatives. Freshwater, so out of domain for Indian coastal seabed. |
| **GhostVision v1.0.0** | 6,655 | Derelict crab pots, Delaware bays — highest PS relevance of anything found. **CC-BY-SA 4.0**, share-alike. |
| **China-Offshore-SSS-AI** | 2,072 | Chinese offshore survey; supplies gullies, riprap, scour and sand waves as hard negatives. Also the origin of the 73 net chips. |
| **SubPipe** | 2,049 | Submarine pipeline inspection — this *is* the `debris` class, and it is one survey. CC BY 4.0. |
| **SCTD 1.0** | 327 | Sonar Common Target Detection: 271 ship / 57 aircraft, VOC boxes, clean. Small crops, not waterfalls. |
| **Marine PULSE** | 88 | Imported for background only — but recorded across five different sonars, which is the cheap instrument-diversity test. |
| **GHOSTNET-HAND** | 73 | The team's own hand-drawn net boxes. The only class whose ground truth was produced here. |
| **sonar_detect** (Roboflow) | 70 | Scraped mixed set; screened for burned-in UI chrome. `fish` class excluded. CC BY 4.0. |

Evaluated and **not** used:

- **KLSG / SeabedObjects** — 447 images, classification-only, no boxes.
- **KLSG-II** — advertises 578 seafloor negatives; the repo is one 45 KB JPEG.
- **Zenodo seafloor sediments** — 434,164 tiles, but one 52.3 GB split archive with no way to take a slice.
- **MDT / UATD** — the only real marine-debris sonar sets, but **forward-looking sonar**, not side-scan. Different geometry and shadow behaviour.
- **`Side Scan Sonar.yolov8`** (on disk, unused) — 549 images, Plane + Ship. **All 60 PLANE-HAND images are inside it**, split across train/valid/test. Importing it naively puts training images into the test split. See §8.

**Licences:** only sonar_detect and SubPipe carry explicit permissive terms
(CC BY 4.0). GhostVision is **share-alike**. AI4Shipwrecks, SCTD, Marine PULSE
and China-Offshore have no formal licence file — cite every source.

---

## 8. Facts, traps and hard-won knowledge

**One uvicorn worker, always.** `processing_service` keeps running jobs in a
process-local dict and slowapi's limiter is in-memory. A second worker silently
breaks job cancellation and halves the rate limits.

**`preprocess()` is never called.** The only occurrence outside its definition is
inside its own docstring. `Settings.preprocessing` is read only by
`provenance()`. Harmless today because the default is `"none"` — but set it to
`"median3-v1"` and inference is byte-identical while provenance claims a filter
that never ran.

**Priority is keyed off `uncertainty`, not confidence.** The old thresholds
(0.85/0.80/0.65/0.50) were tuned against the mock adapter's 0.45–0.98 range. Real
calibrated scores: **median 0.42, 90th 0.66, max 0.728**. `CRITICAL` and `HIGH`
were unreachable and the queue silently stopped triaging.

**`storage.path_for()`, never `storage_reference`.** The reference is a
storage-relative key. Passing it through made `cv2.imread` return `None`,
`detect()` logged "image not found" as a *warning*, and the job completed
successfully with zero detections — an uploaded PNG could never produce a
detection, and it looked like a model finding nothing rather than a path that
did not exist.

**Deleting a file cascades.** `sonar_frames` cascades off `survey_files`, and
`detections` off **both** `frame_id` and `source_file_id`. Refused with 409 while
a job runs, because the cascade would pull rows from under a task still writing.

**Audit rows are written after the act, not before.** An entry written first
records deletions that were then refused — a trail that lies in exactly the case
it exists to explain.

**Image uploads can never be geolocated.** No ping headers, no geometry. The
system says so rather than estimating: an invented position looks identical to a
measured one on a map.

**`PLANE-HAND ⊂ Side Scan Sonar.yolov8`.** Verified by perceptual hash — all 60
overlap. PLANE-HAND is pinned train-only; that Roboflow set splits the same
images across train/valid/test. Dedupe before importing or the plane score rises
for the wrong reason.

**The frontend must run production, not `next dev`.** Dev wedged repeatedly under
concurrent `.next` writes (`Cannot find module './vendor-chunks/next.js'`,
`PageNotFoundError` on files that exist) and served pages in **seconds** rather
than milliseconds. Never run `next dev` against `app/frontend` while the
production server is up — they destroy each other's build output.

**The water shader is expensive.** A full-screen raymarch at 1.6× DPR saturates
integrated graphics, and a saturated GPU stalls the compositor — which presents
as *dropped clicks and hanging navigation*, not as slow water. Its loop now stops
when off-screen, on a hidden tab, or under reduced motion.

**`ghostnet.pt` is tracked in this repo** (19 MB, committed in the initial
import), so a clone gets real weights. In `E:\New folder` it is gitignored — clone
that without copying the weights and `try_build()` falls back to `MockAIAdapter`,
stamping every payload `mock-ghostnet-dev-v0`.

**Tests need their own database.** `TEST_DATABASE_URL` defaults to
`ghostnet_test`; without it all 74 tests error on connection.

---

## 9. Quick reference

```bash
# stack
psql -d ghostnet -c "CREATE EXTENSION postgis"
cd app/backend && .venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m uvicorn app.main:app --port 8000 --workers 1
cd app/frontend && npm ci && npm run build && npm run start

# tests
cd app/backend && .venv/Scripts/python -m pytest tests/ -q     # 74 passed
cd app/frontend && npx tsc --noEmit && npm run build

# credentials (dev)
operator / operator123        ports 3000 / 8000 / 5432
```

| Want | Look in |
|---|---|
| Why a class maps where it does | `ai/ghostnet/taxonomy.py` |
| Why a detection was suppressed | `ai/ghostnet/decision.py` |
| Why a position is missing | `app/services/ghostnet_adapter.py` (`GEOMETRY_FIELDS`) |
| What the model can and cannot do | `docs/MODEL_CAPABILITY_EVIDENCE.md` |
| Where data came from | `docs/DATA.md`, `ai/data/provenance/` |
| The story version of all this | `docs/PROJECT_WALKTHROUGH.md` |
