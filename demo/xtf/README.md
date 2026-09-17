# Per-class demo containers

Four uploadable `.xtf` files, one per object class, for demonstrating the whole
pipeline from an upload rather than from a pre-seeded database row:

| file | what is in it |
|---|---|
| `wrecks_demo_fixture.xtf` | 4 shipwreck frames + 2 clean seabed |
| `aircraft_demo_fixture.xtf` | 4 submerged aircraft + 2 clean seabed |
| `debris_demo_fixture.xtf` | 4 pipeline/debris frames + 2 clean seabed |
| `ghost_gear_demo_fixture.xtf` | 1 ghost net, 3 crab pots + 2 clean seabed |

Drop one into a new survey and press Start Processing. The reader splits it
into six 640×640 tiles, the model scores each, and the track is drawn from the
ping headers.

## These are fixtures, and the filenames say so

**Real:** every sample is pixel data from a real side-scan frame in a public
dataset's **held-out** split — nothing here was trained on. The detections the
app produces are produced live by the model, from these bytes, through the
ordinary pipeline. Nothing is pre-recorded or hand-placed.

**Synthetic:** the container and its navigation. These pings never existed as
pings; they are a re-encoding of imagery that arrived as PNG and JPEG, given a
track in the Gulf of Mannar so the geolocation half of the system has something
to work on. The frames come from four different countries, so there is no real
track they could share.

**Processed:** each frame's own across-track brightness trend is replaced with
a sonar-like one — bright at nadir, falling toward the outer swath. This is not
decoration. `waterfall()` works out which way round a channel's samples are
stored by comparing the mean amplitude at its two ends, so a frame that is
uniformly bright edge to edge has no detectable orientation and the reader will
mirror half of it. The correction is a per-column gain: it rescales columns
without moving anything, so shapes, shadows and local contrast are untouched.
Real sonar processing applies the same correction (TVG and beam-pattern).

Per-frame provenance — original filename, source dataset, split, and the
confidence and IoU the model achieves **after** the round trip — is in
`demo/showcase/manifest.json`.

## Not committed; rebuild them

`*.xtf` is gitignored and these are 6.4 MB each. They are generated from
`demo/showcase/frames/`, which **is** committed, so a clone rebuilds them in
about half a minute:

```bash
.venv/Scripts/python.exe scripts/build_demo_xtf.py
```

That script verifies each file as it writes it: it reads the container back
through the real reader and asserts the waterfall round-trips at correlation
> 0.98 against what was intended. A mirrored channel is the failure that would
otherwise pass unnoticed — the file still parses, still tiles, and still yields
detections, just on a mirrored image.

## Why the frames are the ones they are

They were chosen by whether the model still finds the labelled object **after**
the full round trip, not before it. That distinction matters more than it
sounds: `waterfall()` finishes with a 2–98 percentile stretch, and that stretch
alone costs detections — an otherwise untouched frame loses them going through
it. Ranking on the source PNG picked frames that scored beautifully and then
arrived at the model as something it no longer recognised, which is how the
pipeline survey once went from 5 detections to 1.

Selection is a demo decision, and `scripts/build_demo_xtf.py` and
`docs/DEMO_RUNBOOK.md` both say so. What was *not* curated is the model's
output on them.
