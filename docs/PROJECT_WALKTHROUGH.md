# GhostNet-AI — Project Walkthrough

**SIH26057.** Detecting ghost nets and marine debris in side-scan sonar imagery.

This document follows one real detection from a file landing on disk to a
reviewed finding on a map. Every number in it was read from the running system,
not estimated — the worked example is survey `DEMO - NBP0505 Line 01B`,
detection `D-F439794C`, produced by `gv5-yolo11s` on 18 September 2026.

---

## 1. The problem

Abandoned, lost or discarded fishing gear — **ghost nets** — keeps fishing after
nobody owns it. It drifts, snags on wrecks and reefs, and drowns fish, turtles
and cetaceans for years. To recover it you first have to find it, and the ocean
is opaque: the practical survey instrument is **side-scan sonar (SSS)**, which
drags a towfish behind a vessel and paints the seabed with sound.

The problem statement asks for a system that **separates natural seafloor
topology from artificial anomalies** and puts the artificial ones on a map an
operator can act on.

That wording matters, and the project takes it literally. See §8 for why the
headline metric is artificial-vs-natural and not a ghost-net F1 score.

---

## 2. The system in one picture

```
   Operator                Browser                    Server                    Model
   ────────                ───────                    ──────                    ─────
   uploads .xtf  ─────►  Next.js 14  ──HTTP/WS──►  FastAPI          ┌──►  ghostnet (Python pkg)
   reviews boxes         React Query                SQLAlchemy      │       YOLO11s, 5 classes
   exports report        Leaflet map                PostGIS  ◄──────┘       temperature calibration
                         three.js                   asyncio jobs            shadow verification
                                                                            slant-range geotagging
```

Two halves, one frozen interface between them:

| Half | Owns | Lives in |
|---|---|---|
| **AI** | preprocessing, detection, calibration, shadow reasoning, geotagging | `ai/ghostnet/` |
| **App** | auth, database, jobs, GIS, review UI, reports | `app/backend/`, `app/frontend/` |
| **Contract** | the JSON both sides validate against | `contracts/` |

The contract is versioned and checked at startup. The adapter logs
`ghostnet contract 1.2.0 (MAJOR 1, as expected)` — a major bump means the app
half refuses the payload rather than silently misreading it.

---

## 3. The entities

Everything below is a real table. Cascades are declared at the database level,
so deleting a parent removes its children in one statement.

| Entity | What it is | Key relationships |
|---|---|---|
| **User** | operator or admin | owns surveys; every action lands in `audit_logs` |
| **Survey** | one survey job — a line, a site, a day's work | has many `SurveyFile` |
| **SurveyFile** | one uploaded artefact (`.xtf`, `.png`, …) | has many `SonarFrame` |
| **SonarFrame** | one tile of the waterfall, with its own nav fix | has many `Detection` |
| **Detection** | one box the model drew, with class and position | has many `DetectionReview` |
| **DetectionReview** | a human's verdict on a detection | belongs to a `User` |
| **ProcessingJob** | one run of the pipeline over a survey | reports stage + progress |
| **Report** | an export — CSV or JSON | snapshots detections at a point in time |
| **AuditLog** | who did what, when, from where | append-only |

The chain that matters:

```
Survey ──► SurveyFile ──► SonarFrame ──► Detection ──► DetectionReview
                              │
                              └── carries the four geometry values
                                  that turn pixels into coordinates
```

---

## 4. The story: one detection, end to end

### 4.1 An operator signs in

`operator` logs in. The backend returns a short-lived access token and a
refresh token; the frontend keeps them in a Zustand store and attaches the
access token to every call. A failed login is counted — five failures for the
same username inside fifteen minutes locks further attempts, derived from
`audit_logs` rather than a second tracking table.

### 4.2 A survey is created, a file is uploaded

The operator creates **`DEMO - NBP0505 Line 01B`** and drags in
`NBP0505_line01B_demo.xtf` — **40,000,000 bytes** of raw side-scan.

