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

**`uncertainty` — `"low"` is a real claim, and today it never happens.**
Until the model is calibrated on a validation set, the pipeline **refuses to emit
`"low"`** and caps at `"medium"` no matter how high the score. If you see `"low"`,
a temperature was genuinely fitted.

But do not design a UI state around it. Measured on 259 real detections from the
shipped model, the **highest** calibrated confidence produced was **0.728**, and
the `"low"` band starts at 0.75 — so `"low"` is currently unreachable, not merely
rare. Build the `"low"` branch so it renders correctly if it ever appears, and
expect `"medium"` and `"high"` to be the only two states you actually see.
Section 3b explains why, and it is the most misused thing in this contract.

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

## 3b. There are two score scales. Never set a threshold without saying which.

**This has now caused three separate defects, so it gets its own section.**

The detector emits a **raw score**. It is systematically overconfident, so a
fitted temperature squashes it toward 0.5 to produce
`calibrated_confidence`. The squash is severe, and it works *against* you at the
top of the range: to reach a calibrated 0.85, the detector must first produce a
raw 0.99.

| you want calibrated | detector must produce raw |
|---|---|
| 0.85 | 0.9912 |
| 0.80 | 0.9775 |
| 0.75 | 0.9520 |
| 0.65 | 0.8436 |
| 0.50 | 0.5000 |

0.50 is the fixed point: below it the squash raises scores, above it lowers them.

### What the shipped model actually produces

Measured over 500 random held-out tiles, 259 detections, at the deployed
detector floor:

| | calibrated confidence |
|---|---|
| 5th percentile | 0.318 |
| median | 0.422 |
| 75th percentile | 0.562 |
| 90th percentile | 0.664 |
| 99th percentile | 0.700 |
| **maximum** | **0.728** |

32.6% of tiles carried at least one detection. Band split: `low` **0.0%**,
`medium` 40.2%, `high` 59.8%.

**So the whole useful range is roughly 0.30 to 0.73.** A threshold at 0.8 or 0.85
selects nothing at all — it is not strict, it is dead.

### What to do instead

**Key your logic off `uncertainty`, not off numbers.** It is already computed
from band edges fitted to this distribution, it is a closed three-value
vocabulary, and it survives a retrain — which a hardcoded 0.85 does not. If you
have written priority tiers, severity colours, or alert rules against numeric
confidence, they are almost certainly selecting nothing. Check them against the
table above.

If you genuinely need a numeric threshold, take it from the table, and write the
scale name next to it in the code. Every one of the three defects this section
exists to prevent was a number chosen on one scale by someone reasoning about
the other.

**These figures are properties of one trained model.** They move on every
retrain, so re-measure rather than trusting them after the model changes, and
never carry a threshold across a model change without re-deriving it.

---

## 4. `class`: four values, and `natural` is not noise

```
ghost_net | debris | natural | unknown
```

`natural` means the model actively decided "this is seabed topology, not a
man-made object." It stays in the vocabulary because removing a value would be a
breaking change.

**But the shipped model never emits it, and no future model on this plan will.**
`natural` is not a training class. Every natural example the project has is a
hard negative — a tile with no object on it — which YOLO expresses as an empty
label file, not a class. A `natural` class would carry zero instances. Nobody is
going to hand-draw boxes around rocks, so this stays out for good. The reasoning
is written out at length in `ai/ghostnet/taxonomy.py`.

**So do not build a UI filter, tab, or legend entry for `natural`.** It can only
ever show an empty list. In practice you will see three values: `ghost_net`,
`debris`, `unknown`.

The artificial-vs-natural separation is still measured, and measured more
honestly than a class label would be: it is the **false-alarm rate on held-out
tiles carrying no annotation** — 7.8% at the deployed operating point. That is
the number to put on screen when you want to show the separation working. If you
want a "natural" figure in the dashboard, derive it from that, not from a class
count that will always be zero.

Note `review_status: rejected_natural` is a different thing and is correct: that
is a *human* deciding a detection was seabed after all. Keep it.

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

### 1.1.0 — `frame_position` (minor, nothing breaks)

A new optional top-level field. Pinned to major 1, your code keeps working and
can ignore it entirely.

```json
"frame_position": {
  "latitude": -46.351818,
  "longitude": -73.731983,
  "heading_deg": 348.5,
  "timestamp": "2005-07-01T05:54:51"
}
```

**Where the towfish was, which is not where any detection is.** A detection's
coordinates say where an object is; this says where the sensor was. You need it
to draw the survey track — and a track is what turns a scatter of pins into a
line someone can follow back to the water.

Two things make it worth storing on every frame:

- **It is present even on frames with no detections**, which is most of a real
  survey. A track built only from detections has gaps wherever the seabed was
  clean, which reads as missing data rather than as an uneventful stretch.
- **It carries the frame's own timestamp**, so frames can be ordered in
  acquisition order rather than by whenever the rows happened to be written.

`null` when the pings covering that frame carried no usable navigation — same
rule as everywhere else in this contract: no position rather than a made-up one.

Populated automatically for any frame produced by `detect_survey()` or
`iter_survey_frames()` from a `.xtf`, because the values are in the ping
headers. `null` for a bare image with no metadata.

### 1.3.0 — `mask` can now carry a polygon (minor, but check your types)

`Detection.mask` has been in the contract since 1.0 and was always `null`. From
1.3.0 it is filled for `ghost_net` when the optional net segmentation model is
configured (`GHOSTNET_NET_WEIGHTS`):

```json
"bbox": [320, 180, 190, 120],
"mask": [[330, 290], [345, 298], [508, 192], [494, 182]],
"review_only": true
```

- **Same pixel frame and origin as `bbox`**: integer `[x, y]` pairs, top-left
  origin. Draw it with the same scale you already apply to the box.
- **Still `null` for every other class**, and for nets when no segmentation
  model is configured. Treat `null` as "box only", not as an error.
- **Nets stay `review_only: true`.** A better outline is still a candidate.
- **Why a minor bump for an old key:** nothing ever filled it, so a consumer
  could have mistyped it without anything failing. The backend had it as a
  string. Check yours.
- **Which model fills it (26 Sep 2026):** a U-Net, `gvU1n-unet-hardneg-s1`,
  promoted to `ai/models/trained/ghostnet_net.pt` by
  `ai/scripts/promote_net_model.py`. A promoted file is used automatically;
  `GHOSTNET_NET_WEIGHTS=none` switches it off. A YOLO-seg checkpoint still
  works in the same slot.
- **`provenance.net_model_version` says whether it ran.** It names the model
  only on frames where the net model produced the nets. When it is configured
  but did not run (failed to load, unreadable frame, a crash on that frame) it
  reads `none (configured net model did not run on this frame)`, and the
  frame's nets came from the box detector.
