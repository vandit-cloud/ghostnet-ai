"""Speckle-filter tests (problem statement requirement 3).

The important assertion here is the DEFAULT. This filter measurably reduces
mAP50 by 13% when applied to a model trained without it, so a change that
quietly turns it on would look like a mysterious regression rather than a
config error.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

from ghostnet.config import Settings  # noqa: E402
from ghostnet.preprocess import DEFAULT, PREPROCESSORS, preprocess  # noqa: E402

rng = np.random.default_rng(0)


def seabed(h=120, w=200):
    return np.clip(rng.normal(120, 25, (h, w)), 0, 255).astype(np.uint8)


def test_the_default_is_no_filter():
    """gv5 and everything before it were trained and scored on raw frames.
    Despeckling them costs 13% of mAP50 -- see the module docstring."""
    assert DEFAULT == "none"
    assert Settings().preprocessing == "none"
    g = seabed()
    assert np.array_equal(preprocess(g), g), "the default must not touch the frame"


def test_named_filter_actually_filters():
    g = seabed()
    out = preprocess(g, "median3-v1")
    assert out.shape == g.shape and out.dtype == g.dtype
    assert out.std() < g.std(), "a despeckler must reduce spread"


def test_target_contrast_survives_the_filter():
    """A filter that removes speckle by removing the target is not a filter.
    Measured at 102% contrast retention over 59 real frames."""
    g = seabed()
    g[50:70, 90:110] = 230                       # a bright target
    def contrast(img):
        obj = img[50:70, 90:110].astype(float)
        m = np.ones(img.shape, bool); m[50:70, 90:110] = False
        return abs(obj.mean() - img[m].astype(float).mean())
    assert contrast(preprocess(g, "median3-v1")) > 0.9 * contrast(g)


def test_an_unknown_name_is_a_no_op_not_a_crash():
    """A typo in a config must degrade to unfiltered inference rather than take
    down a survey."""
    g = seabed()
    assert np.array_equal(preprocess(g, "no-such-filter"), g)
    assert preprocess(None, "median3-v1") is None


def test_names_are_a_wire_format():
    """They are recorded in payload provenance, so a stored detection can say
    how its frame was processed. Renaming one orphans that record."""
    assert "none" in PREPROCESSORS and "median3-v1" in PREPROCESSORS


def test_provenance_reports_the_active_filter():
    assert Settings().provenance()["preprocessing_version"] == "none"
    assert Settings(preprocessing="median3-v1").provenance()["preprocessing_version"] == "median3-v1"