`file_service.validate_upload()` checks extension and size, stores the bytes
under `uploads/<survey_id>/<uuid>_<name>`, and records a SHA-256 checksum. The
file is marked:

```
validation_status : VALID
metadata_status   : VALID
```

That second field is the interesting one. It starts `PENDING` — the uploader
supplied no metadata — and becomes `VALID` only because the **file carried its
own**, in the ping headers. That is the case `PENDING` was standing in for.

### 4.3 The container becomes frames

An `.xtf` is not one image. It is thousands of pings, so
`xtf_ingest.ingest_xtf()` tiles it into **40 `SonarFrame` rows**, each written
to disk as a PNG and each carrying the navigation read from its own headers.
The first frame:

```
frame_id            fee53b6a…_NBP0505_line01B_demo__p000000__x00000
latitude            -46.351818
longitude           -73.731983
heading             348.5°
nadir_col           1024
range_resolution_m  0.09747      (metres per pixel)
altitude_m          7.7976       (towfish height ABOVE the seabed)
quality_status      ok
```

**Those four bottom values are the whole ballgame.** Without `nadir_col`,
`range_resolution_m`, `altitude_m` and `heading`, a detection can be drawn but
never placed. They exist in `.xtf` ping headers and nowhere else — which is why
a `.png` upload produces boxes with no coordinates, and why the UI explains
that rather than showing eight rows of "Unavailable". See §7.

Note what is *not* here: `depth` is null, and the system does not substitute it
for `altitude_m`. Water depth and towfish height above the seabed are different
quantities; swapping one for the other does not degrade a position, it corrupts
it — worst near nadir, where an operator trusts it most.

### 4.4 The job runs

Pressing **Process** creates a `ProcessingJob` and an `asyncio` task. The job
walks a fixed stage machine, broadcasting `job.updated` over a WebSocket at
every transition so the progress page moves without polling:

```
QUEUED → VALIDATING → DECODING → PREPROCESSING → DETECTION
       → VERIFICATION → CALIBRATION → GEOTAGGING → SAVING → DONE
```

Frames go to the model in **batches**, not one at a time — `detect_batch` is
roughly ten times faster than `detect` in a loop.

### 4.5 The model draws a box

On one frame, YOLO11s emits a box at `x=284, y=63, w=141, h=47` with a **raw
score of 0.1966**, class `wreck`.

Four things then happen to it, in order, and each is a deliberate decision.

**Calibration.** The raw score is temperature-scaled (`T = 2.72`) into a
**calibrated confidence of 0.3735**. Raw detector scores are overconfident and
shift every retrain; calibrated ones keep a fixed meaning, so every threshold
downstream is applied to the calibrated number.

**The decision policy.** `apply_decision_policy()` decides whether this survives
at all. The floors are deliberately **asymmetric**: artificial classes clear a
low bar (0.20) because a missed ghost net keeps fishing for years, while a
low-confidence `natural` clears a higher one (0.45) because it is neither
actionable nor evidential. `ghost_net` gets a third, lower gate *and* is flagged
review-only — a lenient floor is only defensible because the payload says the
output is a candidate.

**Taxonomy collapse.** The detector said `wreck`. The contract has no `wreck`
value, so it reports as **`debris`** — and the original finding is preserved in
the payload:

```json
"notes": "detector class: wreck"
```

This is the project's sharpest self-imposed rule. Mapping `ghost_pot` → `ghost_net`
would be the most tempting lie available — it would make the headline metric
look like it measures the problem statement's exact words. A crab pot is fishing
*gear*; it is not a *net*. So it reports as `debris` and the real class travels
in `notes`, where a reviewer sees the truth and the contract claims nothing it
cannot support.

**Shadow verification.** A raised object on the seabed casts an acoustic shadow
on its far side. `shadow.py` measures both flanks:

```
"shadow_context": "confirmed: the port flank is 44% darker than the near flank,
                   consistent with an object standing proud of the seabed"
```

That is independent physical corroboration, not a second opinion from the same
network.

### 4.6 Pixels become a position

With all four geometry values present plus a nav fix, the box centre is
converted through slant-range correction into a real coordinate:

