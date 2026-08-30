# Member 1 → Member 2 handoff

**Everything you need to build the whole application before the model exists.**

Contract version **1.0.0**. Read [Breaking changes](#breaking-changes) before you
rely on anything here.

---

## 1. What you get

| Thing | Where | Status |
|---|---|---|
| Frozen output schema | `contracts/ai-output.schema.json` | stable |
| Input schema | `contracts/ai-input.schema.json` | stable |
| Error envelope | `contracts/ai-error.schema.json` | stable |
| Example payloads | `ai/fixtures/*.json` | stable |
| Working inference package | `ai/ghostnet/` | runs today, returns empty detections until a model is trained |

The schemas are **generated** from `ai/ghostnet/contract.py`, not hand-written.
`ai/scripts/export_schemas.py --check` fails the build if they drift, so what is
in `contracts/` is always what the code actually emits.

---

## 2. Build against the fixtures, not against me

You do not need my machine, my GPU, or a trained model. Point your mock AI
adapter at these three files:

| Fixture | The case it covers | What your UI must do |
|---|---|---|
| `example_full.json` | Geometry and a nav fix were both available | Render two detections on the map with uncertainty circles |
| `example_no_metadata.json` | No navigation data | Render a detection with **no coordinates** without crashing |
| `example_empty.json` | Clean seabed, or no model loaded | Render a meaningful empty state |

`example_empty.json` is not an error and not a bug. A survey line with no debris
is the normal case, and the demo will show it.

---

## 3. The five fields that matter most

Most of the payload is self-explanatory. These five are the ones that get
misused, and misusing them is what turns an honest system into a dishonest one.

**`calibrated_confidence` — display this. Never display `raw_score`.**
A raw detector score is a ranking number, not a probability, and it is
systematically overconfident. `raw_score` is in the payload for debugging only.
Threshold on `calibrated_confidence`.

**`uncertainty` — `"low"` is a real claim, so treat it as one.**
Until the model is calibrated on a validation set, the pipeline **refuses to emit
`"low"`** and caps at `"medium"` no matter how high the score. If you see `"low"`,
a temperature was genuinely fitted. Colour-code accordingly.

**`latitude` / `longitude` can be `null`, and that is legal.**
Missing navigation metadata, or a detection inside the water column, means no
position can be derived. The pipeline reports the detection **without** a
position rather than inventing one. Do not treat `null` as corrupt data, do not
substitute `0, 0`, and do not drop the detection.

**`position_error_m` — draw the circle, not a pin.**
Every position carries an error radius combining GPS scatter, heading error
through the across-track lever arm, altitude uncertainty and layback. A bare pin
claims precision the physics does not support. Judges notice this.

**`warnings` — surface them.**
Non-fatal, but they are the explanation for everything odd on screen: why a
detection has no coordinates, how many were suppressed below the review floor,
whether any model was loaded at all. Hiding them makes the system look broken
when it is being careful.

---

## 4. `class`: four values, and `natural` is not noise

```
ghost_net | debris | natural | unknown
```

`natural` means the model actively decided "this is seabed topology, not a
man-made object." That is the evidence the artificial-vs-natural separation
works, which is one of the problem statement's own requirements. It is
**reported, not suppressed**.

Suggested handling: filter `natural` out of the default map view, but keep it
available behind a toggle and count it in the stats. Do not discard it at ingest.

`unknown` is an anomaly the model could not name. It is **actionable** — show it.

These are closed vocabularies. Your DB can use enum columns. Adding a value is a
breaking change and gets a major version bump.

---

## 5. How to call it

**Now, and probably at the demo too: import it.**

```bash
pip install -e ai/
```

```python
from ghostnet import detect, warmup

warmup()                       # call once from the FastAPI lifespan handler
result = detect(image_path, survey_meta)   # -> dict matching ai-output.schema.json
```

`detect()` **never raises** for a missing model, missing metadata or a missing
GPU. It returns a valid payload with `warnings` set. You do not need
`try/except` around it for those cases, and you must not treat them as failures.

You never import `ultralytics`, never touch a `.pt` file, never see a confidence
threshold. If you find yourself needing to, tell me — that is a contract gap.

**Later, only if we genuinely need two machines live:** a thin HTTP wrapper
around the same `detect()` call, `POST /ai/v1/infer`, multipart upload.

> **Not `image_path` over HTTP.** A filesystem path from your machine does not
> exist on mine. It will work perfectly in local testing and fail the instant the
> two PCs are actually connected. The image goes over the wire as a file part or
> a URL I can fetch. This is why `ai-input.schema.json` names the field `image`.

---

## 6. What I need from you

- A sample of the metadata you can realistically supply per frame. Which of
  `heading_deg`, `altitude_m`, `nadir_col`, `range_resolution_m` will actually be
  present? Coordinates require **all four** plus a lat/lon fix; without them
  every detection comes back with `localization: "none"`, which is a much less
  impressive demo.
- Your review-workflow expectations, so `review_status` transitions match what
  your DB stores.
- Anything in the payload you cannot render. Better to find it now.

---

## 7. Breaking changes

`contract_version` is semver and rides in every payload.

- **Patch** — docs, descriptions. Ignore it.
- **Minor** — a new optional field. Your code keeps working.
- **Major** — a renamed or removed field, or a new `class` / `uncertainty` value.
  **I will tell you before pushing one.**

Pin the major version in your validator and fail loudly on a mismatch. A silent
schema disagreement discovered during integration week is the single most
expensive thing that can happen to this project.
