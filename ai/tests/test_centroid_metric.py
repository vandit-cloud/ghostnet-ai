"""Centroid detection rate, rule C: cluster into nets, then match one-to-one.

The cases that matter here are the disagreements between rules, not the
arithmetic. Each of the two worked examples below scores differently under the
strict and lenient rules, so if someone later swaps the matcher out, these fail
rather than quietly changing what the project means by "we found the net".
"""

from __future__ import annotations

import sys
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT / "scripts"))

from centroid_metric import (  # noqa: E402
    Shape,
    cluster_shapes,
    match_centroids,
    polygon_centroid,
)

TOL = 0.10


def at(x, y, r=0.005):
    """A small square centred on (x, y) -- a stand-in for one bead chain."""
    return Shape(points=[(x - r, y - r), (x + r, y - r), (x + r, y + r), (x - r, y + r)])


# --- centroids ------------------------------------------------------------

def test_square_centroid_is_its_centre():
    cx, cy = polygon_centroid([(0, 0), (1, 0), (1, 1), (0, 1)])
    assert abs(cx - 0.5) < 1e-9 and abs(cy - 0.5) < 1e-9


def test_degenerate_strip_falls_back_instead_of_exploding():
    """A net traced down its middle is nearly zero-area; the shoelace formula
    divides by that area. The fallback must give a finite point on the strip."""
    strip = [(0.1, 0.5), (0.9, 0.5), (0.9, 0.5), (0.1, 0.5)]
    cx, cy = polygon_centroid(strip)
    assert 0.1 <= cx <= 0.9 and abs(cy - 0.5) < 1e-9


def test_two_point_shape_does_not_crash():
    cx, cy = polygon_centroid([(0.0, 0.0), (1.0, 1.0)])
    assert (cx, cy) == (0.5, 0.5)


# --- clustering -----------------------------------------------------------

def test_single_linkage_chains_a_long_net_into_one_object():
    """Endpoints 0.24 apart, far beyond the 0.10 tolerance, but each link is
    within it. A net IS a chain, so this must be ONE net, not three."""
    chain = [at(0.10, 0.5), at(0.18, 0.5), at(0.26, 0.5), at(0.34, 0.5)]
    assert len(cluster_shapes(chain, TOL)) == 1


def test_well_separated_nets_stay_separate():
    assert len(cluster_shapes([at(0.1, 0.1), at(0.9, 0.9)], TOL)) == 2


def test_empty_input_clusters_to_nothing():
    assert cluster_shapes([], TOL) == []


# --- the worked examples --------------------------------------------------

def test_one_net_traced_as_three_found_by_one_blob():
    """Rule C: 1 of 1 net. (Strict would say 1 of 3 and punish the annotator's
    choice of where to break the chain.)"""
    truth = [at(0.30, 0.5), at(0.36, 0.5), at(0.42, 0.5)]
    preds = [at(0.36, 0.5)]
    assert match_centroids(truth, preds, TOL) == (1, 0, 0)


def test_one_net_predicted_as_five_fragments_is_not_four_false_alarms():
    """Rule C: 1 hit, 0 false alarms. (Strict would charge 4 false alarms for a
    fragmentation that costs the operator nothing.)"""
    truth = [at(0.50, 0.5)]
    preds = [at(0.46, 0.5), at(0.50, 0.5), at(0.54, 0.5), at(0.58, 0.5), at(0.62, 0.5)]
    assert match_centroids(truth, preds, TOL) == (1, 0, 0)


def test_a_spurious_net_elsewhere_is_charged_once():
    """The lenient rule cannot express this at all -- and it is the cost that
    lands on a human review queue, so it has to be countable."""
    truth = [at(0.20, 0.2)]
    preds = [at(0.20, 0.2), at(0.80, 0.8), at(0.86, 0.8)]
    assert match_centroids(truth, preds, TOL) == (1, 0, 1)


def test_missed_net_is_a_miss_not_a_silent_drop():
    assert match_centroids([at(0.2, 0.2), at(0.8, 0.8)], [at(0.2, 0.2)], TOL) == (1, 1, 0)


def test_no_predictions_misses_everything():
    assert match_centroids([at(0.2, 0.2), at(0.8, 0.8)], [], TOL) == (0, 2, 0)


def test_no_truth_makes_every_predicted_net_a_false_alarm():
    assert match_centroids([], [at(0.2, 0.2), at(0.8, 0.8)], TOL) == (0, 0, 2)


# --- invariants -----------------------------------------------------------

def test_hits_plus_misses_equals_truth_nets():
    """The denominator must be the cluster count, or the rate is not a rate."""
    truth = [at(0.10, 0.1), at(0.16, 0.1), at(0.80, 0.8)]
    preds = [at(0.12, 0.1)]
    hits, misses, _ = match_centroids(truth, preds, TOL)
    assert hits + misses == len(cluster_shapes(truth, TOL)) == 2


def test_matching_is_one_to_one_so_one_net_cannot_claim_two():
    """Two distinct truth nets, one prediction between them: exactly one hit."""
    truth = [at(0.40, 0.5), at(0.56, 0.5)]
    preds = [at(0.48, 0.5)]
    hits, misses, false_alarms = match_centroids(truth, preds, TOL)
    assert (hits, misses, false_alarms) == (1, 1, 0)


def test_result_does_not_depend_on_input_order():
    truth = [at(0.10, 0.1), at(0.50, 0.5), at(0.80, 0.8)]
    preds = [at(0.12, 0.1), at(0.82, 0.8)]
    assert match_centroids(truth, preds, TOL) == \
        match_centroids(list(reversed(truth)), list(reversed(preds)), TOL)


# --- aspect correction ----------------------------------------------------

def test_aspect_correction_makes_vertical_and_horizontal_distance_agree():
    """On a 3:1 chip, 0.1 in y is a third of the pixel distance that 0.1 in x
    is. After correction the same separation in either axis gives the same
    distance, so the tolerance is a circle rather than an ellipse."""
    from centroid_metric import aspect_correct, distance

    aspect = 112 / 331  # the real 3:1 chip in the test split
    horizontal = aspect_correct([(0.0, 0.5), (0.3, 0.5)], aspect)
    vertical = aspect_correct([(0.5, 0.0), (0.5, 0.3)], aspect)

    # 0.3 of the width is 3x the pixel span of 0.3 of the height on this chip
    assert abs(distance(*horizontal) - 0.3) < 1e-9
    assert abs(distance(*vertical) - 0.3 * aspect) < 1e-9


def test_square_chip_is_unchanged_by_correction():
    from centroid_metric import aspect_correct

    pts = [(0.1, 0.2), (0.3, 0.4)]
    assert aspect_correct(pts, 1.0) == pts
