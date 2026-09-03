# Integrating the model into the web app

**For Member 2.** The AI side is one Python function. This is what it takes,
what it returns, and the four things that will bite if they are not known up
front.

---

## What has to travel with the code

The repository does **not** contain the model. `*.pt` is gitignored, because
trained weights are build artefacts and would bloat every clone.

Copy these two files onto the machine that runs the app:

```
ai/models/trained/ghostnet.pt      19 MB   the model
ai/models/trained/ghostnet.json     1 KB   which run it came from, and its SHA-256
```

They must travel **together**. The sidecar is what makes every payload name its
own model (`model_version: "gv5-yolo11s"`); without it a stored detection
cannot be traced to the run that produced it, which is the whole point of the
provenance block.

Also copy `ai/models/calibrator/temperature.json`. Without it confidences are
raw detector scores, which are not probabilities and are systematically
overconfident. The package warns if it is missing or belongs to different
weights -- it compares by file content, not path, so a deployed copy at a new
location is fine.

---

## The API is two functions

```python
from ghostnet import detect, detect_batch, warmup

warmup()                      # call once at FastAPI startup
result  = detect(path, meta)             # one frame  -> one payload
results = detect_batch(paths, meta)      # many frames -> many payloads
```

Nothing else needs importing. You never touch ultralytics, never load a `.pt`,
never see a threshold. `meta` is optional acquisition metadata; without it you
get boxes and no coordinates, which is a valid result rather than an error.

Payload shape is frozen and validated against `contracts/ai-output.schema.json`.
Anything added there is a contract change and a version bump.

---

## **Use `detect_batch`. This is the one that matters.**

Measured on the RTX 3050 this project targets:

```
detect() one frame at a time      3.6 frames/s
detect_batch (batches of 8)      37.4 frames/s
```

Ten times, and the cause is not arithmetic. A single 640px frame is too little
work to pull the GPU out of its idle power state -- it stays at 255 MHz of a
2100 MHz boost clock, drawing 4.8 W. Feed it eight and it clocks to 1987 MHz at
40 W. **One frame at a time, this GPU is slower than its own CPU.** If you loop
`detect()` over an upload, the service will look ten times slower than it is
and the model will get the blame.

So: collect the frames of an upload, then hand the whole list to
`detect_batch`. Batch size comes from `SETTINGS.batch_size` (8; higher barely
helps and costs VRAM, of which there are 4 GB).

Rough planning figure: **a 1,000-frame survey takes about 30 seconds** on the
GPU, or about 2.5 minutes on CPU. Long enough to want a job queue and a
progress bar; short enough that it does not need a cluster.

---

## The two shapes of input

### 1. Images the user uploads

The common case. PNG or JPG frames, one per upload item.

```python
results = detect_batch(frame_paths, {"survey_id": upload_id})
```

Coordinates require acquisition metadata. Accept it as a JSON sidecar matching
`contracts/ai-input.schema.json` -- `ai/fixtures/survey_meta.example.json` is a
worked example. Per-frame values can be passed as
`meta["frames"][<file stem>]`, which overlays the shared keys.

Without metadata every detection comes back with `latitude: null` and
`localization: "none"`. That is the designed behaviour, not a failure: the
system never invents a position it cannot support.

### 2. A raw sonar file

```powershell
python ai\scripts\xtf_to_frames.py --xtf <survey>.xtf --out <dir> --detect
```

This is the demo worth showing. A real `.xtf` goes in; frames, a metadata
sidecar per frame, geotagged detections and `report.csv` come out, with
coordinates read from the sonar's own navigation. Verified on an EdgeTech 4200
survey from the 2005 Nathaniel B. Palmer cruise.

For the app, call the same functions the script does:
`ghostnet.xtf.iter_pings` / `waterfall` / `geometry_for`, then `detect_batch`.

JSF is **not** implemented -- no file was available to test against. Reject
`.jsf` uploads with a clear message rather than guessing at the format.

---

