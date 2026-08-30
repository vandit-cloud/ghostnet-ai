"""Tests for temperature fitting and the calibration policy it feeds.

Calibration is the one number in this project a reviewer can feel directly: a
detection labelled 90% that turns out to be a rock is a broken promise, not a
rounding error. The fit is small enough to verify exactly, so it is.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

from ghostnet import decision  # noqa: E402
from ghostnet.config import Settings  # noqa: E402

SCRIPT = AI_ROOT / "scripts" / "fit_calibration.py"


@pytest.fixture(scope="module")
def cal():
    spec = importlib.util.spec_from_file_location("fit_calibration", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


# --- geometry --------------------------------------------------------------

def test_iou_basics(cal):
    assert cal.iou((0, 0, 10, 10), (0, 0, 10, 10)) == pytest.approx(1.0)
    assert cal.iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0
    # half-overlap: intersection 50, union 150
    assert cal.iou((0, 0, 10, 10), (5, 0, 15, 10)) == pytest.approx(50 / 150)


def test_matching_is_greedy_by_score_and_one_to_one(cal):
    """Two predictions on one object: the confident one is correct, the other
    is a duplicate. Letting both claim it would reward duplicates, which a
    calibrated score should discourage."""
    gts = [(0, 0, 0, 10, 10)]
    preds = [
        (0.9, 0, (0, 0, 10, 10)),
        (0.6, 0, (1, 1, 11, 11)),
    ]
    assert cal.match(preds, gts, 0.5) == [1, 0]


def test_class_mismatch_is_not_a_match(cal):
    gts = [(1, 0, 0, 10, 10)]
    preds = [(0.9, 0, (0, 0, 10, 10))]
    assert cal.match(preds, gts, 0.5) == [0]


def test_prediction_on_empty_background_is_a_false_positive(cal):
    """The case the whole hard-negative strategy exists to reduce."""
    assert cal.match([(0.8, 0, (0, 0, 10, 10))], [], 0.5) == [0]


# --- the fit ---------------------------------------------------------------

def test_recovers_a_known_temperature(cal):
    """Generate scores that ARE calibrated at some T, and check the fit finds
    it. Without this, a plausible-looking T could be silently wrong."""
    rng = np.random.default_rng(0)
    true_t = 2.0
    logits = rng.normal(0, 3, 40000)
    true_p = 1 / (1 + np.exp(-logits / true_t))
    labels = (rng.random(40000) < true_p).astype(float)
    scores = 1 / (1 + np.exp(-logits))          # the overconfident raw score
    assert cal.fit_temperature(scores, labels) == pytest.approx(true_t, rel=0.10)


def test_already_calibrated_scores_yield_temperature_near_one(cal):
    rng = np.random.default_rng(1)
    scores = rng.random(40000)
    labels = (rng.random(40000) < scores).astype(float)
    assert cal.fit_temperature(scores, labels) == pytest.approx(1.0, abs=0.15)


def test_fit_reduces_expected_calibration_error(cal):
    rng = np.random.default_rng(2)
    logits = rng.normal(0, 3, 20000)
    labels = (rng.random(20000) < 1 / (1 + np.exp(-logits / 2.5))).astype(float)
    scores = 1 / (1 + np.exp(-logits))
    t = cal.fit_temperature(scores, labels)
    z = np.log(scores / (1 - scores)) / t
    assert cal.ece(1 / (1 + np.exp(-z)), labels) < cal.ece(scores, labels)


def test_ece_is_zero_for_a_perfectly_calibrated_set(cal):
    scores = np.repeat([0.05, 0.25, 0.55, 0.85], 5000)
    rng = np.random.default_rng(3)
    labels = (rng.random(scores.size) < scores).astype(float)
    assert cal.ece(scores, labels) < 0.02


# --- the effect on what gets reported --------------------------------------

def test_temperature_is_monotonic_so_ranking_never_changes(cal):
    """Temperature scaling must not touch mAP. If it reordered detections, a
    calibration step would silently change the detector's behaviour."""
    s = np.array([0.1, 0.3, 0.5, 0.7, 0.9])
    z = np.log(s / (1 - s)) / 2.7
    out = 1 / (1 + np.exp(-z))
    assert list(out) == sorted(out)