```
latitude             -46.346286
longitude            -73.726674
position_error_m     3.76
localization_method  frame-level
dimensions           13.8 m × 113.84 m  (status: estimated)
```

`localization_method` is not decoration. `frame-level` says the position came
from the frame's own nav fix — distinct from `operator-supplied` or `none`, so
the map can never conflate a measured position with an entered one.

### 4.7 Triage

The detection is saved with `uncertainty: high` and **`priority: low`**.

Priority is keyed off **uncertainty, not confidence** — and that is a repaired
bug worth knowing. The thresholds were once 0.85/0.80/0.65/0.50, chosen against
the mock adapter, which produces confidences from 0.45 to 0.98. The real
detector does not live on that scale: calibrated over 259 real detections the
distribution was **median 0.42, 90th percentile 0.66, maximum 0.728**. A
calibrated 0.85 needs a raw score of 0.9912. `CRITICAL` and `HIGH` were
unreachable, everything fell through to `LOW`, and the review queue silently
stopped triaging while still looking like it worked.

`uncertainty` is computed from band edges fitted to the model's own
distribution, so it survives a retrain. A hardcoded 0.85 does not.

A `detection.created` event goes out over the WebSocket, and the row appears in
the operator's queue while the job is still running.

### 4.8 A human decides

The operator opens `D-F439794C`. They get the raw frame with a **green box**
drawn on it, the AI evidence, the geospatial panel, and a **Despeckle** toggle.

The despeckle filter is worth a note. It runs **in the browser, after
detection** — it cannot reach the model or the payload, which is exactly what
makes it safe. Filtering *before* inference was measured and rejected: gv5
scored **mAP 0.3066 raw versus 0.1644 despeckled**, because the model was
trained on speckled data and a cleaned frame is out of distribution. The view
filter is 3×3 median plus a mild sharpen; 5×5 was tried and cost more detail
(36% retained) than the speckle it removed (42%).

The reviewer records one of:

| Verdict | Meaning |
|---|---|
| `accepted_artificial` | yes, this is man-made — actionable |
| `rejected_natural` | no, that is seabed — a false positive |
| `unknown` | cannot tell from this frame |

The verdict is a `DetectionReview` row, not an edit. **The model's original
output is never overwritten**, so the disagreement between machine and human
stays on the record and can be counted later.

### 4.9 Export

A `Report` snapshots the chosen detections to CSV or JSON with coordinates,
classes, confidences and model version. Because every payload carries
`model_version` (`gv5-yolo11s`) and the dataset fingerprint, a finding can be
traced back to the exact run and the exact data that produced it, months later.

---

## 5. A second detection, and why it is honest

`D-23E8D839`, from the same survey, shows the system declining to overclaim:

```json
"bbox": { "x": 0.0, "y": 151.0, "w": 129.0, "h": 62.0 },
"shadow_context": "not_evaluated: the shadow would fall outside this frame"
```

The box starts at `x = 0` — it is cut off by the tile edge. The shadow that
would corroborate it lies in the neighbouring tile, so the check reports
`not_evaluated` with the reason, rather than returning a verdict it cannot
support or silently omitting the field.

That is the pattern throughout: **absent is stated, never inferred.**

---

## 6. What the model is

`gv5-yolo11s`, promoted 3 September 2026. YOLO11s at 640 px, 60 epochs,
**eight merged sources, 18,310 images**.

| Source | Images | Contributes |
|---|---|---|
| AI4Shipwrecks | 6,976 | shipwrecks + most empty seabed |
| GhostVision | 6,655 | derelict crab pots |
| China-Offshore-SSS-AI | 2,072 | hard negatives: gullies, riprap, scour, sand waves |
| SubPipe | 2,049 | submarine pipelines |
| SCTD | 327 | ships, aircraft |
| Marine PULSE | 88 | seabed across five different sonars |
| GHOSTNET-HAND | 73 | fishing nets, hand-annotated by the team |
| sonar_detect | 70 | mixed objects |

