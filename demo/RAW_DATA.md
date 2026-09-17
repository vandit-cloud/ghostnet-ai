# Raw data package — NBP0505 Line 01B

Everything in `demo/` and where it came from. Verified 2026-09-04 against a
live run of the app.

**What is committed:** `NBP0505_line01B_demo.xtf`, both files in `reports/`, and
this document — so a fresh clone can reproduce the run described here without
hunting for data. See `docs/SETUP.md`.

**What is not, and why:** `.survey_id` is per-database, `raw_*_dbdump.csv` is a
snapshot of one run, and `raw_frames/*.png` are named after detection refs that
change every time the survey is re-seeded. All three are rebuilt by the commands
at the bottom; shipping them would ship a stale copy.

---

## 1. The upload input — what you drag into the web app

| file | size | sha256 |
|---|---|---|
| `NBP0505_line01B_demo.xtf` | 40,000,000 B | `4e1d960e9c5eaa874a3f55a38b8bbe8f567075841f2381c6a87d47eca81aa025` |

**Provenance.** A byte-exact head slice of a real 2005 side-scan survey:
research vessel *Nathaniel B. Palmer*, cruise **NBP0505**, line **01B**, off
Golfo de Penas, Patagonia. Source file on this machine:

```
ai/data/raw/research/MGDS_Download/MGDS_Download/NBP0505/NBP050501B.XTF/NBP050501B.XTF
```

209,722,368 B, dated 2006-10-02, from the Marine Geoscience Data System (MGDS).
The slice's sha256 equals `head -c 40000000` of that file — checked, not
assumed, so the demo input traces to public archival data.

**Why sliced.** The original is 209 MB; the app's `max_upload_size_mb` is 200,
so the whole file is rejected at upload. Truncating XTF is safe — the reader
stops at the last complete ping. The slice yields **40 frames**.

**What the app reads out of it.** Not pre-cut images — the raw sonar container.
Per ping it reads latitude, longitude, heading and timestamp from the ping
header, which is what draws the vessel track and places detections.

## 2. Ground truth of this run — the database, exported raw

Straight `\copy` of the tables, no reshaping, all columns:

| file | rows | what |
|---|---|---|
| `raw_survey_dbdump.csv` | 1 | the survey record |
| `raw_frames_dbdump.csv` | 40 | every frame, with per-ping geometry |
| `raw_detections_dbdump.csv` | 5 | every detection, all 27 columns incl. `raw_score` before calibration |

`raw_detections_dbdump.csv` is the honest one: it carries both `raw_score` and
`calibrated_confidence`, so the temperature scaling is visible rather than
asserted. Example — `D-3AD4F717`: raw `0.1566` → calibrated `0.3501`.

## 3. The sonar imagery, as the model saw it

`raw_frames/D-*.png` — the five 640×640 frames that produced the five
detections, one per detection ref, exactly what the Sonar Investigation view
renders under the bounding box overlay.

Open `D-C1308A5C_frame.png` and `D-33588A6C_frame.png` side by side. The first
is the one plausible target (6.45 m × 43.6 m). The other four are tall thin
boxes hugging the dark right-hand edge — the far end of the swath, weakest
acoustic return, where the model fires on noise. `3.3 m × 935–1504 m` is not an
object, and you can see why on the image.

## 4. The deliverable reports — what the app exports

| file | size | sha256 |
|---|---|---|
| `reports/NBP0505_line01B_full_survey.csv` | 1,250 B | `72856f2dcef52d532a2a773f4a95c3894bfd370c0e8da5c2ba1e4140f2c56858` |
| `reports/NBP0505_line01B_full_survey.json` | 4,184 B | `99d379d113117910ec59cca61c46ae178afc4662671c154f1e88cbed364aadde` |

Regenerated live today from the running backend and byte-identical to these
copies. 15 CSV columns; every row names `model_version: gv5-yolo11s`, so a
stored result traces back to the exact training run.

Keep these two on hand as the demo fallback — if the app dies mid-presentation,
the deliverable still exists.

## 5. Bookkeeping

`.survey_id` — the survey UUID of the seeded run, currently
`1d145dd3-98ef-4dbb-8091-ba6c4dae25e4`. `demo_seed.py` rewrites it on every
seed. It used to go stale silently, which made map queries answer with an empty
survey instead of a 404.

---

## Regenerating all of it

The 40 MB input:

```bash
head -c 40000000 "ai/data/raw/research/MGDS_Download/MGDS_Download/NBP0505/NBP050501B.XTF/NBP050501B.XTF" > demo/NBP0505_line01B_demo.xtf
```

Everything else — upload, process, both reports, `.survey_id` — with the stack
running (see `docs/DEMO_RUNBOOK.md` §1–3):

```bash
cd "E:/New folder/app/backend"
.venv/Scripts/python.exe ../../scripts/demo_seed.py
```

Wipe first if a survey already exists, since a second `process` is refused with
409 by design:

```bash
PGPASSWORD=ghostnet "/e/SIH-Debries-rudra/pgportable/pgsql/bin/psql.exe" -h 127.0.0.1 -U ghostnet -d ghostnet -c "delete from surveys;"
```
