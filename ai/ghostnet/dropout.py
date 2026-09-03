"""Data-dropout detection (problem statement requirement 6).

A side-scan image is a time series stacked into a picture: each ROW is one
ping. When the sonar misses returns, when the tow cable glitches, or when a
tile is padded past the end of a swath, rows appear that carry no acoustic
information at all -- flat black, flat white, or flat anything.

    invalid_row_mask(gray)          -> bool array, one entry per row
    frame_dropout_note(gray)        -> str | None, for FrameResult.warnings
    dropout_context(gray, bbox)     -> str, for evidence_summary

Why this matters to a detector rather than just to an operator
--------------------------------------------------------------
A dead band is flat and near-black, and so is acoustic shadow. A detector that
has learned "dark region next to bright region" will happily fire on the edge
of a dropout, and the resulting box looks exactly like a confident find. The
cheapest defence is not a better model but knowing which pixels are real.

Padding counts as a dropout here, on purpose
--------------------------------------------
Measured over 500 test tiles, only two contained degenerate rows, and both were
PADDING rather than lost pings: 19 rows at the bottom edge of an AI4Shipwrecks
tile, and 256 interior rows of a SubPipe tile that extends past the end of its
swath. Both are pure black, mean 0.0 and std ~0.

They are reported the same way, because the operational question is not "did
the sonar drop a ping" but "is this detection standing on real data". For that
question, padding and a dead ping are the same fact.

The corpus is not evidence that dropouts are rare in the wild
-------------------------------------------------------------
0.4% of frames here contain any degenerate row, but these are curated tiles
from published datasets whose authors already removed bad pings, cropped around
annotated objects, and would not have published a survey line full of holes. A
live survey from Member 2 is where this earns its place. What the corpus DOES
establish is the false-positive rate: on 500 real frames the test fired twice,
and both times it was right.
"""

from __future__ import annotations

import numpy as np

#: A row whose spread is below this carries no information at any brightness --
#: flat black, flat white, or flat grey. Chosen as "essentially constant"
#: rather than tuned: real sonar rows in this corpus sit at a per-row std of
#: roughly 0.34x the frame median at the 1st percentile, which is orders of
#: magnitude above a constant row.
CONSTANT_ROW_STD = 1.0

#: A near-black row with almost no spread is a dead ping even if not exactly
#: constant, which is what the SubPipe padding looks like (mean 0.0, std 0.18).
DEAD_ROW_MEAN = 8.0
DEAD_ROW_STD = 3.0

#: Fraction of a detection's rows that must be invalid before its uncertainty
#: is widened. A quarter is the point where the box is no longer mostly
#: standing on real returns.
OVERLAP_ESCALATE = 0.25


def invalid_row_mask(gray: np.ndarray) -> np.ndarray:
    """True for each image row that carries no acoustic information."""
    if gray is None or gray.ndim != 2 or gray.shape[0] == 0:
        return np.zeros(0, bool)
    std = gray.std(axis=1)
    mean = gray.mean(axis=1)
    constant = std < CONSTANT_ROW_STD
    dead = ((mean < DEAD_ROW_MEAN) | (mean > 255 - DEAD_ROW_MEAN)) & (std < DEAD_ROW_STD)
    return constant | dead


def frame_dropout_note(gray: np.ndarray) -> str | None:
    """A frame-level warning when any pings are missing, or None."""
    mask = invalid_row_mask(gray)
    if mask.size == 0 or not mask.any():
        return None
    n = int(mask.sum())
    frac = n / mask.size
    # Padding is a run of dead rows CONTIGUOUS with the frame boundary, not a
    # row that happens to fall in the first few percent. The distinction is
    # what an operator acts on: edge padding is a tiling artefact and expected,
    # an interior hole means the sonar or the tow lost data on that line.
    lead = 0
    while lead < mask.size and mask[lead]:
        lead += 1
    trail = 0
    while trail < mask.size - lead and mask[mask.size - 1 - trail]:
        trail += 1
    interior = n - lead - trail
    where = "interior" if interior > 0 else "at the frame edge"
    return (f"{n} of {mask.size} rows ({frac:.0%}) carry no acoustic return "
            f"({where}); detections overlapping them are flagged individually")


def dropout_overlap(gray: np.ndarray, bbox: list[int]) -> float:
    """Fraction of a detection's rows that are dropouts. 0.0 when clean."""
    mask = invalid_row_mask(gray)
    if mask.size == 0:
        return 0.0
    _x, y, _w, h = (int(v) for v in bbox)
    y0, y1 = max(0, y), min(mask.size, y + h)
    if y1 <= y0:
        return 0.0
    return float(mask[y0:y1].mean())


def dropout_context(gray: np.ndarray, bbox: list[int]) -> str:
    """One sentence about the data this detection is standing on."""
    frac = dropout_overlap(gray, bbox)
    if frac <= 0.0:
        return "clear: every ping under this detection carries a return"
    if frac < OVERLAP_ESCALATE:
        return (f"partial: {frac:.0%} of the rows under this detection carry no return; "
                "the box still rests mostly on real data")
    return (f"UNRELIABLE: {frac:.0%} of the rows under this detection carry no acoustic "
            "return, so it may be an artefact of missing data rather than an object")
