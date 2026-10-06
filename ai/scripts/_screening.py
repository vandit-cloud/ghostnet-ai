"""Overlay screening, shared by the dataset importers.

Separates raw sonar from contaminated frames: acquisition-software screenshots
with toolbars, annotated figures with leader lines, measurement scale bars,
copyright banners, and an annotator's graphics burned into the pixels. A
detector trained on those learns the overlay, not the object -- a shortcut that
validates beautifully and fails on real sonar.

Lives here rather than inside `ghostnet` on purpose: this is dataset-preparation
code, and the runtime package is what Member 2 installs. It should not carry
tooling they never call.

The one signal deliberately NOT used
------------------------------------
"Large flat dark region" looks like the obvious screenshot cue and is the worst
one available: acoustic shadow is flat and near-black, and it is the single
most informative feature in a side-scan image. Screening on it discards the
best data. Only flat MID-TONE counts, which is UI chrome rather than shadow.

A known limitation
------------------
RED paint on an AMBER palette is not reliably detected, and no threshold fixes
it. Red sits at hue 0 and the copper ramp near hue 17, so a red ring is not
"off hue"; and a saturated amber return reaches the same saturation as paint.
They genuinely overlap in colour space. Far-hue paint -- cyan, green, white,
blue -- IS caught, as are toolbars, caption bars and large painted areas.

Why a fifth signal exists: the four above are all FRACTIONS OF FRAME
---------------------------------------------------------------------
Every signal above is a mean over the image, so its sensitivity scales with how
much of the frame the contamination covers. That leaves a hole at marker scale.
A survey target report draws a small circle over the object -- 25x25 px on a
431x431 snippet, 261 px out of 185,761, a fraction of 0.0014 against an
`off_hue` limit of 0.040. Measured on 47 such snippets, all four signals
returned exactly 0.0 and every frame passed clean. A detector trained on them
learns the circle, which is the label-leak this module exists to prevent.

`marker_paint` closes it by measuring the largest blob of cold-hue paint in
ABSOLUTE PIXELS rather than as a fraction of frame, with three extra tests a
drawn marker passes and an artefact does not: brightness, compactness, and a
size floor.

This signal is a TRADE, not a clean separation, and the honest summary is
that no formulation tried was right on every population. Five were measured
against all 19,734 real frames and 563 survey snippets:

  1. largest saturated blob, ungated -- flagged clean amber SCTD sonar
     including the `plane` frame SCTD__000068, because a bright amber return
     is both saturated and contiguous (242 px, against a real marker's 261);
  2. the same, gated to achromatic frames -- safe, but blind to the 117
     targets in N-09-03/04, whose snippets use an amber palette;
  3. fixed cold band, no brightness or shape test -- 34 false positives from
     JPEG chroma ringing, which turns dark regions of a compressed warm
     palette blue-purple (one artefact was a 791x4 strip spanning the full
     frame width; another was noise scattered at 3% density);
  4. fixed cold band + bright + compact -- 11 flagged. SIX were genuine
     (SONARDETECT presentation slides and software screenshots) and five were
     CYAN- and BLUE-ramped SCTD frames, because the premise "sonar palettes
     are never cold" is false;
  5. off-hue relative to the frame's own dominant hue, to fix (4)'s palette
     problem -- measured WORSE, 52 flagged, because a bright amber return
     sits >25 hues from its own copper ramp. It reintroduced failure (1),
     including SCTD__000068 again.

(4) ships. It is wrong on roughly five cyan/blue-palette SCTD frames out of
19,734, and that is the accepted cost: (5) is wrong ten times more often and
in the direction that destroys `plane` data, a class with 39 training boxes.
Limits measured on both populations -- real markers V>=118, fill 0.352-0.55,
aspect 1.0-7.5; artefacts V=59, fill 0.034, aspect 198.

What it does NOT catch, stated so nobody assumes otherwise:

  * CYAN- and BLUE-ramped sonar is FALSELY flagged (SCTD__000153, 000420).
    Review a flagged frame by eye before deleting it.
  * RED paint on an AMBER palette -- hue 0 is where the palette lives. The
    known limitation above, unchanged.
  * A blue UI scale BAR, e.g. a sonar-acquisition screenshot already sitting
    in the val split (SONARDETECT__000189). It is 320x13 at aspect 24.6, so
    compactness excludes it by design -- it is chrome, not a marker, and
    `ui_rows` is the signal that ought to catch it. `ui_rows` reads 0.0 on
    that frame and `off_hue` 0.018 against a 0.040 limit, so all five signals
    pass it today. That is a real, separate gap and it is not fixed here.
"""

