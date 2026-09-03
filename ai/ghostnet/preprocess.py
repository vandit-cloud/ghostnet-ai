"""Speckle suppression (problem statement requirement 3).

    from ghostnet.preprocess import preprocess

    frame = preprocess(gray)          # uses SETTINGS.preprocessing

Side-scan sonar is speckled: coherent acoustic returns interfere, producing a
grain that is not the seabed. The build plan's §12 warns that no filter should
be assumed to help, so this was measured before it was written, and the
measurement changed the plan twice.

What was measured, and why the default is "none"
------------------------------------------------
This was measured three times and the answer changed twice. The sequence is
recorded because the mistake in the middle is easy to repeat.

An outside review reported detection "collapses to zero at speckle sigma 0.35".
That was one image. Over 109 frames the model is far more robust, and the
filter recovers a great deal on degraded input -- frames that detect on clean
data, after synthetic speckle:

    sigma 0.35    noisy 71/109    despeckled 95/109    +34%
    sigma 0.50    noisy 61/109    despeckled 93/109    +53%
    sigma 0.70    noisy 48/109    despeckled 75/109    +56%

On clean data the same frame-level count showed no cost at all -- 109/140
either way, with 15% fewer false alarms -- which looked like free upside.

IT IS NOT. Scored properly, as mAP over the whole 4,346-frame test split:

                        mAP50    mAP50-95   precision   recall
    gv5, raw frames     0.3525    0.1995      0.5795    0.3609
    gv5, despeckled     0.3066    0.1644      0.5484    0.3468
                        -13%      -18%

The frame-level metric -- "does this frame yield any detection" -- hid the
whole regression. Boxes still appeared; they were looser and less well
localised, which mAP50-95 punishes hardest and a yes/no count cannot see. A
crude proxy agreed with the hypothesis twice before a real metric disagreed.

The cause is domain mismatch, not the filter. gv5 was trained on raw speckled
frames, so despeckling at inference moves every input off the distribution it
learned. That is why the DEFAULT IS "none", and why applying this to a model
trained without it is a regression dressed as an improvement.

Two things follow, and only one of them is settled:

  * SETTLED: do not despeckle at inference for a model trained without it.
  * OPEN: a model TRAINED on despeckled data would not have the mismatch, and
    the robustness numbers above say there is something real to gain on noisy
    input. That needs a training run to answer, and it is the only remaining
    problem-statement item that does.

Why a 3x3 median
----------------
Four candidates were compared on 59 frames for the only trade that matters --
how much background speckle is removed against how much target contrast
survives:

    filter      speckle kept   contrast kept   ratio
    median3        86.0%          102.2%        1.19
    lee5           87.0%           99.7%        1.15
    bilateral      88.0%          100.0%        1.14
    nlm            98.5%          100.1%        1.02

Median wins on the ratio and is the cheapest of the four. Non-local means costs
orders of magnitude more time to do almost nothing. A 3x3 kernel, not 5x5: the
targets here are small, and a wider kernel starts removing the isolated bright
returns that ARE the object.

Never applied blindly
---------------------
`Settings.preprocessing` names the active filter and `provenance()` reports it,
so a stored detection records how its frame was processed. That matters because
a model trained on despeckled data and run on raw data (or the reverse) is a
silent domain mismatch, and the payload is the only place the mismatch would
ever be visible.
"""

from __future__ import annotations

from typing import Callable

import numpy as np

#: Kernel for the median filter. 3, not 5 -- see the module docstring.
MEDIAN_KSIZE = 3


def _identity(frame: np.ndarray) -> np.ndarray:
    return frame


def _median(frame: np.ndarray) -> np.ndarray:
    import cv2

    return cv2.medianBlur(frame, MEDIAN_KSIZE)


#: Name -> filter. The names are recorded in payload provenance, so treat them
#: as a wire format: add, never rename. "none" must stay the default, because
#: gv5 and everything before it were trained and scored without any filter.
PREPROCESSORS: dict[str, Callable[[np.ndarray], np.ndarray]] = {
    "none": _identity,
    "median3-v1": _median,
}

DEFAULT = "none"


def preprocess(frame: np.ndarray, name: str = DEFAULT) -> np.ndarray:
    """Apply a named filter. An unknown name is a no-op, not an error.

    A frame is worth more than a preprocessing preference: a typo in a config
    should degrade to unfiltered inference rather than take down a survey.
    """
    if frame is None:
        return frame
    return PREPROCESSORS.get(name, _identity)(frame)
