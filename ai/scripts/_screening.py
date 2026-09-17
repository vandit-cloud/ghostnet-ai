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
"""

from __future__ import annotations

import cv2
import numpy as np

# Tuned against the measured distribution of the real datasets, not guessed.
# off_hue at 0.010 rejected 9 of 74 debris frames and only 2 were genuinely
# contaminated: bright amber returns shift hue enough to look like paint
# against a darker copper background.
DEFAULT_LIMITS: dict[str, float] = {
    "off_hue": 0.040,
    "flat_midtone": 0.120,
    "ui_rows": 0.060,
    "pure_paint": 0.150,
}


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
            "ui_rows": ui_rows, "pure_paint": pure_paint}


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
    return None
