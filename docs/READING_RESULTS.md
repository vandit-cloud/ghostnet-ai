# Reading the results: did the model actually work?

How to interpret everything the model tells you — the terminal output, the
annotated image, the JSON payload, and every part of the test bench page.

Companion to `docs/TESTING_GUIDE.md`, which covers *how to run it*. This one
covers *what the output means*.

---

## Part 0 — The most important thing to understand first

**The test bench page and `try_model.py` are two different things.**

| | What it is | Your own images? |
|---|---|---|
| `try_model.py` | Runs the model, right now, on any images you point it at | **Yes — this is the one to use** |
| `testbench.html` | A frozen snapshot of 23 pre-chosen test tiles | **No. Never.** |

The test bench was generated once, from the official test split, and baked into
a file. It is a *report*, not an application. Nothing you put in `E:\sonar-test`
will ever appear in it, no matter how many times you reload it.

So: run `try_model.py`, then look in `ai\experiments\tryout\`. That folder is
where your own results live.

---

## Part 1 — Reading the terminal output

```
  b-25-800.jpg                     reported=0  below_floor=0  top=0.000
```

Three numbers, and you need all three.

**`reported`** — detections at or above the review floor. These are what a human
reviewer would be shown. This is the "the model found something" number.

**`below_floor`** — detections the model produced but suppressed as too
uncertain. **This is the number people forget, and it is the most diagnostic
one.** It separates two completely different situations:

| reported | below_floor | What it means |
|---|---|---|
| 0 | 0 | The model saw **nothing at all**. Either the image is genuinely empty, or it is so far outside what the model knows that nothing registered. |
| 0 | 2 | The model **did** see something, but wasn't confident enough. Lower the threshold with `--conf 0.10` and look at what it found. |
| 3 | 0 | Confident detections, nothing marginal. The clean case. |

**`top`** — the highest calibrated confidence on that image. `top=0.000` means
literally nothing was produced. `top=0.19` with `reported=0` means you missed a
detection by one hundredth — worth a second look at a lower floor.

### The summary line

```
  0 of 1 images had at least one detection at or above 0.2
```

On a folder of survey tiles, most images *should* report nothing. Real seabed is
overwhelmingly empty. A model that fires on every frame is broken in a way that
looks like success.

### The warning

```
  - incomplete sonar geometry; detections reported without coordinates
