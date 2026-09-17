# Known issues — full app walkthrough, 2026-09-04

Findings from driving every surface of the app end to end: the four the user hit
by hand, plus everything a systematic pass over the API and the page code turned
up. Each entry says what happens, how to see it again, and where it comes from.

## Status, 2026-09-05

Everything that stood between the app and a working demo has been fixed and
verified against the running stack; the rest is still open and still described
below as it was found.

| | | |
|---|---|---|
| **A1** finished job vanishes | **fixed** | `GET /surveys/{id}/jobs/latest`, and the page reads only that |
| **A2** no completion state | **fixed** | counts plus Detections / Map / Report links when a run ends |
| **A3** progress bar jumps | **fixed** | one source of truth, and the stepper handles QUEUED and DONE |
| **A4** no way to delete a survey | **fixed** | `DELETE /surveys/{id}`, hard, behind a typed-name confirm |
| **B1** dashboard counts all surveys | **fixed** | every stat scoped to the survey the card names |
| **B2** no survey on a detection row | **fixed** | Survey column plus a Survey filter |
| **D1** IPv6 fallback on every call | **fixed** | frontend addresses `127.0.0.1` |
| **B3** selected-detection report | open | needs a `reports.detection_id` migration |
| **B4** filtered-detections report | open | page never sends `filters` |
| **B5** bbox bounds ignore the filter | open | |
| **C1-C7** API robustness | open | lenient, not broken, except C1 |
| **F1** starboard half of every frame mirrored | **fixed** | sample order detected per channel; nadir now lands at the centre |
| **F2** uploaded images never produced a detection | **fixed** | the frame stored a storage key where the detector needed a path |
| **F3** boxes hugging the tile edge | **fixed** | shape-based suppression in the decision layer, reported not silent |

Verified end to end after the fixes: a 40-frame run through the browser reports
40 processed / 5 detections, the bar moves 0 -> 100 without ever moving
backward, all eight stepper nodes are lit at DONE, and the completed job is
still on screen after a reload. 61 backend tests pass, including ten new
regressions in `app/backend/tests/test_demo_blockers.py`.

Ordered worst first. Ownership is marked per the build plans:
**M2** = frontend / backend / database / GIS (member 2),
**M1** = AI / ML / sonar (member 1),
**env** = local setup, nobody's code.

Verified against the running stack (Postgres 5432, backend 8000, frontend 3000),
model `gv5-yolo11s`, 4 surveys in the database.

---

## A · Blocks a demo

### A1 · A finished job vanishes and the page says nothing ran — **M2** — FIXED

*This is the "it shows processing but gives no output" report.*

**What happens.** Upload a file, press Start Processing, watch it run. The moment
it finishes, the processing screen flips back to
*"No processing job is running for this survey."* with a fresh
`Start Processing` button — as if nothing had happened. There is no result, no
count, no error. The work actually succeeded: both surveys the user ran this way
hold **40 frames and 5 detections each**, sitting correctly in the database.

**Reproduce.** New survey → upload `demo/NBP0505_line01B_demo.xtf` → Start
Processing → wait ~14 s. Or straight from the API:

```bash
# on a COMPLETED survey
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/surveys/<completed-id>/jobs/active
null
```

**Cause.** Two things compounding, both in
`app/frontend/src/app/app/surveys/[surveyId]/process/page.tsx:20-27`:

```ts
const { data: activeJob } = useActiveJob(surveyId);   // /surveys/{id}/jobs/active
const { data: job }       = useJob(activeJob?.id);    // /jobs/{id}
const displayedJob = job ?? activeJob;
```

`/jobs/active` only returns jobs in `QUEUED | VALIDATING | PROCESSING`
(`app/backend/app/services/processing_service.py:25,38`). On completion it
returns `null`, so `activeJob` becomes null, so `useJob(activeJob?.id)` is
called with `undefined` — a *different* React Query cache key, which holds no
data and is disabled. `job` goes undefined too, `displayedJob` is null, and the
page renders its empty state. The completed job is still fetchable at
`/jobs/{id}`; the page has simply lost the id.

**Note.** The 409 re-process guard makes this worse than it looks: the user's
instinct is to press Start Processing again, which is refused, so the survey
looks both un-run and un-runnable.

**Fixed by.** A new `GET /surveys/{survey_id}/jobs/latest` returns the survey's
most recent job whatever state it is in, and the processing page now reads that
and nothing else — `useActiveJob` and `useJob` are gone from it, so there is no
id to lose and no second source to disagree with. The endpoint 404s for a
survey that does not exist, so "bad id" stays distinguishable from "never
processed". The 409 the note describes now surfaces the server's own message
instead of a generic failure, and the completion panel offers an explicit
**Re-process** that confirms before discarding.

