# GhostNet-AI — demo runbook

Everything needed to run the demo yourself, in order, with the exact commands.
Written 2026-09-04 after a full end-to-end verification on real sonar.

**Read the two red flags first:**

1. **Start the frontend before anything else takes port 3000.** The shipped
   `cors_origins` default is `["http://localhost:3000"]`. If Next.js finds 3000
   busy it silently moves to 3001, every API call then fails CORS preflight, and
   the UI shows only "Unable to reach the server. Please try again." — which
   looks exactly like the backend being down. See Troubleshooting.
2. **Do not demo from Docker.** `docker compose up` works, but the backend image
   cannot reach `ai/`, so it runs on `MockAIAdapter` and the detections are
   invented. See `app/README.md`.

---

## 0. What you already have

| thing | where |
|---|---|
| Demo sonar file, 40 MB | `demo/NBP0505_line01B_demo.xtf` |
| Pre-generated CSV report | `demo/reports/NBP0505_line01B_full_survey.csv` |
| Pre-generated JSON report | `demo/reports/NBP0505_line01B_full_survey.json` |
| Login | `operator` / `operator123` |

The database already holds one processed survey — **NBP0505 Line 01B — Golfo de
Penas**, 40 frames, 5 detections — so the app has something to show the moment
it starts. Section 4 covers uploading live instead.

The demo file is a 40 MB slice of a real 2005 side-scan survey off Patagonia
(Nathaniel B. Palmer cruise NBP0505, line 01B). To regenerate it:

```bash
head -c 40000000 "ai/data/raw/research/MGDS_Download/MGDS_Download/NBP0505/NBP050501B.XTF/NBP050501B.XTF" > demo/NBP0505_line01B_demo.xtf
```

**Why a slice and not the whole file:** the original is 209 MB and the app's own
`max_upload_size_mb` is 200, so the full file is rejected. Truncating an XTF is
safe — the reader stops at the last complete ping.

---

## 1. Start the database

```bash
"/e/SIH-Debries-rudra/pgportable/pgsql/bin/pg_ctl.exe" -D "E:/SIH-Debries-rudra/pgportable/data" -l "E:/SIH-Debries-rudra/pgportable/pg.log" start
```

Check it:

```bash
netstat -ano | grep "127.0.0.1:5432" | grep -i listen
```

**If you skip this**, every backend test and request fails with
`sqlalchemy.exc.OperationalError`, which reads like a code fault and is not.

## 2. Start the backend

```bash
cd "E:/New folder/app/backend"
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Watch the startup lines. You want to see:

```
ghostnet.ai: ghostnet contract 1.1.0 (MAJOR 1, as expected)
ghostnet.ai: AI adapter: ghostnet (weights loaded=True)
```

**If instead you see** `AI adapter: MockAIAdapter -- these are NOT real
detections`, stop. The model did not load and everything downstream is fake.
Fix it before demoing (Troubleshooting).

Health check:

```bash
curl -s http://localhost:8000/api/v1/health
```

## 3. Start the frontend

**Port 3000 must be free.** Check first:

```bash
netstat -ano | grep ":3000" | grep -i listen
```

If anything is listed, kill it (`taskkill //PID <pid> //T //F`) — a leftover
dev server from an earlier session is the usual culprit.

```bash
cd "E:/New folder/app/frontend"
npm run dev
```

Confirm it says `Local: http://localhost:3000` and **not** 3001. Then open
<http://localhost:3000> and log in as `operator` / `operator123`.

---

## 4. The demo, in the order that tells the best story

Seven pages, numbered in the sidebar. This route follows the data.

### 1. Dashboard — "one survey, processed, 5 candidates"

Opens on mission summary and live pipeline state. Point at the survey card and
the class distribution.

### 2. Surveys → upload live (optional but strong)

`Surveys` → `New Survey`, give it any name (non-ASCII is fine, it round-trips),
then upload `demo/NBP0505_line01B_demo.xtf`.

