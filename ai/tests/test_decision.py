"""Tests for the reporting policy and the sonar geometry it depends on.

Run:  .venv/Scripts/python -m pytest ai/tests -q
"""

from __future__ import annotations

import math
import sys
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ghostnet import decision  # noqa: E402
from ghostnet.config import Settings  # noqa: E402
from ghostnet.contract import CLASS_VALUES, UNCERTAINTY_VALUES  # noqa: E402
from ghostnet.decision import (  # noqa: E402
    apply_decision_policy,
    assess_uncertainty,
    escalate_uncertainty,
    normalise_class,
)
from ghostnet.geo import (  # noqa: E402
    SonarGeometry,
    geotag_pixel,
    ground_range_from_slant,
    pixel_to_ground_offset,
)


@pytest.fixture
def uncalibrated(monkeypatch):
    """The state the project is actually in today: T == 1.0, never fitted."""
    monkeypatch.setattr(decision, "_TEMPERATURE", 1.0)
    monkeypatch.setattr(decision, "_CALIBRATION_LOADED", True)
    return Settings()


@pytest.fixture
def calibrated(monkeypatch):
    """A model whose temperature has been fitted. T > 1 softens scores."""
    monkeypatch.setattr(decision, "_TEMPERATURE", 1.6)
    monkeypatch.setattr(decision, "_CALIBRATION_LOADED", True)
    return Settings()


# --- the policy's headline claims -----------------------------------------

def test_natural_is_reported_not_discarded(uncalibrated):
    """Claim 1: 'natural' is evidence for the artificial-vs-natural metric."""
    out = apply_decision_policy("natural", 0.80, uncalibrated)
    assert out is not None
    assert out[0] == "natural"


def test_floors_are_asymmetric(uncalibrated):
    """Claim 2: a mid-confidence artificial call survives where natural does not."""
    score = 0.30  # between review_floor_artificial (.20) and _natural (.45)
    assert apply_decision_policy("ghost_net", score, uncalibrated) is not None
    assert apply_decision_policy("natural", score, uncalibrated) is None


def test_unknown_is_treated_as_artificial(uncalibrated):
    """An unnameable anomaly is exactly what a reviewer should see."""
    assert apply_decision_policy("some_novel_thing", 0.25, uncalibrated) is not None


def test_below_artificial_floor_is_suppressed(uncalibrated):
    assert apply_decision_policy("ghost_net", 0.05, uncalibrated) is None


def test_evaluation_can_disable_the_floors(uncalibrated):
    """Metrics must be computable on unfiltered output, or recall is measured
    after the filter that damaged it."""
    eval_settings = replace(uncalibrated, review_floor_artificial=0.0, review_floor_natural=0.0)
    assert apply_decision_policy("ghost_net", 0.01, eval_settings) is not None
    assert apply_decision_policy("natural", 0.01, eval_settings) is not None


# --- the uncertainty cap ---------------------------------------------------

def test_uncalibrated_never_claims_low_uncertainty(uncalibrated):
    """The honesty rule: a 0.99 ranking score is not a 0.99 probability."""
    assert assess_uncertainty(0.99, uncalibrated) == "medium"
    assert apply_decision_policy("ghost_net", 0.99, uncalibrated)[2] == "medium"


def test_calibrated_can_reach_low_uncertainty(calibrated):
    """Once T is fitted the cap lifts -- but T=1.6 softens 0.99 to ~0.97."""
    assert decision.calibrate(0.99, calibrated) < 0.99
    assert assess_uncertainty(0.90, calibrated) == "low"


def test_uncertainty_bands_are_ordered(uncalibrated):
    assert assess_uncertainty(0.10, uncalibrated) == "high"
    assert assess_uncertainty(0.50, uncalibrated) == "medium"


def test_escalation_saturates():
    assert escalate_uncertainty("low") == "medium"
    assert escalate_uncertainty("medium") == "high"
    assert escalate_uncertainty("high") == "high"


# --- contract conformance --------------------------------------------------

@pytest.mark.parametrize("name", ["ghostnet", "fishing_net", "Ghost-Net", "rock", "seabed", "wat"])
def test_policy_output_always_satisfies_the_contract(name, uncalibrated):
    out = apply_decision_policy(name, 0.95, uncalibrated)
    assert out is not None
    cls, conf, unc = out
    assert cls in CLASS_VALUES
    assert unc in UNCERTAINTY_VALUES
    assert 0.0 <= conf <= 1.0


def test_class_aliases_map_onto_the_closed_vocabulary():
    assert normalise_class("Fishing-Net") == "ghost_net"
    assert normalise_class("seafloor") == "natural"
    assert normalise_class("nonsense") == "unknown"


# --- geometry: the gap-#3 fix ---------------------------------------------

def test_slant_to_ground_is_pythagorean():
    assert ground_range_from_slant(20.0, 12.0) == pytest.approx(16.0)


def test_water_column_has_no_solution():
    """Inside the water column any position would be invented."""
    assert ground_range_from_slant(5.0, 12.0) is None


def test_port_and_starboard_sides_are_signed():
    g = SonarGeometry(nadir_col=512, range_resolution_m=0.1, altitude_m=12.0, heading_deg=0.0)
    assert pixel_to_ground_offset(100, g)[1] == -1
    assert pixel_to_ground_offset(900, g)[1] == 1


def test_across_track_is_perpendicular_to_heading():
    """Heading north, starboard target must move east at constant latitude."""
    g = SonarGeometry(nadir_col=512, range_resolution_m=0.1, altitude_m=12.0, heading_deg=0.0)
    lat, lon = geotag_pixel(900, 0, 20.0, 70.0, g)
    assert lat == pytest.approx(20.0, abs=1e-6)
    assert lon > 70.0


def test_ignoring_slant_correction_would_shift_the_fix():
    """Why the fix matters: the naive pixel*resolution answer is metres wrong."""
    g = SonarGeometry(nadir_col=512, range_resolution_m=0.1, altitude_m=12.0, heading_deg=0.0)
    slant_m = 200 * g.range_resolution_m          # naive across-track distance
    ground_m, _ = pixel_to_ground_offset(712, g)  # corrected
    assert slant_m - ground_m > 3.0


def test_nadir_band_position_is_withheld():
    g = SonarGeometry(nadir_col=512, range_resolution_m=0.1, altitude_m=12.0, heading_deg=90.0)
    assert geotag_pixel(520, 0, 20.0, 70.0, g) is None


def test_layback_places_the_fish_astern():
    """Heading north with layback, the fish sits south of the GPS antenna."""
    g = SonarGeometry(
        nadir_col=512, range_resolution_m=0.1, altitude_m=12.0, heading_deg=0.0, layback_m=50.0
    )
    lat, _ = geotag_pixel(900, 0, 20.0, 70.0, g)
    assert lat < 20.0
    assert math.isclose(lat, 20.0, abs_tol=1e-3)
