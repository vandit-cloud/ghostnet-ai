# GhostNet-AI — operator manual

How to drive the web console end to end: sign in, upload a raw sonar file,
process it, read what the model found, and export the evidence.

Written against a live end-to-end run of the console on 2026-09-04, model
`gv5-yolo11s`, survey *NBP0505 Line 01B*. Every button and field name below is
the literal on-screen label.

| | |
|---|---|
| Console | <http://localhost:3000> |
| Username | `operator` |
| Password | `operator123` |

Companion documents: `docs/DEMO_RUNBOOK.md` starts the stack and carries the
presenter's script; `demo/RAW_DATA.md` covers the input file's provenance and
checksums.

---

## 00 · Before you open the browser

Three services must already be up: Postgres on `5432`, the backend on `8000`,
the frontend on `3000`. Starting them is a separate job — see
`docs/DEMO_RUNBOOK.md` §1–3. Confirm the backend answers first:

```bash
curl -s http://localhost:8000/api/v1/health
{"status":"ok"}
```

> **Trap — this one costs you the whole demo.** The frontend **must** be on port
> 3000. If 3000 was busy, Next.js moves to 3001 without complaining, the
> backend's CORS policy then blocks every request, and the console shows only
> *"Unable to reach the server. Please try again."* — which looks exactly like
> the backend being down. Check the browser's address bar. If it says `3001`,
> stop, free port 3000, restart the frontend.

## 01 · Sign in

Single operator account; there is no self-service password reset in this build.

1. **Open `http://localhost:3000`.** You land on the sign-in screen — dark, with
   an ambient ocean background and the heading **Operator sign-in**. The root
   URL redirects here on its own.
2. **Fill the two fields.** `Username or email` → `operator`.
   `Password` → `operator123`.
3. **Press `Enter Console`.** You arrive on the Dashboard. If you instead get a
   red line under the password box, read it: a wrong password says so
   specifically, while *"Unable to reach the server"* means the backend or the
   port is wrong, not your credentials.

## 02 · The seven pages

The left sidebar numbers itself 01–07. That order follows the data, so it
doubles as a demo route.

| | page | what you do there |
|---|---|---|
| 01 | **Dashboard** | Mission summary — survey status, frame count, candidate count, class mix |
| 02 | **Surveys** | Create a survey, upload files into it, start processing |
| 03 | **Sonar Viewer** | Jump straight to the highest-priority pending detection |
| 04 | **Detections** | The full findings table, with filters |
| 05 | **Review Queue** | Accept or reject each candidate — the human decision |
| 06 | **GIS Map** | Vessel track and detections in 2D or 3D, with time replay |
| 07 | **Reports** | Generate and download CSV or JSON evidence |

A survey is already loaded when you first sign in — *NBP0505 Line 01B — Golfo
de Penas*, 40 frames, 5 candidates — so every page has something to show
immediately. Section 03 is only needed when you want to run your own file.

## 03 · Upload and process your own data

Four moves: create a survey, drop files in, start processing, watch it run.

### 1. Sidebar → `Surveys` → `New Survey`

Three fields; only the first is required.

| field | what to put |
|---|---|
| `Survey Name` | Anything, up to 200 characters. Non-ASCII is fine — accents and em-dashes round-trip correctly. |
| `Source (vessel / mission)` | For the demo file: `RV Nathaniel B. Palmer, NBP0505` |
| `Sonar Type` | `side-scan` |

Press `Create Survey`. You are taken to the survey's own page.

### 2. Drop the sonar file onto `Upload SSS Data`

The dropzone reads *"Drag & drop sonar files here"* — or click it to browse. It
takes several files at once. Accepted: `.xtf`, `.jsf`, `.tif`, `.tiff`, `.png`,
`.jpg`, `.jpeg`.

Use `demo/NBP0505_line01B_demo.xtf` (40 MB). A toast says *"Upload complete."*
and the file appears in the `Files` list below with a validation verdict.

**The five boxes above the dropzone** — `Latitude`, `Longitude`, `Depth (m)`,
`Heading (°)`, `Sonar Range (m)` — **leave all five blank for an XTF.** A raw
sonar container already carries position, heading and timestamp in every ping
header, and the app reads them from there. These boxes exist for plain image
files (PNG, TIFF) that have no geometry of their own; whatever you type is
applied to every file in that batch.

> **Trap — upload size.** The limit is 200 MB. The full source survey is 209 MB
> and gets rejected, which is exactly why the demo file is a 40 MB slice.
> Truncating an XTF is safe; the reader stops at the last complete ping.

### 3. Press `Start / Continue Processing`

Top-right of the survey page. It takes you to the processing screen, which shows
*"No processing job is running for this survey."* and a `Start Processing`
button. Press that.

The button is disabled until at least one file is uploaded — if it looks dead,
that is why, and the page says so underneath.

### 4. Watch it run

Progress is live over a WebSocket, not polling: a stage update per phase, one
event per frame, one per detection. For the 40-frame demo file that is **49
events in about 14 seconds** on the RTX 3050. `Cancel Processing` is available
while it is still queued or running.

It splits the file into 40 frames and reads each frame's latitude, longitude,
heading and timestamp straight from the ping headers. That is what draws the
vessel track — including the long stretches where nothing was found, which is
most of any real survey.

> **If you press Process twice.** A finished survey refuses a second run with
> `409 ALREADY_PROCESSED`. That is deliberate: a second pass would append a
> duplicate copy of every detection and discard the review decisions already
> recorded. To redo one on purpose, send `force_restart: true` to the process
> endpoint, or delete the survey and re-upload.