from __future__ import annotations

import cv2
import numpy as np

# Tuned against the measured distribution of the real datasets, not guessed.
# off_hue at 0.010 rejected 9 of 74 debris frames and only 2 were genuinely
# contaminated: bright amber returns shift hue enough to look like paint
# against a darker copper background.
# marker_paint is in PIXELS, not a fraction -- that is the point of it. 40 px
# sits well above JPEG colour fringing and well below a real marker's ~250.
DEFAULT_LIMITS: dict[str, float] = {
    "off_hue": 0.040,
    "flat_midtone": 0.120,
    "ui_rows": 0.060,
    "pure_paint": 0.150,
    "marker_paint": 40,
}

#: Green through blue. Most sonar palettes are grey or a warm ramp at hue
#: 0-40. NOT ALL -- SCTD ships cyan- and blue-ramped frames, and those are the
#: documented false positives of this signal. See the module docstring for why
#: the alternative measured worse.
COLD_HUE = (60, 170)

#: Shape tests that separate a drawn marker from JPEG chroma ringing. Measured
#: across 563 real markers: fill 0.352-0.55, aspect 1.0-7.5. The false
#: positives they exclude measured fill 0.034 and aspect 198.
MIN_MARKER_PX = 20
MARKER_MIN_FILL = 0.25
MARKER_MAX_ASPECT = 10.0

#: Annotation paint is drawn BRIGHT. JPEG chroma ringing is not: it lives in
#: dark regions, where a heavily compressed warm palette turns blue-purple.
#: Measured -- real markers V >= 118, the artefacts V = 59. At 100 the real
#: markers and the real contamination both survive and the ringing does not.
PAINT_MIN_VALUE = 100


