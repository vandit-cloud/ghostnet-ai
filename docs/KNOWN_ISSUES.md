# Known issues — full app walkthrough, 2026-09-04

Findings from driving every surface of the app end to end: the four the user hit
by hand, plus everything a systematic pass over the API and the page code turned
up. **Nothing here is fixed.** Each entry says what happens, how to see it
again, and where it comes from.

Ordered worst first. Ownership is marked per the build plans:
**M2** = frontend / backend / database / GIS (member 2),
**M1** = AI / ML / sonar (member 1),
**env** = local setup, nobody's code.

Verified against the running stack (Postgres 5432, backend 8000, frontend 3000),
model `gv5-yolo11s`, 4 surveys in the database.

---

## A · Blocks a demo

### A1 · A finished job vanishes and the page says nothing ran — **M2**

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

### A2 · Nothing tells you where the results went — **M2**

Even with A1 fixed, the processing page has no completion state: no
"40 frames, 5 detections", no `View Detections` or `Open Map` button, no
navigation. The survey page has those two links, but the user is left on the
processing screen and has to work out on their own that the sidebar now has
something to show. Related to B1/B2, which make finding the results harder
still.

### A3 · The progress bar jumps forward and backward — **M2**

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

### A4 · No way to delete a survey — **M2**

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

---

## B · Shows the wrong thing

### B1 · The Dashboard names one survey and counts all of them — **M2**

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

### B2 · The Detections table doesn't say which survey a row belongs to — **M2**

Columns are Detection ID, Class, Confidence, Uncertainty, Priority, Location,
Review Status (`app/frontend/src/components/DetectionTable.tsx:59-65`). No
survey column, and the page has filters for Class / Priority / Review Status but
**none for survey** — survey scoping only happens if you arrive with
`?survey_id=` in the URL from a survey page
(`app/app/detections/page.tsx:46`). Land on Detections from the sidebar and you
get every detection from every survey in one undifferentiated list.

Together with B1, this is most of why a freshly processed survey feels like it
produced nothing: the numbers don't match it and the rows don't name it.

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

## D · Environment

### D1 · The frontend calls a hostname the backend only half-answers — **env**

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

---

## E · Not bugs

Recorded so nobody spends a day on them.

- **409 on a second Process.** By design — a second run would append a duplicate
  copy of every detection and discard review decisions. `force_restart: true`
  overrides deliberately.
- **Every confidence sits near 0.35.** Real. Temperature scaling caps this
  model's calibrated output at 0.728; the four edge-of-swath candidates genuinely
  are low-confidence. Reporting them as `uncertainty: high, priority: low` is
  correct behaviour. **M1**, and no action.
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

1. **Delete: soft or hard?** A hard delete cascades away detections *and* their
   review audit trail, which sits badly with A4's own justification for keeping
   who-decided-what. A soft delete (hide, keep rows) preserves the trail but
   needs every list query filtered.
2. **Should the Dashboard follow a survey or the whole fleet?** B1 can be fixed
   in either direction — scope the counts to `current_survey`, or drop
   `current_survey` and label the numbers as fleet-wide. Pick one; the bug is
   that it currently does both.
3. **B3 needs a migration** (`reports.detection_id`). Worth batching with any
   other schema change rather than shipping alone.