Five training classes — `wreck`, `plane`, `debris`, `ghost_pot`, `ghost_net` —
collapsing to the contract's `debris` / `ghost_net` / `natural`.

Test performance on a 4,346-image held-out split:

| Class | mAP50 |
|---|---|
| debris | 0.8695 |
| ghost_pot | 0.3143 |
| plane | 0.2923 |
| wreck | 0.2787 |
| **ghost_net** | **0.0093** |
| overall | 0.3528 |

---

## 7. The limits, stated plainly

A reader who only remembers one section should remember this one.

**`ghost_net` does not work.** 0.0093 mAP50, recall effectively zero. The cause
is documented and external: **no public side-scan dataset contains ghost nets** —
confirmed independently by an October 2025 survey of sonar datasets, which names
it as an open gap in the field. The 73 hand-annotated chips are the only real
side-scan nets the project could find anywhere. 215 training boxes is not enough
for the hardest target in the set, and synthetic augmentation was tried (gv6) and
did not rescue it.

**`debris` reads 0.87 and should not be over-read.** That number is carried by
SubPipe — pipelines from **one survey**. It measures the model on one seabed with
one instrument. It is not evidence of general debris detection.

**`plane` is measured on ~9 test boxes.** Whatever it reads, it is noise.

**Image uploads cannot be geolocated.** A `.png` has no ping headers, so no
altitude, heading, nadir column or range resolution. The system reports no
position rather than estimating one, because an invented position looks
identical to a measured one on a map — and an operator dispatches a boat on it.

**The 73 net chips have an open provenance question.** They are not published in
this repository; what is published is the project's own annotation work over
them. See `DATA.md`.

---

## 8. Why the headline metric is what it is

The obvious metric — ghost-net F1 — **cannot honestly be measured**, because no
real labelled ghost-net side-scan data exists to measure it against. Quoting a
number there would mean inventing the ground truth it was scored on.

So the metric is **binary artificial-vs-natural separation**, which real data
does support, and which matches the problem statement's own wording: *"separates
natural seafloor topology from artificial anomalies."*

This is why `natural` detections are **reported, not discarded**. The model
asserting "that is a rock" is the evidence that the separation works. Throwing
it away would delete the proof of the thing being claimed.

---

## 9. Where things live

| Path | Contents |
|---|---|
| `ai/ghostnet/` | `infer`, `decision`, `taxonomy`, `shadow`, `geo`, `xtf`, `preprocess` |
| `ai/models/trained/ghostnet.pt` | the promoted weights (tracked in this repo) |
| `ai/models/trained/ghostnet.json` | which run and which dataset produced them |
| `app/backend/app/api/v1/` | `auth`, `surveys`, `files`, `frames`, `processing`, `detections`, `reports`, `maps`, `ws` |
| `app/backend/app/services/` | `ghostnet_adapter` (the seam), `processing_service` (the job), `xtf_ingest` |
| `app/frontend/src/components/SonarViewer.tsx` | the frame viewer, box overlay, despeckle |
| `contracts/` | JSON Schemas both halves validate against |
| `docs/` | build plans, data provenance, capability evidence |

**The seam worth knowing:** `app/services/ghostnet_adapter.py` implements the
same protocol as `MockAIAdapter`. If the `ghostnet` package or the trained
weights are missing, the system falls back to mock detections stamped
`mock-ghostnet-dev-v0` — clearly labelled, never to be shown as real results.
`get_ai_adapter()` chooses between them at startup and logs which one it picked.

---

## 10. Running it

```bash
# Database (PostgreSQL 16 + PostGIS)
createdb ghostnet && psql -d ghostnet -c "CREATE EXTENSION postgis"

# Backend
cd app/backend
.venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m uvicorn app.main:app --port 8000 --workers 1

# Frontend
cd app/frontend && npm ci && npm run build && npm run start
```

Then `http://localhost:3000`, sign in as `operator`.

**One worker, deliberately.** `processing_service` keeps running jobs in process
memory and the rate limiter is in-memory too; a second worker silently breaks
job cancellation and halves the limits.
