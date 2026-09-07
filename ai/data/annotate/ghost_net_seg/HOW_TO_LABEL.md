# Labelling ghost nets as polygons

73 chips, `images/`. Worked examples in `_guide/` — start with
`00_box_vs_polygon.jpg`, then `03_what_a_chain_looks_like.jpg`.

## What you are looking for

**A chain: repeated dark beads in a line.** Not a blob, not a shadow — a
*repetition*. Usually several roughly parallel chains running diagonally
across the frame. Zoom in; the repetition is the signal, a single dark speck
is speckle.

## The rule that matters

**One polygon per chain. Follow the chain, do not enclose it.**

**The beads go down the MIDDLE of the polygon, and the polygon is only just
wide enough to hold them.** Two separate things, both required:

* *Centred* — if the chain runs along one edge of your strip, everything on the
  other side of it is seabed you are labelling as net.
* *Narrow* — about **20-25 px** wide. A bead chain is roughly 10 px, so that is
  the chain plus a small margin. A perfectly centred 45 px strip is still wrong.

Worked reference: `_guide/12_width_closeup.jpg` shows a 45 px strip with the
beads hugging its left edge — the mistake. Chips `quanzhou_HN_001`, `_008` and
`_009` are the target.

Trace a long thin strip along the line of beads, a few pixels either side.

**Vertex count follows the chain, not a target.** A straight chain needs
exactly 4 vertices — a rotated quad hugging the beads is the correct answer and
adding points to a straight line buys nothing. Add vertices only where the
chain actually bends. What is always wrong is an *axis-aligned* box; what is
fine is a 4-point strip at whatever angle the chain runs.

**Stop where the beads stop.** Do not run the strip on to the frame edge if the
chain fades out before it. The empty tail teaches "plain seabed is a ghost
net", which is the exact failure this re-annotation exists to remove.

Why: the current boxes claim a **median 56% of the frame** as net (up to 86%).
In the schematic in `_guide/00_box_vs_polygon.jpg` the same chain is 39% of the
frame as a box and 5% as a polygon. Everything inside a box and outside the net
is teaching the detector that plain seabed is a ghost net — which is the most
likely reason the class scores recall 0.000.

## Do

- One polygon per chain, even when chains are parallel and close together.
- Follow curves and bends with extra vertices.
- Include the beads and a thin margin. Nothing more.
- Leave an image with no polygon if you genuinely see no chain. That is a
  legitimate negative and the converter will name it so you can confirm.

## Do not

- Do not use the rectangle tool. `Ctrl+N` is polygon. The converter refuses
  rectangles on purpose — a rectangle re-creates exactly the problem this
  re-annotation exists to fix.
- Do not merge several parallel chains into one polygon. The gaps between them
  are seabed.
- Do not draw one polygon around a whole net array.
- Do not guess. An uncertain chain left unlabelled costs less than a wrong one:
  36 test boxes cannot absorb noisy ground truth.

## Keyboard

| key | action |
|---|---|
| `Ctrl+N` | new polygon |
| click | add vertex · click the first vertex to close |
| `Ctrl+Z` | undo last vertex |
| `D` / `A` | next / previous image |
| `Ctrl+Shift+drag` | move a vertex after closing |

Autosave is ON by default in labelme 7, so there is no save step: the JSON
lands beside the image as you go.

**labelme 7 dropped two flags that older guides still show.** `--autosave` is
now the default (disable with `--no-auto-save`) and `--nodata` became the
opt-in `--with-image-data`. Passing either old flag is an immediate error.

## Progress and conversion

```bash
# safe to run any time, writes nothing
.venv/Scripts/python.exe ai/scripts/labelme_to_yoloseg.py --class ghost_net --dry-run

# when finished
.venv/Scripts/python.exe ai/scripts/labelme_to_yoloseg.py --class ghost_net
```

## If in doubt

Stop and ask rather than guessing a convention. Two contradictory definitions
of a class is the failure `stage_annotations.py` documents for `plane`, and it
is worse than fewer labels.