### A2 · Nothing tells you where the results went — **M2** — FIXED

Even with A1 fixed, the processing page has no completion state: no
"40 frames, 5 detections", no `View Detections` or `Open Map` button, no
navigation. The survey page has those two links, but the user is left on the
processing screen and has to work out on their own that the sidebar now has
something to show. Related to B1/B2, which make finding the results harder
still.

**Fixed by.** `CompletionPanel` in the processing page: frames processed,
frames failed, detections found, and buttons through to Detections, Map and
Report, every link carrying `?survey_id=` so the destination opens scoped. A
run that found nothing says so in words rather than looking like a failure, and
a FAILED or CANCELLED run gets its own panel with Run Again.

### A3 · The progress bar jumps forward and backward — **M2** — FIXED

*The "glitched, moves forward backward recklessly" report.* Two independent
causes; both need fixing.

**Cause 1 — two sources of truth that disagree.** `displayedJob = job ?? activeJob`
reads two endpoints that are refreshed on different triggers: `["active-job"]`
is invalidated on `job.updated`, `["job", id]` on every `frame.processed` *and*
polled every 1500 ms (`app/frontend/src/features/processing/hooks.ts:19-27`,
`app/frontend/src/hooks/useRealtime.ts:60-72`). Whenever `job` is momentarily
absent the display falls back to the staler `activeJob`. Sampled during a real
run, the same instant reported:

```
 t      /jobs/active         /jobs/{id}          displayed
 0.0    0%  DECODING         22% VERIFICATION    22% VERIFICATION
 4.3    52% CALIBRATION      80% VERIFICATION    80% VERIFICATION
```

22 percentage points apart at t=0. Any fallback between those two is a visible
jump. The server's own `progress` is monotonic — it is
`(processed + failed) / total` over cumulative counters
(`processing_service.py:205`) — so the jumping is entirely client-side.

**Cause 2 — the stage stepper un-lights itself.**
`app/frontend/src/components/ProcessingProgress.tsx:5-14` lists **8** stages:

```
VALIDATING DECODING PREPROCESSING DETECTION VERIFICATION CALIBRATION GEOTAGGING SAVING
```

`app/backend/app/models/enums.py:30-40` defines **10** — it also has `QUEUED`
and `DONE`. `STAGES.indexOf(job.stage)` therefore returns `-1` for both, and
with `currentIndex === -1` every node renders `pending`. So the stepper is fully
grey while queued, lights up green through the run, then **goes completely grey
again the instant the stage becomes `DONE`**. That alone reads as the bar
collapsing backward at the finish.

**Reproduce.** Watch the last second of a run. Or check the arrays against each
other — no run needed.

**Fixed by.** Cause 1 is gone with A1 — there is only one endpoint now, and the
server's `progress` was always monotonic. Cause 2 is a `stageIndex()` helper in
`ProcessingProgress.tsx` that maps DONE (and the COMPLETED/PARTIAL statuses) to
"past the end", QUEUED to "before the start", instead of letting `indexOf`
return -1 for both. Watched in a browser this time, not inferred: sampled every
150 ms through a real 40-frame run, the bar went 0 -> 100 in 55 samples without
one backward step, and all eight nodes were lit at DONE.

### A4 · No way to delete a survey — **M2** — FIXED

*Requested feature, and it is a real gap.* There is **no DELETE route anywhere
in the API** — not for surveys, files, detections, jobs or reports:

```bash
curl -X DELETE .../api/v1/surveys/<id>   ->  405 Method Not Allowed
```

Confirmed by enumerating every path in `/openapi.json`: zero `delete` methods.
So a mistaken upload is permanent through the UI, and the only cleanup is raw
SQL — which `docs/DEMO_RUNBOOK.md` §6 has to document:

```sql
delete from surveys;   -- cascades to files, frames, detections, jobs, reports
```

The cascade already exists at the database level (`ondelete="CASCADE"`), so the
hard part is done; what is missing is a route, a confirm dialog, and a button.
Worth deciding whether delete is soft (recoverable, keeps the audit trail) or
hard — see the open question at the bottom.

**Fixed by.** `DELETE /surveys/{survey_id}` -> 204, hard delete, per the
decision recorded under Open questions. The service stops any still-running job
task first (it holds its own Session and would otherwise keep writing to a
deleted row) and removes the survey's storage directory, then lets the existing
database cascade take files, frames, detections, jobs, reports and the reviews
hanging off those detections. In the UI it is a **Delete Survey** button on the
survey page behind a dialog that requires the survey's name to be typed.

