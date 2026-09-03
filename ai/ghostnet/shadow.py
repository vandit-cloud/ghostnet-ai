"""Acoustic-shadow evidence for a detection (problem statement requirement 5).

A side-scan sonar lights the seabed from one side. An object standing proud of
the bottom blocks the beam, leaving an unensonified strip immediately BEYOND it
-- further from nadir. That shadow is the classic side-scan cue: it is often
clearer than the target return itself, and its length encodes object height.

    shadow_context(gray, bbox, geom) -> str      # for evidence_summary

What this is for, and what it is NOT for
----------------------------------------
It produces a sentence for a human reviewer. It never suppresses a detection,
never changes a class, and never moves a confidence. The measured signal is far
too weak to gate anything on, and the section below says how weak.

Why the obvious implementation was measured and thrown away
-----------------------------------------------------------
The natural version -- "look just beyond the box; if it is dark, that is a
shadow" -- does not work on this data. Measured over 561 wreck boxes in the
test split against a MATCHED control (the same statistic computed at random
columns on the same rows):

    ratio < 0.55   wrecks 42.2%   control 42.1%    lift x1.00
    ratio < 0.65   wrecks 51.7%   control 52.0%    lift x0.99

Zero discrimination. An earlier run appeared to show a large gap only because
it compared min(left, right) against a SINGLE random patch: a minimum of two
draws is biased low, and the whole effect was that bias. Any threshold picked
from those numbers would have fired on ordinary seabed as often as on shadow.

What does carry signal is ASYMMETRY between the two flanks:

    wreck flank asymmetry |R-L| / object mean   median 0.384
    random pair, same rows and width            median 0.255

Separation +0.130 -- real, modest, and exactly what a shadow on one side and
plain seabed on the other should produce. So the test here is PAIRED: the flank
away from nadir against the flank toward it, each normalised by the object's own
return. That cancels per-tile contrast normalisation, which differs by source
and which no absolute threshold can survive.

Requiring geometry is the point, not a limitation
--------------------------------------------------
Which flank the shadow falls on is decided by which side of nadir the object
sits, so this returns "not_evaluated" without sonar geometry. A proposed version
defaulted `nadir_col` to 320; the project's own example metadata has nadir_col
0, which would have pointed the ray the wrong way on every detection and
reported the near flank as the shadow.

Physics also predicts where this SHOULD find nothing, and the data agrees.
Measured by class, the flank darkening relative to control was:

    wreck       +0.263      stands proud, casts shadow
    ghost_pot   +0.058      small, low relief
    ghost_net   +0.023      lies flat -- no shadow, correctly
    debris      +0.014      buried/surface pipeline -- no shadow, correctly

So "absent" is NOT evidence against a detection. For a pipeline or a net it is
the expected answer, and the returned sentence says so rather than leaving a
reviewer to read absence as doubt.
"""

from __future__ import annotations

import numpy as np

from .geo import SonarGeometry, pixel_to_ground_offset

#: Flank contrast, in units of the object's own mean return, above which the
#: away-flank is called a shadow. 0.25 sits just below the random-pair median
#: asymmetry (0.255) measured above, so "confirmed" means an asymmetry larger
#: than most chance ones -- not a rare one. Deliberately not tuned finer: the
#: distributions overlap heavily and a sharper number would imply a precision
#: the measurement does not support.
CONFIRM_CONTRAST = 0.25
WEAK_CONTRAST = 0.10

#: Classes that lie flat on the seabed and are not expected to cast a shadow.
FLAT_CLASSES = frozenset({"debris", "ghost_net"})


def _flank(gray: np.ndarray, x0: int, x1: int, y0: int, y1: int) -> float | None:
    """Mean intensity of a clipped region, or None if it falls outside."""
    h, w = gray.shape[:2]
    x0, x1 = max(0, x0), min(w, x1)
    y0, y1 = max(0, y0), min(h, y1)
    if x1 - x0 < 3 or y1 - y0 < 3:
        return None
    patch = gray[y0:y1, x0:x1]
    return float(patch.mean()) if patch.size else None


def shadow_context(
    gray: np.ndarray,
    bbox: list[int],
    geom: SonarGeometry | None,
    cls: str = "",
) -> str:
    """One sentence of acoustic-shadow evidence for `evidence_summary`."""
    if geom is None:
        return "not_evaluated: no sonar geometry, so the shadow side is unknown"

    x, y, w, h = (int(v) for v in bbox)
    if w < 8 or h < 8:
        return "not_evaluated: detection too small to resolve a shadow"

    centre_col = x + w / 2.0
    _ground, side = pixel_to_ground_offset(centre_col, geom)

    # The shadow falls AWAY from nadir: to starboard of a starboard target,
    # to port of a port one. `side` is +1 starboard, -1 port.
    reach = max(10, w)
    if side >= 0:
        away = _flank(gray, x + w, x + w + reach, y, y + h)
        near = _flank(gray, x - reach, x, y, y + h)
    else:
        away = _flank(gray, x - reach, x, y, y + h)
        near = _flank(gray, x + w, x + w + reach, y, y + h)

    obj = _flank(gray, x, x + w, y, y + h)
    if obj is None or obj < 1.0:
        return "not_evaluated: object return too dark to normalise against"
    if away is None:
        return "not_evaluated: the shadow would fall outside this frame"
    if near is None:
        return "not_evaluated: no comparable near flank inside this frame"

    contrast = (near - away) / obj
    where = "starboard" if side >= 0 else "port"

    if contrast >= CONFIRM_CONTRAST:
        return (f"confirmed: the {where} flank is {contrast:.0%} darker than the near flank, "
                "consistent with an object standing proud of the seabed")
    if contrast >= WEAK_CONTRAST:
        return (f"weak: the {where} flank is {contrast:.0%} darker than the near flank, "
                "within the range ordinary seabed variation also produces")
    if cls in FLAT_CLASSES:
        return ("absent, as expected: a flat-lying target casts no shadow, so this is "
                "not evidence against the detection")
    return "absent: no flank darkening away from nadir"
