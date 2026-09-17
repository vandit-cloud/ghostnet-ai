# Setup — from a fresh clone to a real end-to-end run

For anyone picking up this repo on a new machine. At the end you will have the
console running against the **real trained model**, on the same sonar file and
with the same 5 detections the docs describe — so a fix can be verified rather
than assumed.

Written 2026-09-05, verified on Windows 11. Linux/macOS differ only in the
path style and the venv activation.

> **The one thing to get right.** If the backend logs
> `AI adapter: MockAIAdapter -- these are NOT real detections`, stop and fix it
> before judging anything you see. The mock produces contract-valid but
> **invented** detections with confidences from 0.45 to 0.98. Debugging the
> frontend against those wastes a day. Step 6 is how you confirm.

---

## What ships in this repo

| | |
|---|---|
| `ai/models/trained/ghostnet.pt` | The deployed model, 18 MB, `gv5-yolo11s`. Committed on purpose — without it you get the mock. |
| `demo/NBP0505_line01B_demo.xtf` | 40 MB of real 2005 side-scan sonar. What you upload. Provenance and checksums in `demo/RAW_DATA.md`. |
| `demo/reports/*.csv|json` | Reference exports, so you can diff your run against a known-good one. |

Not shipped, and not needed: training datasets, run artefacts, `.env` files.

## Prerequisites

- **Python 3.12** (3.12.10 here). 3.13 is untested.
- **Node 18+** for the frontend.
- **PostgreSQL 14+ with PostGIS available.** PostGIS is not optional — the
  `detections.location` column is `geometry(Point,4326)`, and migration `0001`
  runs `CREATE EXTENSION postgis`, which fails if the extension is not
  installed on the server. On Windows, tick PostGIS in the Stack Builder or EDB
  installer; on Debian/Ubuntu, `apt install postgresql-16-postgis-3`.
- **A GPU is not required.** Inference falls back to CPU automatically and it is
  fast enough: measured **0.52 s/frame**, so the 40-frame demo file takes about
  21 seconds. Force it either way with `GHOSTNET_DEVICE=cpu` or `=cuda`.

## 1 · Clone

```bash
git clone https://github.com/vandit-cloud/ghostnet-ai.git
cd ghostnet-ai
git checkout main
```

## 2 · Database

Create the role and database the default `DATABASE_URL` expects:

```sql
CREATE USER ghostnet WITH PASSWORD 'ghostnet';
CREATE DATABASE ghostnet OWNER ghostnet;
```

You do **not** need to create the PostGIS extension by hand — migration `0001`
does it. You do need the server to have PostGIS installed.

## 3 · Python environment

From the repository root:

```bash
cd app/backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m pip install -e ../../ai
```

That last line installs the AI half by relative path. It is what makes
`import ghostnet` work from the backend, and therefore what decides whether you
get the real model or the mock.

> **If torch installs without CUDA and you have an NVIDIA GPU**, that is fine —
> see the CPU note above. If you *want* the GPU, install the CUDA build of
> torch first, then re-run the two commands above.

## 4 · Configuration

```bash
cp app/backend/.env.example app/backend/.env
cp app/frontend/.env.local.example app/frontend/.env.local
```

The defaults work as-is against the database from step 2. Change `JWT_SECRET`
if this will ever be reachable from outside your machine.

**Known wrinkle** — both example files point at the hostname `localhost`, while
the backend below binds `127.0.0.1`. Nothing listens on `::1`, so every request
pays an IPv6 fallback before retrying IPv4. Either use `127.0.0.1` in
`.env.local` or bind the backend to `::`. Logged as D1 in
`docs/KNOWN_ISSUES.md`.

## 5 · Schema

```bash
cd app/backend
.venv/Scripts/python.exe -m alembic upgrade head
```

Three migrations, ending at `0003`. Verify with
`select * from alembic_version;` — it should read `0003`.

The `operator` / `operator123` login is created automatically on first backend
start (`ensure_seed_admin`), so there is no user to seed by hand.

## 6 · Start the backend, and check the adapter

```bash
cd app/backend
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Confirm the real model loaded — this is the step that matters:

```bash
cd app/backend
.venv/Scripts/python.exe -c "import ghostnet; print(ghostnet.CONTRACT_VERSION, ghostnet.warmup())"
1.1.0 True
```

`True` means the weights loaded. `False` means `ai/models/trained/ghostnet.pt`
is missing; an `ImportError` means step 3's last line did not take.

Health check: `curl -s http://localhost:8000/api/v1/health` → `{"status":"ok"}`

## 7 · Start the frontend

**Port 3000 must be free.** If it is taken, Next.js moves to 3001 without
complaining, the backend's `cors_origins` then blocks every request, and the UI
shows only *"Unable to reach the server. Please try again."* — which looks
exactly like the backend being down.

```bash
cd app/frontend
npm install
npm run dev
```

Confirm it says `Local: http://localhost:3000` and **not** 3001. Open it and
log in as `operator` / `operator123`.

## 8 · The reference run

Two ways. Either drive the UI — `docs/OPERATOR_MANUAL.md` is the click-by-click
guide — or do it in one command:

```bash
cd app/backend
.venv/Scripts/python.exe ../../scripts/demo_seed.py
```

That creates the survey, uploads the sonar file, processes it, exports both
reports and stamps `demo/.survey_id`. **Expected result, and the thing to
compare against:**

```
40 frames, 5 detections
map: 5 markers, 40 track points
D-*  debris  confidence 0.34-0.36  uncertainty high  priority low
one plausible target at 6.45 m x 43.6 m; the other four are
3.3 m x 935-1504 m -- edge-of-swath noise, and correctly flagged
```

Detection refs (`D-XXXXXXXX`) are generated per run and will not match the
docs. The counts, classes, confidences and dimensions will.

Diff your export against the committed reference to confirm the pipeline agrees
end to end:

```bash
diff <(tail -n +2 demo/reports/NBP0505_line01B_full_survey.csv) <(tail -n +2 your-export.csv)
```

Columns other than the ids and timestamps should be identical.

## Reset between runs

A finished survey refuses a second `process` with **409 ALREADY_PROCESSED**, on
purpose — a second pass would append a duplicate copy of every detection and
discard review decisions. There is no delete route yet (issue A4), so to start
clean:

```sql
delete from surveys;   -- cascades to files, frames, detections, jobs, reports
```

Or send `{"force_restart": true}` to `POST /api/v1/surveys/<id>/process` to
redo one deliberately.

## Where to look next

| | |
|---|---|
| `docs/KNOWN_ISSUES.md` | Every open defect, worst first, with a repro and a `file:line` cause. **Start here.** |
| `docs/OPERATOR_MANUAL.md` | Driving the console, click by click |
| `docs/DEMO_RUNBOOK.md` | Presenting it, and the talking points that survive scrutiny |
| `demo/RAW_DATA.md` | Where the sonar file came from, with checksums |
| `docs/EXPERIMENT_GV6.md` | Why `ghost_net` scores near zero, and the run that proved it |

## Do not demo from Docker

`docker compose up` starts, but the backend image cannot reach the `ai/`
package, so it runs on `MockAIAdapter` and every detection is invented. Run it
natively.