## 04 · Read what it found

Map for where, Sonar Viewer for whether it is real, Review Queue for the
decision.

### The map — `GIS Map`

Pick your survey in the `Survey` selector. You should see **5 detections and 40
track points** for the demo file. Filters for `Class`, `Priority` and
`Review Status` sit alongside.

- The line is the **vessel track**, drawn from the ping headers.
- Each detection is drawn as an **error circle, not a pin**. The radius is a
  real number — 4.3–4.5 m here — derived from GPS scatter, heading error and
  altitude uncertainty. A pin would claim a precision the system refuses to
  claim.
- Detections sit slightly **off** the track. That is correct: side-scan sonar
  looks sideways, so an object is not where the boat was. If they sat on the
  line, the geometry would be wrong.
- `2D` / `3D View` toggle at the top. `▶ Replay` walks the survey forward in
  time.

> **Trap — the 3D view looks empty.** It is not. The default camera just does
> not frame the survey on entry. Click `Fit Survey` once and everything appears.

### The detection itself — `Detections` → any row

You get the real 640×640 sonar frame with the bounding box drawn on it, beside
class, confidence, uncertainty band, priority, coordinates and dimensions. This
is where you decide whether the model found an object or fired on noise.

On the demo survey, four of the five candidates are tall thin boxes hugging the
dark right-hand edge of the frame. That edge is the far end of the sonar swath,
where acoustic return is weakest. Their dimensions read `3.3 m × 935–1504 m` —
and a 1.5 km piece of debris is plainly not an object. Only **`D-C1308A5C`**
(6.45 m × 43.6 m) is a plausible target.

**Say this out loud if you are presenting:** the dimensions are a free
plausibility filter, and the system already flagged all five
`uncertainty: high`, `priority: low`, at 34–36% confidence — just above the
review floor. It is telling you it is unsure, and it is right. An operator
rejects those four in one click each.

### The decision — `Review Queue`

1. **Open `Review Queue` and click a pending detection.** You get the sonar
   image, the map location, the evidence summary and the review history for that
   one candidate. `Sonar Viewer` in the sidebar is a shortcut to the
   highest-priority pending one.
2. **Choose `Accept Artificial` or `Reject Natural`.** Accept means you judge it
   a man-made object; reject means seabed or noise. There is an optional note
   field — *"Add context for this decision"* — worth using, because the note is
   kept.
3. **Confirm it was recorded.** A toast says *"Review saved."* and you return to
   the queue. The detection's status changes and the decision is appended to
   `Review History` with the reviewer's name and your note.

   The reviewer is taken from your login token, never from the browser's
   request, so a decision cannot be attributed to someone who did not make it.
   That is the audit-integrity answer if a judge asks.

## 05 · Export the evidence

The deliverable. CSV opens in Excel; JSON is the machine format.

1. **Sidebar → `Reports`.** Three dropdowns: `Survey`, `Report Type`, `Format`.

   | report type | contains |
   |---|---|
   | `Full Survey` | Every detection in the survey. The normal choice. |
   | `Filtered Detections` | Only what your current filters select. |
   | `Selected Detection` | One detection. Greyed out unless you arrived from a detection page. |

2. **Press `Generate Report`.** Generation is asynchronous — the row appears
   immediately and settles on *"Ready to download"* within a couple of seconds.
3. **Open the report row and press `Download CSV` / `Download JSON`.** 15
   columns in the CSV. Every row names `model_version: gv5-yolo11s`, so any
   stored result traces back to the exact training run that produced it.
   Pre-generated copies live in `demo/reports/` — keep them open in a tab as a
   fallback in case the app dies mid-presentation.

## 06 · When something looks wrong

Most of these are the system behaving correctly. Read before assuming a bug.

| what you see | what it means |
|---|---|
| "Unable to reach the server" | Almost always the frontend on port 3001 instead of 3000, so CORS blocks every call. Check the address bar before anything else. |
| Every page errors at once | Postgres is not running. It reads like a code fault and is not. |
| Confidences all sit near 0.35 | Correct. This model's calibrated confidence never exceeds 0.728 — a 90% reading is not something it can output. The UI keys off the uncertainty band, not a number. |
| A detection has no coordinates | That frame carried no usable sonar geometry and the system declined to guess. Check `localization_method`: `none` means exactly that. |
| The map is empty | Wrong survey selected, or that survey has no geotagged detections. A survey that does not exist returns 404 rather than an empty map. |
| The 3D view is blank | Click `Fit Survey`. |
| Process button does nothing | No file uploaded yet, or the survey already finished — see the 409 note above. |

## 07 · Before you present

Walk this once, in order. Two minutes, and it catches everything that has ever
gone wrong.

```
[ ] Postgres listening on 5432
[ ] Port 3000 free BEFORE the frontend starts
[ ] Backend startup mentions the ghostnet contract and weights loaded=True
    -- if it says MockAIAdapter, stop; the detections would be invented
[ ] Browser address bar reads localhost:3000, not 3001
[ ] Signed in as operator, Dashboard shows the survey
[ ] GIS Map shows 5 detections and 40 track points
[ ] 3D view: Fit Survey clicked once, markers visible
[ ] A detection page opens with its sonar frame and bounding box
[ ] Both report formats download
[ ] demo/reports/ copies open in a spare tab as fallback
```

> **Never demo from Docker.** `docker compose up` starts, but the backend image
> cannot reach the `ai/` package, so it silently falls back to the mock adapter
> and every detection on screen is invented. Run it natively.