```

**This is not an error.** It appears on every image that has no navigation
metadata attached — which is all of them, unless you supply a GPS fix, heading,
altitude, nadir column and range resolution. It means: "I found things, but I
cannot tell you where on Earth they are, so I am not going to guess."

---

## Part 2 — Reading the annotated image

In `ai\experiments\tryout\<name>_annotated.jpg`:

- **Amber box** — reported. A reviewer would see this.
- **Blue box** — found, but held below the floor.

The label reads `debris 0.49`: the reported class, then the **calibrated
confidence**.

Look at three things, in this order:

1. **Is there a box at all?** No box means nothing was produced.
2. **Is the box in the right place?** A box on empty seabed next to the real
   object is a false alarm *and* a miss, not a partial success.
3. **Does the box cover the whole object?** A small box on the corner of a large
   wreck means the model latched onto one feature, not the object. This is a
   failure, even though something was drawn.

Point 3 is the one that fools people. A box on the image is not a detection of
the thing in the image.

---

## Part 3 — Reading the JSON payload

`ai\experiments\tryout\<name>.json`. Field by field:

```json
{
  "detections": [
    {
      "raw_score": 0.1074,
      "calibrated_confidence": 0.2129,
      "uncertainty": "high",
      "bbox": [344, 344, 63, 68],
      "class": "debris",
      "latitude": null,
      "longitude": null,
      "localization": "none",
      "evidence_summary": { "notes": "detector class: ghost_pot" }
    }
  ],
  "warnings": ["incomplete sonar geometry; ..."],
  "contract_version": "1.0.0"
}
```

**`raw_score`** — the detector's own number. **Never quote this to anyone.** It
is a ranking score, not a probability; it is systematically overconfident. It is
in the file for debugging only.

**`calibrated_confidence`** — the same detection after temperature scaling
(T = 1.619 for this model). This is the number that means something close to
"probability this is real". Threshold on this. Show this.

**`uncertainty`** — `low`, `medium` or `high`, derived from the calibrated
confidence. `"high"` is the model telling you it is guessing. Treat a `high`
detection as a lead, not a finding.

**`bbox`** — `[x, y, width, height]` in pixels, from the top-left. Compare these
to your image size. A 63 × 68 box on a 640 × 450 image covers **1.5% of the
frame** — if the object you care about fills half the picture, that box is not
on your object even if it overlaps it.

**`class`** — the *contract* class the application receives: `ghost_net`,
`debris`, `natural` or `unknown`.

**`evidence_summary.notes`** — the *detector* class underneath: `wreck`,
`plane`, `debris` or `ghost_pot`. These differ on purpose. A `ghost_pot`
detection is reported as `debris` because a crab pot is fishing gear but is not
a net, and calling it one would be a lie.

**`latitude` / `longitude` / `localization`** — `null` and `"none"` without
navigation metadata. Legal and expected. See Part 1.

---

## Part 4 — A decision procedure

Work down this list. Stop at the first one that matches.

**1. Did the four known-good frames give the expected answers?**
(`docs/TESTING_GUIDE.md`, "Check it works before trusting it".) If not, the
setup is broken — the weights did not load, or the wrong interpreter ran. Fix
that before interpreting anything else.

**2. Is the object in your image a class this model can detect?**
Check the table below *before* concluding anything. If the answer is no, the
model failing is the model working as measured.

**3. Is `below_floor` greater than zero?**
Then it saw something. Re-run with `--conf 0.10` and look at where the boxes
landed.

**4. Is the image inside the model's world?**
Greyscale side-scan sonar, object roughly 640 px across. Colour, forward-looking
sonar, a photograph, or a whole waterfall shrunk to fit will all under-perform
or produce nothing.

**5. Only now**, if all four pass and it still fails: you have found a genuine
model weakness. Note the image and move on.

### What this model can and cannot detect

From the held-out test split, `gv2-yolo11s`:

| detector class | test instances | mAP50 | Verdict |
|---|---|---|---|
| `ghost_pot` | 567 | **0.297** | Works. This is the class the project is about. |
| `wreck` | 836 | 0.095 | Weak. Finds some wrecks, imprecisely. |
| `debris` | 14 | 0.106 | Too few examples to trust either way. |
| `plane` | 9 | 0.030 | **Recall 0.000. It does not detect aircraft.** |

Read that last row before testing on an aeroplane wreck. Nine training-relevant
examples is not enough to learn a class, and the metrics say so plainly.

---

## Part 5 — Worked example: the B-25 bomber image

**What you ran:**

```
b-25-800.jpg     reported=0  below_floor=0  top=0.000
```

**The image:** a 640 × 450 side-scan sonar image of a B-25 bomber wreck, in
amber false-colour. A genuinely good sonar image — a person can see the aircraft
instantly.

**Step 1 — read the numbers.** `reported=0` *and* `below_floor=0` *and*
`top=0.000`. Nothing was produced at all. Not "unsure" — blank.

**Step 2 — check the class.** It is an aircraft. The table above says `plane`
recall is **0.000**. The model was never going to find this. That alone explains
the result.

**Step 3 — check the domain anyway.** The image is amber false-colour; training
data is greyscale. Two problems, not one.

**Step 4 — isolate them.** Convert to greyscale and re-run:

```
b25_grey.png     reported=1   top=0.213
```

So colour *was* suppressing output. But look at what came back:

```
raw_score  0.1074      calibrated  0.2129      uncertainty  high
bbox       [344, 344, 63, 68]      class  debris  (detector: ghost_pot)
```

A 63 × 68 box — **1.5% of the frame** — on an aircraft that fills most of it,
labelled a crab pot, at `uncertainty: high`.

**Verdict: the model failed on this image, and greyscale conversion did not fix
it.** It latched onto one small fragment of the tail section and guessed. Anyone
reporting this as "the model detected the B-25" would be misreading their own
output — which is exactly why Part 2 says to check whether the box covers the
object, not just whether a box exists.

**What it teaches, and this is the useful part:** the metrics predicted this
before the test was run. `plane` recall 0.000 is not a footnote, it is a
statement that this capability does not exist. The measurements were honest, and
they were right.

**Where to get a fair test instead:** use tiles from
`ai\data\processed\test\images\` containing crab pots or wrecks, or crop a
greyscale side-scan image of derelict fishing gear to about 640 px square.

---

## Part 6 — The test bench page, element by element

`start "E:\New folder\ai\experiments\gv2-yolo11s\testbench.html"`

### The header strip

Four grey chips: `model = gv2-yolo11s`, `split = test · held out`,
`contract = 1.0.0`, `frames = 23 of 3410`.

"Held out" is the important one: these tiles were never trained on. "23 of 3410"
says you are looking at a hand-picked sample of the full test split, not all of
it.

### The four stat tiles

| Tile | What it means |
|---|---|
| **ghost_pot mAP50 0.297** | Accuracy on derelict fishing gear across 567 held-out boxes. The project's headline number. |
| **precision 0.451** | Of everything the model reported, this fraction was real. Higher = less crying wolf. |
| **recall 0.178** | Of everything that was really there, this fraction was found. Lower = more misses. This is the cost of the high precision. |
| **false alarms @ 0.20 2.9%** | Of 2,620 verified-empty seabed tiles, this fraction got a box anyway. |

Precision and recall always trade against each other. You cannot raise one
without lowering the other; you can only choose where to sit.

### The threshold console (the sticky bar)

**The slider** sets the review floor: the calibrated confidence below which a
detection is not shown. Dragging it hides and reveals boxes across the entire
page at once.

**`Shown here`** — total boxes currently visible across all 23 tiles.

**`False alarms`** — how many of those are on tiles that contain nothing. This
number should fall as you drag right.

**`Empty seabed flagged`** — the measured false-alarm rate on all 2,620 empty
tiles at this threshold. It reports the nearest threshold **actually measured**,
not an interpolated guess, so the number on screen is one that was really
observed.

**How to use it:** drag slowly from left to right and watch `Shown here` and
`False alarms` together. Below 0.20 the false alarms climb fast. Above 0.50 real
detections start disappearing faster than false ones. The useful range is in
between, and seeing it is the point of the control.

### The four sections

Ordered deliberately — two kinds of success, then two kinds of failure.

**Found it (8 frames)** — the model reported an object where the survey recorded
one. Dashed cyan is the human-drawn truth; solid amber is the model. Compare
them: a good detection sits on top of the truth box, not merely near it.

**Missed it (5 frames)** — a real object not reported at this threshold. You
will see a cyan truth box and no amber box. Lower the slider and some of these
light up — along with more false alarms elsewhere.

**Correctly ignored (5 frames)** — verified-empty seabed where the model
reported nothing. Blank tiles, and they are a *result*: this is the
artificial-vs-natural requirement working, the model declining to call a rock an
anomaly.

**False alarm (5 frames)** — empty seabed the model flagged anyway. Every one is
a dive somebody would waste. Drag the slider right and watch them disappear —
that is the argument for a higher floor, and the misses are the argument
against.

### The boxes

- **Solid amber** — a model detection, with class and calibrated confidence.
- **Dashed cyan** — human ground truth, the correct answer.

Cyan with no amber = a miss. Amber with no cyan = a false alarm. Overlapping =
a hit.

### Clicking a tile

Opens the complete contract payload for that frame — the same JSON described in
Part 3. Any warnings appear above it in an amber panel.

---

## Part 6b — Coordinates: it works, it just needs metadata

Geotagging is **implemented, not a to-do**. `ai/ghostnet/geo.py` does the real
work: slant-range to ground-range correction, water-column width, the
across-track offset perpendicular to heading, layback, and a position error
radius.

It stays silent because a bare PNG carries no navigation data. Supply the
metadata and coordinates appear.

**The six fields it needs** (all of them, or you get `localization: "none"`):

| field | meaning |
|---|---|
| `latitude`, `longitude` | a GPS fix for the tow point on this frame |
| `heading_deg` | vessel heading, so across-track can be turned into a direction |
| `altitude_m` | towfish height above the seabed, for the slant-range correction |
| `nadir_col` | pixel column directly beneath the towfish |
| `range_resolution_m` | metres per pixel across-track |

`layback_m` (cable payout behind the GPS antenna) is optional and defaults to 0.

**Demonstrated on a real detection, 2026-09-01:**

```
A) no metadata
   lat=None  lon=None  localization=none  position_error_m=None
   warnings: ['incomplete sonar geometry; detections reported without coordinates']