---

## B · Shows the wrong thing

### B1 · The Dashboard names one survey and counts all of them — **M2** — FIXED

`app/backend/app/services/dashboard_service.py:22` picks `current_survey` as the
most recently updated survey. Every number beside it — `candidates`,
`needs_review`, `confirmed_artificial`, `rejected_natural`, `high_priority`,
`class_distribution`, `detection_trend` — is a **global** count with no survey
filter (lines 53-90). With 4 surveys in the database right now:

```
current_survey = "PROBE walkthrough run"
candidates = 20     frames = 160     debris = 20
```

That survey has 5 detections and 40 frames. The card is showing the sum of all
four. During a demo this reads as the app inventing detections.

**Side effect.** Because `current_survey` is ordered by `updated_at`, *renaming*
a survey silently makes it the current mission.

**Fixed by.** Every stat in `build_dashboard_summary` is scoped to
`current_survey.id` — the card names a survey, so the card counts that survey.
With no surveys at all every scoped number is 0 rather than an error. The
rename side effect is unchanged and still true; it is now harmless, because the
numbers follow the name.

### B2 · The Detections table doesn't say which survey a row belongs to — **M2** — FIXED

Columns are Detection ID, Class, Confidence, Uncertainty, Priority, Location,
Review Status (`app/frontend/src/components/DetectionTable.tsx:59-65`). No
survey column, and the page has filters for Class / Priority / Review Status but
**none for survey** — survey scoping only happens if you arrive with
`?survey_id=` in the URL from a survey page
(`app/app/detections/page.tsx:46`). Land on Detections from the sidebar and you
get every detection from every survey in one undifferentiated list.

Together with B1, this is most of why a freshly processed survey feels like it
produced nothing: the numbers don't match it and the rows don't name it.

**Fixed by.** `DetectionOut` carries `survey_name` (resolved in one query per
page, not one per row), `DetectionTable` has a Survey column linking back to the
survey, and the Detections page has a Survey filter alongside Class / Priority /
Review Status. The column hides itself when the page is already scoped to one
survey rather than repeating the same name down every row.

### B3 · A "selected detection" report contains the whole survey — **M2**

Ask for a report on one detection and you get all of them, labelled
`type: selected_detection`. Verified byte-identical to the full-survey export:

```
full_survey        -> 5 data rows
selected_detection -> 5 data rows      (asked for 1)
cmp: IDENTICAL
```

**Cause.** `detection_id` is accepted by the API schema
(`app/backend/app/schemas/report.py`) and then dropped on the floor:

- `app/backend/app/models/report.py:14-23` — the `Report` table **has no
  `detection_id` column**.
- `app/backend/app/services/report_service.py:76-83` — `create_report` never
  reads `payload.detection_id`.
- `report_service.py:158-163` — the background generator rebuilds a
  `ReportCreate` from the stored row *without* `detection_id`, so the filter at
  line 60 (`if type == SELECTED_DETECTION and payload.detection_id`) can never
  be true.

This is a data-correctness bug, not cosmetic: the export claims a scope it does
not have. Needs a migration to fix properly.

### B4 · "Filtered detections" reports are also unfiltered — **M2**

Same output as full survey. The backend *can* filter
(`report_service.py:62-71` reads `class`, `priority`, `review_status`,
`min_confidence` out of `filters`), but the Reports page never sends a `filters`
object — it posts only `survey_id`, `type`, `format`
(`app/frontend/src/app/app/reports/page.tsx:44`). So the dropdown option exists
and does nothing. Either wire the Detections page's active filters through, or
remove the option until it works.

### B5 · A bbox that excludes every marker still zooms to the whole survey — **M2**

The marker filter works (0 markers returned), but `bounds` is computed from
markers **plus the unfiltered track**
(`app/backend/app/api/v1/maps.py:56-63`), and the track is never filtered by
bbox. Result: the map frames the entire survey and shows nothing in it.

---

## C · API robustness

Each of these is small on its own. They matter because a judge poking the API,
or the next person writing a client, hits them.

| # | probe | now | should be | owner |
|---|---|---|---|---|
| C1 | `POST /reports` with an unknown `survey_id` | **500 INTERNAL_ERROR** | 404 SURVEY_NOT_FOUND | M2 |
| C2 | `POST /reports` `type=selected_detection`, no `detection_id` | 202 Accepted | 422 | M2 |
| C3 | `GET /surveys/<unknown>/jobs/active` | 200 `null` | 404 | M2 |
| C4 | `GET /detections?detection_class=dragon` | 200, empty list | 422 — a typo should not look like "no results" | M2 |
| C5 | `GET /detections?review_status=maybe` | 200, empty list | 422 | M2 |
| C6 | map bbox with `min > max` | 200, silently empty | 422 | M2 |
| C7 | review `note` of 10,000 characters | 201 Created | length cap, as `name` has (200) | M2 |