def overlay_signals(image: np.ndarray) -> dict[str, float]:
    """Four measurements that separate raw sonar from a screenshot.

    off_hue      Sonar palettes are one hue -- greyscale, or a single amber or
                 copper ramp. A saturated colour far from the frame's dominant
                 hue is paint: a red circle, a cyan box, a leader line.
    flat_midtone Blocks with no texture at all, at mid brightness. Sonar always
                 carries speckle; a smooth grey panel is a toolbar. Mid-tone
                 explicitly, because flat DARK is acoustic shadow and precious.
    ui_rows      Rows near-constant across the full width and not dark. Window
                 borders and toolbars span the frame; seabed does not.
    pure_paint   Fully-saturated maximum-value pixels. Annotation paint is
                 exactly S=255; a sonar ramp through JPEG rarely is, over area.
    """
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hue, sat, val = (hsv[..., i].astype(np.int16) for i in range(3))

    saturated = sat > 60
    dominant = int(np.bincount(hue[saturated], minlength=180).argmax()) if saturated.any() else 0
    delta = np.minimum(np.abs(hue - dominant), 180 - np.abs(hue - dominant))
    off_hue = float(((sat > 120) & (val > 80) & (delta > 25)).mean())

    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    k = 16
    h, w = grey.shape[0] // k * k, grey.shape[1] // k * k
    if h and w:
        blocks = grey[:h, :w].reshape(h // k, k, w // k, k).swapaxes(1, 2).reshape(-1, k, k)
        sd, mu = blocks.std(axis=(1, 2)), blocks.mean(axis=(1, 2))
        flat_midtone = float(((sd < 3.0) & (mu > 55) & (mu < 225)).mean())
    else:
        flat_midtone = 0.0

    ui_rows = float(((grey.std(axis=1) < 4.0) & (grey.mean(axis=1) > 40)).mean())
    pure_paint = float(((sat >= 250) & (val >= 200)).mean())

    return {"off_hue": off_hue, "flat_midtone": flat_midtone,
            "ui_rows": ui_rows, "pure_paint": pure_paint,
            "marker_paint": float(marker_blob(image)[0])}


def cold_mask(image: np.ndarray) -> np.ndarray:
    """Every cold-hue painted pixel in the frame, not just the biggest blob.

    An annotator rarely draws only one thing. Survey target reports that label
    a contact with a circle often print the target ID beside it in the same
    colour, and a caller that inpaints only the largest blob leaves the ID
    behind -- still a label leak, and one `marker_paint` correctly keeps
    flagging. Removal wants this; localisation wants `marker_blob`.
    """
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hue, sat, val = (hsv[..., i].astype(np.int16) for i in range(3))
    # Fixed cold band, NOT off-hue relative to the frame's dominant hue.
    # Relative hue was tried and measured worse: it reintroduced design one's
    # failure, because a bright amber return sits more than 25 hues from its
    # own copper ramp, so it flagged 52 frames including the clean `plane`
    # frame SCTD__000068 that design one already got wrong. The fixed band
    # flags 11. Both are wrong somewhere; this one is wrong less often and in
    # a direction that does not cost `plane` data. See the module docstring.
    return ((hue > COLD_HUE[0]) & (hue < COLD_HUE[1])
            & (sat > 90) & (val > PAINT_MIN_VALUE)).astype(np.uint8)


def marker_blob(image: np.ndarray) -> tuple[int, np.ndarray | None, tuple[float, float] | None]:
    """Largest contiguous patch of cold-hue paint: (pixels, mask, centroid).

    Marker-scale annotation is measured in absolute pixels because it does not
    scale with the frame -- a 25x25 circle is a label leak on a 431x431 crop
    and equally one on a 4000 px waterfall. Callers that only want the number
    use `overlay_signals`; the mask and centroid exist for importers that
    remove the marker and keep its position as a localisation label.
    """
    mask = cold_mask(image)
    if not mask.any():
        return 0, None, None
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
    if count <= 1:
        return 0, None, None

    # Largest COMPACT blob, not largest blob. Cold-hue pixels also arise from
    # JPEG chroma ringing along a high-contrast border, and that is what the
    # first version flagged: a 791x4 strip spanning the full width of an amber
    # SCTD frame that had no paint on it at all. Two shape tests separate a
    # drawn marker from an artefact, both measured rather than assumed:
    #
    #   fill    a ring or glyph fills 0.35-0.55 of its own bbox; scattered
    #           chroma noise across a whole frame filled 0.034
    #   aspect  markers ran 1.0-7.5; the border fringe was 198:1
    #
    # Limits sit outside the measured marker range on both sides.
    best, best_area = None, 0
    for i in range(1, count):
        x, y, w, h, area = stats[i]
        if area < MIN_MARKER_PX or area <= best_area:
            continue
        if area / float(w * h) < MARKER_MIN_FILL:
            continue
        if max(w, h) / float(max(1, min(w, h))) > MARKER_MAX_ASPECT:
            continue
        best, best_area = i, int(area)
    if best is None:
        return 0, None, None
    cx, cy = centroids[best]
    return best_area, (labels == best).astype(np.uint8), (float(cx), float(cy))


def screen(signals: dict[str, float], limits: dict[str, float] | None = None) -> str | None:
    """Return why this frame is contaminated, or None to keep it."""
    limits = limits or DEFAULT_LIMITS
    if signals["off_hue"] > limits["off_hue"]:
        return f"burned-in coloured graphics (off_hue {signals['off_hue']:.3f})"
    if signals["flat_midtone"] > limits["flat_midtone"]:
        return f"UI panel or caption bar (flat_midtone {signals['flat_midtone']:.3f})"
    if signals["ui_rows"] > limits["ui_rows"]:
        return f"toolbar or window border (ui_rows {signals['ui_rows']:.3f})"
    if signals["pure_paint"] > limits["pure_paint"]:
        return f"large area of pure paint (pure_paint {signals['pure_paint']:.3f})"
    # .get on both sides: signals dicts recorded by earlier runs predate this
    # key, and a caller may pass a limits dict that does not set it.
    if signals.get("marker_paint", 0) > limits.get("marker_paint", float("inf")):
        return (f"annotation marker burned in "
                f"(marker_paint {signals['marker_paint']:.0f} px)")
    return None
