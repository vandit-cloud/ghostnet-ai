# GhostNet-AI — demo runbook

Everything needed to run the demo yourself, in order, with the exact commands.
Written 2026-09-04 after a full end-to-end verification on real sonar.

If you are driving the console rather than starting it, the click-by-click
guide is `docs/OPERATOR_MANUAL.md` — exact field names, what to type, and what
each screen does. This runbook covers bringing the stack up and the
presenter's script.

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
| Raw data manifest, with provenance and checksums | `demo/RAW_DATA.md` |
| The 5 sonar frames the detections came from | `demo/raw_frames/D-*.png` |
| Raw table exports (survey, 40 frames, 5 detections) | `demo/raw_*_dbdump.csv` |
| Login | `operator` / `operator123` |

The sonar file and both reference reports are committed, so a fresh clone has
them (see `docs/SETUP.md`). The per-run leftovers in `demo/` — the survey id,
the table dumps, the extracted frames — are not, because they go stale;
`demo/RAW_DATA.md` §"Regenerating" rebuilds them.

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
Only `D-C1308A5C` (6.45 m × 43.6 m) is a plausible target.

### 6. Review Queue — human judgement, recorded

`Review Queue` shows everything pending. Accept one as artificial, reject
another as natural. The detection's `review_status` updates and the decision is
kept as an audit trail with reviewer and note — the model proposes, a person
decides, and the record shows who decided. The reviewer is taken from the
access token, not the request body, so a decision cannot be attributed to
someone who did not make it. Worth saying if a judge asks about audit
integrity.

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

## 5b. The four per-class demo files — upload them live

`NBP0505 Line 01B` is the honest headline: a real, unedited slice of a 2005
side-scan line. What it cannot do is let a judge check the model's work — real
seabed is mostly speckle, and after the tile-edge fix it reports 2 detections
across 40 frames, which is correct and undramatic.

`demo/xtf/` holds four containers you can **drag into the browser during the
demo**, one per object class:

| file | contents | detections |
|---|---|---|
| `wrecks_demo_fixture.xtf` | 4 shipwrecks + 2 clean seabed | 6 |
| `aircraft_demo_fixture.xtf` | 4 aircraft + 2 clean seabed | 7 |
| `debris_demo_fixture.xtf` | 4 pipeline frames + 2 clean seabed | 4 |
| `ghost_gear_demo_fixture.xtf` | 1 ghost net + 3 crab pots + 2 clean seabed | 13, incl. the net |

New Survey → drop the file → Start Processing. Six tiles, ~10 seconds, then the
completion panel and the detections.

> **Every target tile produces at least one detection. Every clean-seabed tile
> produces none.** That holds in all four files and across all 40 NBP0505
> frames. It is the sentence worth saying out loud, because the PS's hard part
> is telling debris from rocks and a detector that boxed everything would look
> identical on the target tiles alone.

They are not committed (`*.xtf` is gitignored, 6.4 MB each). Rebuild with:

```bash
.venv/Scripts/python.exe scripts/build_demo_xtf.py
```

They are also pre-seeded as four surveys by
`.venv/Scripts/python.exe ../../scripts/showcase_seed.py`, so there is a
fallback if a live upload goes wrong.

### What to say about them

Say it plainly — the answer is good, and the files are named
`*_demo_fixture.xtf` so the question is going to come up anyway:

- **The imagery is real.** Every sample is a real side-scan frame from a public
  dataset's **held-out** split. Nothing here was trained on.
- **The detections are not staged.** Produced live by the model at processing
  time, through the same code path the raw NBP0505 file takes.
- **The container is synthetic.** These pings never existed as pings; they are
  a re-encoding of frames that arrived as PNG and JPEG, given a track so the
  map has something to draw. The source frames come from four countries, so
  there is no real track they could share.
- **The frames were chosen** for being legible and for surviving the round trip
  — see `demo/xtf/README.md`. That selection is a demo decision. The model's
  output on them is not.

### Which detection to open

Sort the Detections table by **Confidence** before clicking. Each tile can
carry more than one box and the strongest is not first by default — on the
wrecks file the top detection is 59% with IoU 0.94 against the human label,
while an incidental one on the same hull sits at 36%.

Open **Sonar Viewer** on it: the frame, the box, and the AI evidence beside it
— `artificial verification`, `shadow context` (now real, because the container
carries geometry), and `notes`, which names the detector's finer class. A wreck
reads as *class Debris, detector class wreck*.

### Why NBP0505 only reports 2 detections

It used to report 9, and 8 were the same artifact: the detector reacting to the
640 px tile boundary and producing thin strips welded to a frame edge (F1/F3 in
docs/KNOWN_ISSUES.md). Those are now suppressed by shape, so 38 of its 40
frames correctly report nothing. The suppression can be switched off, a frame
that loses a detection to it says so in its warnings, and it is covered by
seven tests.

---

## 6. Reset between runs

**One survey**: open it and press **Delete Survey**, then type its name to
confirm. That removes its files, frames, detections, jobs, reports and the
review decisions on them, and deletes the uploaded bytes off disk. Use this to
clear a survey you uploaded live during a rehearsal — it is also worth showing,
since a judge who asks "what if I upload the wrong file?" is asking about this.

**Everything**, keeping the login:

```bash
PGPASSWORD=ghostnet "/e/SIH-Debries-rudra/pgportable/pgsql/bin/psql.exe" -h 127.0.0.1 -U ghostnet -d ghostnet -c "delete from surveys;"
```

That cascades to files, frames, detections, jobs and reports. It does not
remove the uploaded files from `app/backend/uploads/` — the Delete Survey button
does, the SQL does not.

**Before demoing**, check which survey the Dashboard is showing: its numbers are
now scoped to the survey it names, and that survey is the most recently updated
one. Open **NBP0505 Line 01B** last, or delete the leftover rehearsal surveys,
so the card leads with the one you are about to talk about.

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
| GIS map 404s | The survey id is wrong or the survey was deleted | Check `demo/.survey_id` against `select id from surveys;`. It used to answer 200-with-nothing here, which looked like "nothing found" |
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