C1 is the only one that is outright broken rather than merely lenient — an
unhandled exception reaching the generic 500 handler.

**Working correctly**, checked and worth not "fixing": 401s on missing/garbage
tokens and wrong passwords; 404s for unknown survey / job / detection / frame /
report; 422s for malformed UUIDs, empty or 500-char names, `page=0`,
`page_size=100000`, `min_confidence` out of `[0,1]`, bogus report `format`;
`page=99999` returning an empty page; and the 409 re-process guard.

---

## F · Sonar assembly and the detector's edge behaviour

Found 2026-09-05, while asking why a demo frame looked like noise with a
sliver-shaped box against its right edge.

### F1 · The starboard half of every frame was mirrored — **M1** — FIXED

**What happened.** `waterfall()` reversed the port channel and took starboard as
written, on the assumption that both channels store samples near-range-first.
Measured over 640 pings of the demo file they do not:

| sample index | channel 0 | channel 1 |
|---|---|---|
| 0-127 (should be nadir) | **32.1** | 2.7 |
| 896-1023 (should be far range) | 2.2 | **45.2** |

Channel 1 is written far-range-first. Assembling it as-is produced a sawtooth
across-track profile instead of a bright nadir band down the middle:

```
col     0 (far port)    0.1     col  1024 (nadir)       1.2   <- should be bright
col  1023 (nadir)     100.2     col  2047 (far stbd)  137.9   <- should be dark
```

**Why it mattered beyond looks.** The nadir and water-column return, the
brightest feature in the data, was drawn at the OUTER edge of the swath. And
`geometry_for` places nadir at the image centre, so every starboard detection's
slant-range-to-ground-range conversion measured from the wrong place -- wrong
map positions, not just a wrong-looking picture.

**Fixed by.** Each channel's sample order is now detected from its own mean
amplitude profile over the whole chunk and oriented near-range-first before
assembly. Detected rather than hardcoded, because the correct choice is
vendor-dependent and the two channels in this one file disagree with each
other. After the fix the profile is 0.0 at both outer edges and 120-149 at the
centre, which is what `geometry_for` already assumed. Four regression tests in
`ai/tests/test_waterfall_orientation.py` cover all four storage conventions.

### F2 · An uploaded image could never produce a detection — **M2** — FIXED

**What happened.** Uploading .png/.jpg/.tif built a `SonarFrame` whose
`image_reference` was the storage-relative KEY (`<survey_id>/<unique_name>`).
`processing_service` hands that column straight to the AI adapter as a
filesystem path, where it resolves against the server's working directory
instead of the storage root. `cv2.imread` returned None, `detect()` recorded
"image not found" as a *warning* rather than an error, and the job finished
COMPLETED having found nothing.

Every response along the way was a 2xx, the file was marked VALID, the frame
row existed and the job said COMPLETED. The only symptom was a survey of
uploaded images with zero detections -- which reads as a weak model rather than
a broken path.

This is the same defect commit `144986c` fixed for the XTF branch. That branch
now carries a comment explaining the distinction; this one was missed.

**Fixed by.** `image_reference=str(storage.path_for(storage_reference))`, which
also makes the column mean one thing rather than two. Serving is unaffected --
`storage.open()` joins an absolute path unchanged. Covered by
`test_an_uploaded_image_frame_points_at_a_file_that_exists`.

### F3 · The detector boxes the tile edge — **M1** — FIXED

**This is what section E used to dismiss, and section E was wrong.** E recorded
the four sliver detections on NBP0505 as "edge-of-swath candidates [that]
genuinely are low-confidence... correct behaviour, no action." They were not
low-confidence real candidates. They were one artifact found four times.

Fixing F1 did **not** remove them, which is how we know they are a separate
problem. Before the fix all four sat at global columns 2009-2047 -- one fixed
place, the mirrored nadir band. After the fix they are spread across four
different tiles, each hugging that tile's own LOCAL edge:

```
tile x0=1280  local x 604-638      tile x0=   0  local x   0- 24
tile x0=1408  local x 601-639      tile x0= 640  local x   0-129
```

So the model reacts to the crop boundary itself. `_offsets()` pulls the last
tile back to end flush with the data, so one tile edge always coincides with
the swath edge, which is why it looked like a swath-edge problem.