def test_written_file_lifts_the_low_uncertainty_cap(cal, tmp_path, monkeypatch):
    """End to end: the fitted file is what allows the pipeline to claim 'low'.
    Before it exists the cap is correct and deliberate."""
    monkeypatch.setattr(decision, "_TEMPERATURE", 1.0)
    monkeypatch.setattr(decision, "_CALIBRATION_LOADED", True)
    settings = Settings(models_dir=tmp_path)
    assert decision.assess_uncertainty(0.99, settings) == "medium"

    (tmp_path / "calibrator").mkdir()
    (tmp_path / "calibrator" / "temperature.json").write_text(json.dumps({"temperature": 1.4}))
    monkeypatch.setattr(decision, "_CALIBRATION_LOADED", False)
    assert decision.load_calibration(settings) == pytest.approx(1.4)
    assert decision.assess_uncertainty(0.99, settings) == "low"


def test_a_corrupt_calibration_file_falls_back_to_uncalibrated(cal, tmp_path, monkeypatch):
    """Never crash inference over a bad calibrator, and never silently trust
    one either -- T = 1.0 means the honesty cap stays on."""
    monkeypatch.setattr(decision, "_CALIBRATION_LOADED", False)
    monkeypatch.setattr(decision, "_TEMPERATURE", 1.0)
    settings = Settings(models_dir=tmp_path)
    (tmp_path / "calibrator").mkdir()
    (tmp_path / "calibrator" / "temperature.json").write_text("{ not json")
    assert decision.load_calibration(settings) == 1.0
    assert decision.assess_uncertainty(0.99, settings) == "medium"


# --- the calibrator must belong to the model using it ----------------------

def test_calibration_fitted_for_other_weights_is_flagged(cal, tmp_path, monkeypatch):
    """A temperature is a property of one trained model. After a retrain the old
    file still loads and still looks fine, silently applying the wrong
    correction -- worse than no calibration, because the numbers look
    authoritative."""
    monkeypatch.setattr(decision, "_CALIBRATION_LOADED", False)
    monkeypatch.setattr(decision, "_TEMPERATURE", 1.0)
    monkeypatch.setattr(decision, "_CALIBRATION_WEIGHTS", None)
    (tmp_path / "calibrator").mkdir()
    (tmp_path / "calibrator" / "temperature.json").write_text(
        json.dumps({"temperature": 1.3, "weights": str(tmp_path / "run_a" / "best.pt")})
    )
    settings = Settings(models_dir=tmp_path, weights_path=tmp_path / "run_b" / "best.pt")
    warning = decision.calibration_mismatch(settings)
    assert warning is not None and "may be miscalibrated" in warning


def test_matching_weights_produce_no_warning(cal, tmp_path, monkeypatch):
    monkeypatch.setattr(decision, "_CALIBRATION_LOADED", False)
    monkeypatch.setattr(decision, "_TEMPERATURE", 1.0)
    monkeypatch.setattr(decision, "_CALIBRATION_WEIGHTS", None)
    weights = tmp_path / "run_a" / "best.pt"
    (tmp_path / "calibrator").mkdir()
    (tmp_path / "calibrator" / "temperature.json").write_text(
        json.dumps({"temperature": 1.3, "weights": str(weights)})
    )
    settings = Settings(models_dir=tmp_path, weights_path=weights)
    assert decision.calibration_mismatch(settings) is None


def test_no_calibrator_is_not_a_mismatch(cal, tmp_path, monkeypatch):
    """Uncalibrated is a valid, honest state -- not an error to warn about."""
    monkeypatch.setattr(decision, "_CALIBRATION_LOADED", False)
    monkeypatch.setattr(decision, "_TEMPERATURE", 1.0)
    monkeypatch.setattr(decision, "_CALIBRATION_WEIGHTS", None)
    settings = Settings(models_dir=tmp_path, weights_path=tmp_path / "run.pt")
    assert decision.calibration_mismatch(settings) is None