Two things worth saying out loud as it uploads:

- The app reads the **raw sonar container**, not pre-cut images. It splits the
  file into 40 frames and reads each frame's latitude, longitude, heading and
  timestamp straight from the ping headers.
- That is what draws the vessel track — including the stretches where nothing
  was found, which is most of any real survey.

Then `Process`. Takes about 14 seconds for 40 frames on the RTX 3050.

> **The re-process guard.** Pressing Process a second time on a finished survey
> returns **409 ALREADY_PROCESSED**, on purpose — a second run would append a
> duplicate copy of every detection. To redo it deliberately, send
> `force_restart: true` (section 6). If a judge asks why it refused, that is the
> answer: it protects the data, and re-running discards review decisions.

### 3. Processing / realtime

While it runs, progress is live over a WebSocket — a `job.updated` at each
stage, a `frame.processed` per frame, and a `detection.created` per hit. 49
events for this file.

### 4. GIS Map — the centrepiece

`GIS Map`. You get **5 detections · 40 track points**.

- The blue line is the **vessel track**, from the ping headers.
- The markers are detections, each drawn with its **error circle**, not a pin.
  `position_error_m` is real — derived from GPS scatter, heading error and
  altitude uncertainty. **Say that.** A pin would claim a precision the system
  deliberately refuses to claim.
- Note the detections sit slightly **off** the track line. That is the
  across-track offset: the sonar looks sideways, so an object is not where the
  boat was. If they sat on the line, the geometry would be wrong.
- `2D` / `3D View` toggles. **In 3D, click `Fit Survey`** — the default camera
  does not frame the survey on entry.
- `Replay` walks the survey in time.

### 5. Detections → Sonar Viewer — the honest bit

`Detections` → click any row → the **Sonar Investigation** view: the real
640×640 sonar frame with the detection's bounding box drawn on it, beside class,
confidence, uncertainty, priority, coordinates and dimensions.

**This is the strongest moment in the demo, and it is strongest if you are
honest about it.** Four of the five detections are tall thin boxes hugging the
dark right-hand edge of the frame. That edge is the far end of the sonar swath,
where the acoustic return is weakest — the model is firing on low-signal noise.
You can see it. Their dimensions read `3.3 m × 935–1504 m`, and a 1.5 km piece
of debris is obviously not an object.

So say: *"the dimensions are a free plausibility filter — an operator rejects
that in one click, and the system already flagged all of them `uncertainty:
high`, `priority: low`, at 34–36% confidence, just above the review floor."*
Only `D-6D702B97` (6.45 m × 43.6 m) is a plausible target.

### 6. Review Queue — human judgement, recorded

`Review Queue` shows everything pending. Accept one as artificial, reject
another as natural. The detection's `review_status` updates and the decision is
kept as an audit trail with reviewer and note — the model proposes, a person
decides, and the record shows who decided.

### 7. Reports — the deliverable

`Reports` → generate → download. CSV opens in Excel; JSON is the machine
format. Both name `model_version: gv5-yolo11s`, so any stored result traces back
to the exact run that produced it. Copies are already in `demo/reports/`.

---

## 5. Talking points that survive scrutiny

All true, all verifiable on screen.