## What comes back

```jsonc
{
  "survey_id": "...", "frame_id": "...", "contract_version": "1.0.0",
  "provenance": { "model_version": "gv5-yolo11s", ... },
  "warnings": [ "..." ],            // frame-level, always show these
  "detections": [{
    "detection_id": "D-3D8DCFAC",
    "class": "debris",              // ghost_net | debris | natural | unknown
    "calibrated_confidence": 0.53,  // USE THIS
    "raw_score": 0.58,              // never show a user
    "uncertainty": "medium",        // low | medium | high
    "bbox": [x, y, w, h],
    "latitude": 18.921872, "longitude": 72.834693,
    "position_error_m": 3.18,
    "localization": "frame-level",  // frame-level | ping-level | none
    "dimensions": {"width": 9.93, "length": 27.3, "status": "estimated"},
    "review_status": "pending",     // pending | confirmed | rejected
    "evidence_summary": {
      "artificial_verification": "positive",
      "shadow_context": "confirmed: the starboard flank is 43% darker ...",
      "notes": "detector class: wreck"
    }
  }]
}
```

**Draw the error radius, not a pin.** `position_error_m` is a real number from
GPS scatter, heading error and altitude uncertainty. A pin claims precision the
data does not have.

**`class` is the frozen contract vocabulary, and it is coarser than what the
detector knows.** A shipwreck and an aircraft both report as `debris`; the
finer class is carried in `evidence_summary.notes` as "detector class: wreck".
Show that in the review panel -- it is the difference between a useful UI and a
confusing one.

**`natural` is reported, not hidden.** The model saying "that is a rock" is the
evidence that the artificial-vs-natural separation works. Filter it out of the
default map view if you like; keep it in the data.

**`evidence_summary` is written for a human.** Show it in the review panel
verbatim. Some of it explains an absence -- "absent, as expected: a flat-lying
target casts no shadow, so this is not evidence against the detection" -- and a
reviewer who does not see that will read a missing shadow as doubt.

---

## CSV export is already written

```python
from ghostnet.report import write_csv
write_csv(results, "survey_042.csv")
```

One row per detection, **plus one row per frame that produced none**, marked by
`record_type`. That is deliberate: a file with three rows is otherwise
ambiguous between "three anomalies across 500 frames" and "three frames
processed before something died", and in survey work those are completely
different facts.

The file is UTF-8 **with BOM** and uses `newline=""` -- both are load-bearing
for Excel on Windows and both fail silently otherwise. Serve it as-is.

---

## Four things that will bite

**1. It degrades, it does not raise.** Missing weights, missing metadata,
corrupt upload, unreadable frame -- all return a contract-valid payload with
`detections: []` and a `warnings` entry explaining why. Show the warnings. A
silent empty result and a "no weights loaded" empty result look identical to a
user and are completely different problems.

**2. Never expose `raw_score`.** Ranking, thresholding and display all use
`calibrated_confidence`. The review floor is 0.20 on the calibrated scale,
which is a raw score of 0.0225 -- the two are not interchangeable.

**3. Detections below the floor never reach you.** The model suppresses them
before returning, deliberately: the floor is a policy decision that belongs in
one place. If you want to expose a "show low-confidence" toggle, that is a
change to `review_floor_artificial`, not a filter in the UI.

**4. Call `warmup()` at startup.** The first inference in a process pays CUDA
initialisation, which is hundreds of milliseconds. Paying it during the first
user's upload makes the model look slow when it is not.

---

## The claims the UI may make

Straight from `docs/MODEL_CAPABILITY_EVIDENCE.md`, which has the numbers:

- **May say:** it detects derelict fishing gear (crab pots) and pipelines,
  flags man-made objects against natural seabed, reports calibrated confidence
  and a position with an error radius.
- **May not say:** it detects ghost nets. That class scores mAP50 0.009 with
  recall 0.000 at 215 training boxes. The annotation dataset is a real
  contribution; the detection claim is not supported.