B) with the six fields
   lat=18.92180873  lon=72.83449789
   localization=frame-level  position_error_m=6.48
   warnings: []
```

**`position_error_m: 6.48`** is the point. The system does not claim a pin on a
map — it returns a circle of that radius, combining GPS scatter, heading error
through the across-track lever arm, altitude uncertainty and layback. Draw the
circle, never a bare pin.

So the coordinate pipeline is finished. What is missing is metadata from a real
survey, which is Member 2's side of the handoff (`docs/HANDOFF.md`, section 6).

**Known gap:** `ai/tests/` has tests for calibration, the contract schema, the
decision policy and the importers, but **no `test_geo.py`**. Geotagging is one
of the four named problem-statement deliverables and currently has no automated
coverage. Worth closing before submission.

---

## Part 7 — Quick answers

**"It found nothing on all my images."** Usually correct, and if you took them
from the test split, almost certainly correct: 2,620 of its 3,410 tiles are
empty seabed. Check the tile's label file before blaming the model —
`Get-Content ai\data\processed	est\labels\<name>.txt`. Empty file means
nothing is there and zero detections is the right answer. See
`docs/TESTING_GUIDE.md` for how to list tiles that do contain objects.

**"It found nothing on an image with an obvious object."** Check the class table
in Part 4 first, then the image requirements in Part 5. Most cases are one of
those two, not a broken model.

**"It drew a box but in the wrong place."** That is a false alarm, and it counts
against the model. Do not score it as a partial success.

**"Confidence is only 0.21, is that bad?"** It is above the 0.20 floor, so it
would be shown — but `uncertainty: high` means treat it as a lead. Calibrated
confidence is roughly a probability: 0.21 means about a one-in-five chance it is
real.

**"Why is the class `debris` when the notes say `ghost_pot`?"** `ghost_pot` is
the detector's internal class; `debris` is what the contract reports. A crab pot
is fishing gear but not a net, so it is never called `ghost_net`.

**"`localization: none` on everything."** Correct. No navigation metadata, so no
coordinates, and the pipeline refuses to invent them.