**Fixed by.** `decision.is_edge_sliver`, applied in `detect()` before the
confidence policy. It is a SHAPE rule, not a position rule: a box is dropped
only if it touches a border AND is under 8% of that axis thick AND runs over
40% of the perpendicular axis. The observed artifacts are 34-38 px in a 640 px
tile (5-6%) running 386-640 px tall, so they clear it comfortably; the one
genuine `ghost_net` detection in the whole test set starts at x=0 and survives,
because at 95 px of 374 it is not thin.

Three things keep this honest rather than a number-flattering hack:

* **It is reported, not silent.** A frame that loses detections this way gains
  a warning saying how many and how to see them
  (`suppress_edge_slivers=False`).
* **It can be turned off**, and the tests assert that it can.
* **It does not pretend to be the real fix.** NMS in survey coordinates --
  merging the two halves an object splits into across a seam, rather than
  judging each half alone -- is still the right answer and still not done. This
  rule can discard a genuinely thin object clipped by a seam, and
  `is_edge_sliver`'s docstring says so.

**Measured effect.** NBP0505 went from 9 detections to 2, both interior. The
other 38 of its 40 frames now report nothing, which is the correct answer for
open seabed. Across the four Showcase surveys and all 40 NBP0505 frames there
are now **zero detections on verified-empty seabed**. Seven tests in
`ai/tests/test_decision.py`.

---

## D · Environment

### D1 · The frontend calls a hostname the backend only half-answers — **env** — FIXED

`app/frontend/.env.local` points at:

```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_WS_BASE_URL=ws://localhost:8000/api/v1
```

but the backend is started with `--host 127.0.0.1`, so **nothing listens on
`::1:8000`**. Every request to the name `localhost` tries IPv6 first and falls
back. Measured on this machine:

```
http://127.0.0.1:8000/health   median    1.6 ms
http://localhost:8000/health   median 2051.3 ms   (python urllib)
                                      205   ms    (curl)
```

Browsers recover faster than Python does, but this is dead time on every API
call and on the WebSocket, and it is the kind of thing that makes a progress bar
stutter for reasons that have nothing to do with the progress bar. Fix is a
one-liner either way: bind `--host ::` (and add the port to `cors_origins`), or
point `.env.local` at `127.0.0.1`.

*I measured this from the command line, not from the browser — worth
re-measuring in devtools before spending time on it.*

**Fixed by.** `.env.local`, its example, and the defaults in `api/client.ts` now
address `127.0.0.1` literally. `cors_origins` gained
`http://127.0.0.1:3000` so the browser can be opened at either spelling.

---

## E · Not bugs

Recorded so nobody spends a day on them.

- **409 on a second Process.** By design — a second run would append a duplicate
  copy of every detection and discard review decisions. `force_restart: true`
  overrides deliberately.
- **Every confidence sits near 0.35.** Half right, and the wrong half is
  corrected in F3. Temperature scaling really does cap this model's calibrated
  output at 0.728, and reporting a genuinely uncertain candidate as
  `uncertainty: high, priority: low` really is correct behaviour. But the four
  edge-of-swath candidates were **not** low-confidence real candidates -- they
  were one tiling artifact found four times, and calling them correct behaviour
  is what let them sit unexamined. See F1 and F3.
- **`ghost_net` finds nothing.** Known and documented in
  `docs/EXPERIMENT_GV6.md`. Acoustic limitation, not a code fault. **M1**.
- **Detections without coordinates.** The frame carried no usable geometry and
  the system declined to guess; `localization_method: none` says so.

---

## What I did not check

- The progress bar was diagnosed from the two endpoints and the component code,
  **not** by watching it in a browser. The two causes are certain from the code;
  the exact visual sequence is inferred.
- The 3D view, `Replay`, and the map's error circles were verified as rendering
  (HTTP 200 and data present), not inspected visually for correctness.
- No load, concurrency, or multi-user testing. Two operators reviewing the same
  detection at once is untested.
- Docker path deliberately untested — it runs on the mock adapter and is not a
  demo path.

## Open questions before fixing

1. **Delete: soft or hard?** — **decided: hard.** The review trail goes with
   the survey. The justification: the gesture being supported is erasing a
   mistaken upload, and an audit trail for a survey that no longer exists has
   nothing left to attest to. A soft delete would have meant filtering every
   list, map and dashboard query, which is a lot of surface to get wrong. The
   typed-name confirmation is what stands in for recoverability.
2. **Should the Dashboard follow a survey or the whole fleet?** — **decided:
   follow the survey.** The card leads with a survey name, so the numbers
   beside it are that survey's.
3. **B3 needs a migration** (`reports.detection_id`). Still open. Worth batching
   with any other schema change rather than shipping alone.