| if asked | say |
|---|---|
| "Does it find ghost nets?" | Not yet, and we can prove we tried. `ghost_net` scores mAP50 0.009 on 36 held-out real boxes. We spent a full GPU run (gv6) testing whether synthetic nets fix it — recall stayed at exactly 0.000. The cause is acoustic: a net lies flat, giving one faint curvilinear cue and almost no shadow, unlike a pot which is rigid and casts a clean shadow. Written up in `docs/EXPERIMENT_GV6.md`. |
| "What does it detect well?" | Seabed **pipelines** at mAP50 **0.869** on 615 held-out boxes, derelict crab pots at 0.314 on 567, shipwrecks 0.279 on 836. |
| "How accurate are the positions?" | 4.3–4.5 m error radius here, drawn on the map rather than hidden. Coordinates come from the ping headers with a slant-range correction; a detection with missing geometry is reported *without* a position rather than with a guessed one. |
| "What about false alarms?" | On 2,930 held-out tiles carrying no annotation, 7.8% flagged at the deployed operating point. Say "tiles carrying no annotation", not "verified-empty seabed" — roughly half come from survey lines the source dataset left entirely unannotated, so it is an upper bound. |
| "Is the confidence calibrated?" | Yes, temperature scaling. ECE 0.218 → 0.089. The maximum calibrated confidence this model ever produces is 0.728, so a 90% reading is not something it can output — and the UI keys off the uncertainty band, not a hardcoded number. |
| "Why is everything low priority?" | Because it should be. All five are `uncertainty: high` at 34–36%. The system is telling you it is unsure, and it is right. |

**Do not claim:** `plane` numbers (n=9 in test — one box is 11% of recall),
"verified-empty seabed", or that Docker output is real.

---

## 6. Reset between runs

Wipe all survey data, keep the login:

```bash
PGPASSWORD=ghostnet "/e/SIH-Debries-rudra/pgportable/pgsql/bin/psql.exe" -h 127.0.0.1 -U ghostnet -d ghostnet -c "delete from surveys;"
```

That cascades to files, frames, detections, jobs and reports.

Rebuild the whole demo state from scratch in one go — upload, process, export
both reports:

```bash
cd "E:/New folder/app/backend"
.venv/Scripts/python.exe ../../scripts/demo_seed.py
```

Re-run one survey without wiping it: send `{"force_restart": true}` to
`POST /api/v1/surveys/<id>/process`.

---

## 7. Troubleshooting

| symptom | cause | fix |
|---|---|---|
| UI shows "Unable to reach the server" | Frontend is on **3001** because 3000 was taken, so CORS blocks every call | Free port 3000 and restart `npm run dev`. Or start the backend with `CORS_ORIGINS` including 3001 |
| Every request 500s; tests error with `OperationalError` | Postgres is not running | Section 1 |
| `AI adapter: MockAIAdapter` at startup | `ghostnet` not importable, or no weights | `cd app/backend && .venv/Scripts/python.exe -c "import ghostnet; print(ghostnet.warmup())"`. If `False`, `ai/models/trained/ghostnet.pt` is missing. If ImportError, re-run `pip install -e ./ai --no-deps` from the repo root |
| `SETTINGS.device` says `cpu` on this machine | Broken torch install, **not** a missing GPU — `resolve_device()` catches the failure and falls back silently | Recreate the venv with `--system-site-packages`; see `app/README.md` |
| Process returns 409 | Working as designed — the survey already has detections | `force_restart: true`, or reset |
| Upload rejected as too large | File over `max_upload_size_mb` (200) | Use the 40 MB slice |
| 3D view looks empty | Default camera does not frame the survey | Click **Fit Survey** |
| Detections have no coordinates | The frame carried no usable sonar geometry | Expected and honest — check `localization_method`; `none` means it declined to guess |
| `pytest` at the repo root only runs 246 AI tests | By design after the monorepo merge | Backend suite: `cd app/backend && .venv/Scripts/python.exe -m pytest` |

---

## 8. Pre-demo checklist

```
[ ] Postgres listening on 5432
[ ] Port 3000 free BEFORE starting the frontend
[ ] Backend log shows "ghostnet contract 1.1.0" and "weights loaded=True"
[ ] Frontend says "Local: http://localhost:3000"
[ ] Logged in as operator, dashboard shows the survey
[ ] GIS Map shows 5 detections / 40 track points
[ ] 3D view: clicked Fit Survey once, markers visible
[ ] A detection detail page opens with the sonar frame and bbox
[ ] Both reports downloadable
[ ] demo/reports/ copies on hand as a fallback
```
