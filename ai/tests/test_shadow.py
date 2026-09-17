"""Shadow-evidence tests.

The thresholds in ghostnet/shadow.py came from measurement and cannot be
re-derived here, so these tests assert the two things that ARE decidable: that
the shadow is looked for on the correct side of nadir, and that every path
which cannot answer says so instead of guessing.

The direction test is the one that matters. A proposed implementation defaulted
nadir_col to 320 and would have read the near flank as the shadow for every
target to port of it -- a bug that produces confident, plausible, backwards
evidence, and one no amount of threshold tuning would reveal.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

from ghostnet.geo import SonarGeometry  # noqa: E402
from ghostnet.shadow import shadow_context  # noqa: E402


def frame(shadow_side: str) -> tuple[np.ndarray, list[int]]:
    """A 200x100 seabed with a bright object at x=90..110 and a dark strip
    on the requested side of it."""
    g = np.full((100, 200), 120, np.uint8)
    g[40:60, 90:110] = 220                       # the object return
    if shadow_side == "right":
        g[40:60, 110:140] = 20
    else:
        g[40:60, 60:90] = 20
    return g, [90, 40, 20, 20]


def geom_with_nadir(nadir_col: float) -> SonarGeometry:
    return SonarGeometry(
        nadir_col=nadir_col, range_resolution_m=0.05,
        altitude_m=3.0, heading_deg=0.0, along_track_res_m=0.05,
    )


def test_shadow_found_on_the_far_side_of_nadir():
    """Nadir at column 0: the object is to starboard, so its shadow is to the
    RIGHT. The same picture with the dark strip on the left is not a shadow."""
    g, bbox = frame("right")
    assert shadow_context(g, bbox, geom_with_nadir(0)).startswith("confirmed")

    g, bbox = frame("left")
    assert not shadow_context(g, bbox, geom_with_nadir(0)).startswith("confirmed")


def test_direction_flips_with_nadir():
    """The identical image reads the opposite way when the towfish is on the
    other side -- which is the whole reason geometry is required."""
    g, bbox = frame("left")
    # nadir to starboard of the object: the object is to PORT, shadow is left.
    assert shadow_context(g, bbox, geom_with_nadir(400)).startswith("confirmed")


@pytest.mark.parametrize(
    "kwargs,expected",
    [
        ({"geom": None}, "no sonar geometry"),
        ({"bbox": [90, 40, 4, 4]}, "too small"),
    ],
)
def test_unanswerable_cases_say_so(kwargs, expected):
    g, bbox = frame("right")
    args = {"gray": g, "bbox": bbox, "geom": geom_with_nadir(0)}
    args.update(kwargs)
    out = shadow_context(**args)
    assert out.startswith("not_evaluated"), out
    assert expected in out


def test_flat_classes_get_an_explanatory_absence():
    """A pipeline casts no shadow. The reviewer must not read that as doubt."""
    g = np.full((100, 200), 120, np.uint8)
    g[40:60, 90:110] = 220
    out = shadow_context(g, [90, 40, 20, 20], geom_with_nadir(0), cls="debris")
    assert out.startswith("absent, as expected"), out
    assert "not evidence against" in out


def test_object_never_suppressed_by_a_shadow_verdict():
    """shadow_context returns a STRING and nothing else. If it ever gains the
    power to reject a detection, this test should be the thing that fails."""
    g, bbox = frame("right")
    assert isinstance(shadow_context(g, bbox, geom_with_nadir(0)), str)
