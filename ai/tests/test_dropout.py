"""Dropout-detection tests (problem statement requirement 6).

The corpus contains almost no dropouts -- 2 frames in 500, both padding -- so
these build the failure cases rather than looking for them, and separately
assert that ordinary sonar is left alone.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

from ghostnet.dropout import (  # noqa: E402
    dropout_context, dropout_overlap, frame_dropout_note, invalid_row_mask,
)

rng = np.random.default_rng(0)


def seabed(h: int = 100, w: int = 200) -> np.ndarray:
    """Textured sonar-like seabed: real returns always have spread."""
    return np.clip(rng.normal(120, 25, (h, w)), 0, 255).astype(np.uint8)


def test_ordinary_seabed_is_never_flagged():
    for _ in range(20):
        assert not invalid_row_mask(seabed()).any()


def test_dead_black_rows_are_found():
    g = seabed()
    g[40:50, :] = 0
    mask = invalid_row_mask(g)
    assert mask.sum() == 10
    assert mask[40:50].all()


def test_saturated_white_rows_are_found():
    """A blown-out ping is as informationless as a black one."""
    g = seabed()
    g[10:15, :] = 255
    assert invalid_row_mask(g)[10:15].all()


def test_flat_grey_rows_are_found():
    """Constant at ANY level means no return, not just black or white."""
    g = seabed()
    g[60:64, :] = 130
    assert invalid_row_mask(g)[60:64].all()


def test_acoustic_shadow_is_not_a_dropout():
    """A shadow is dark but LOCAL. Flagging it would gut the strongest cue in
    side-scan interpretation."""
    g = seabed()
    g[30:70, 80:120] = 12          # a dark patch spanning many rows, part-width
    assert not invalid_row_mask(g).any()


def test_overlap_is_measured_over_the_detection_rows_only():
    g = seabed()
    g[50:60, :] = 0
    assert dropout_overlap(g, [0, 50, 20, 10]) == 1.0     # wholly inside
    assert dropout_overlap(g, [0, 0, 20, 10]) == 0.0      # wholly outside
    assert dropout_overlap(g, [0, 45, 20, 10]) == 0.5     # half in


def test_context_escalates_wording_with_overlap():
    g = seabed()
    g[50:60, :] = 0
    assert dropout_context(g, [0, 0, 20, 10]).startswith("clear")
    assert dropout_context(g, [0, 42, 20, 10]).startswith("partial")
    assert dropout_context(g, [0, 50, 20, 10]).startswith("UNRELIABLE")


def test_frame_note_is_none_for_a_clean_frame():
    assert frame_dropout_note(seabed()) is None


def test_frame_note_separates_edge_padding_from_interior_loss():
    """Both are 'not real data', but an operator reads them differently: edge
    padding is a tiling artefact, an interior hole is a sonar problem."""
    edge = seabed()
    edge[-8:, :] = 0
    assert "at the frame edge" in frame_dropout_note(edge)

    interior = seabed()
    interior[40:50, :] = 0
    assert "interior" in frame_dropout_note(interior)


def test_the_two_real_cases_in_the_corpus_are_caught():
    """Regression guard on the only genuine examples available."""
    import cv2

    for name, expect_rows in (
        ("AI4SHIPWRECKS__Haltiner_Barge_03__x480_y0.png", 19),
        ("SUBPIPE__SSS_HF_images_1693573389.819__x1500_y0.png", 280),
    ):
        p = AI_ROOT / "data" / "processed" / "test" / "images" / name
        if not p.exists():
            continue          # dataset is gitignored; skip on a fresh clone
        g = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        assert int(invalid_row_mask(g).sum()) == expect_rows, name
