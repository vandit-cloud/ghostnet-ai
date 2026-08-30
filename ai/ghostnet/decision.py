"""Confidence calibration and the report/suppress decision policy.

Two separable concerns live here on purpose:

  1. CALIBRATION -- mechanical. A raw YOLO score is not a probability; it is
     systematically overconfident. Temperature scaling fits a single scalar T
     on the validation set and divides the logit by it. Nothing to decide.

  2. POLICY -- a judgement call. Given a calibrated probability, do we report
     this detection at all, and how much confidence do we claim? That depends
     on what it costs to be wrong in each direction, which is a domain
     question, not a machine-learning one.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from .config import SETTINGS, Settings
from .contract import CLASS_VALUES

# Fitted on the validation set by scripts/fit_calibration.py once a model
# exists. T == 1.0 means "uncalibrated", i.e. raw scores pass through.
_TEMPERATURE: float = 1.0
_CALIBRATION_LOADED = False


def load_calibration(settings: Settings = SETTINGS) -> float:
    """Read the fitted temperature from models/calibrator/temperature.json."""
    global _TEMPERATURE, _CALIBRATION_LOADED
    if _CALIBRATION_LOADED:
        return _TEMPERATURE
    path = Path(settings.models_dir) / "calibrator" / "temperature.json"
    if path.exists():
        try:
            _TEMPERATURE = float(json.loads(path.read_text())["temperature"])
        except Exception:
            _TEMPERATURE = 1.0
    _CALIBRATION_LOADED = True
    return _TEMPERATURE


def calibrate(raw_score: float, settings: Settings = SETTINGS) -> float:
    """Temperature-scale a raw score into a better-behaved probability.

    Invert the sigmoid to recover the logit, divide by T, re-apply the sigmoid.
    T > 1 softens overconfident scores; T == 1 is a no-op.
    """
    t = load_calibration(settings)
    if t == 1.0:
        return raw_score
    p = min(max(raw_score, 1e-6), 1 - 1e-6)
    logit = math.log(p / (1 - p))
    return 1.0 / (1.0 + math.exp(-logit / t))


def normalise_class(model_class: str) -> str:
    """Map a training-time class name onto the closed contract vocabulary."""
    name = model_class.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "ghostnet": "ghost_net",
        "net": "ghost_net",
        "fishing_net": "ghost_net",
        "seafloor": "natural",
        "seabed": "natural",
        "rock": "natural",
        "background": "natural",
    }
    name = aliases.get(name, name)
    return name if name in CLASS_VALUES else "unknown"


# ---------------------------------------------------------------------------
# The reporting policy.
# ---------------------------------------------------------------------------

# Classes that describe a man-made object. These are actionable: someone may
# put a boat in the water because of them. 'unknown' is included deliberately
# -- an anomaly the model cannot name is exactly what a reviewer should see.
ARTIFICIAL_CLASSES = frozenset({"ghost_net", "debris", "unknown"})


def is_calibrated(settings: Settings = SETTINGS) -> bool:
    """True once a temperature has actually been fitted on a validation set.

    T == 1.0 is the sentinel for 'never fitted', so raw scores are passing
    through untouched and are known to be overconfident.
    """
    return load_calibration(settings) != 1.0


def assess_uncertainty(confidence: float, settings: Settings = SETTINGS) -> str:
    """Bucket a calibrated confidence into the contract's three bands.

    The cap below is the important part. Before calibration is fitted, the
    number being bucketed is a ranking score wearing a probability's clothes.
    Claiming 'low uncertainty' from it would be a confident statement derived
    from an admittedly untrustworthy input -- precisely the overconfidence the
    honesty rules (§25, B4, E16) exist to prevent. So while uncalibrated, the
    best band available is 'medium', no matter how high the score.
    """
    if confidence >= settings.uncertainty_low_edge:
        band = "low"
    elif confidence >= settings.uncertainty_medium_edge:
        band = "medium"
    else:
        band = "high"

    if band == "low" and not is_calibrated(settings):
        return "medium"
    return band


def escalate_uncertainty(current: str) -> str:
    """Widen an uncertainty band by one step.

    Used by the caller for detections landing in acoustically degraded regions
    (the water column), where the class score itself is less trustworthy --
    not merely the position.
    """
    return {"low": "medium", "medium": "high", "high": "high"}[current]


def apply_decision_policy(
    model_class: str,
    raw_score: float,
    settings: Settings = SETTINGS,
) -> tuple[str, float, str] | None:
    """Decide whether and how to report one detection.

    Args:
        model_class: raw class name from the detector.
        raw_score:   raw detector score, 0..1, uncalibrated.
        settings:    runtime settings carrying the floors and band edges.

    Returns:
        (contract_class, calibrated_confidence, uncertainty) to report it, or
        None to suppress it so it never reaches the reviewer.

    Policy, and the reasoning behind each choice:

    1. 'natural' is REPORTED, not discarded. The model asserting "that is a
       rock" is the evidence that the artificial-vs-natural separation works,
       which is both the PS's own wording and the headline metric that replaced
       the unmeasurable ghost-net F1 (gap #4). Throwing it away would delete the
       proof of the thing being claimed. Member 2 filters by `class` for the
       default map view; the data still exists behind that filter.

    2. The floors are ASYMMETRIC. A missed ghost net keeps fishing for years,
       so artificial classes clear a low bar (0.20). A low-confidence 'natural'
       is neither actionable nor evidential, so it clears a higher one (0.45).
       This buys back most of the reviewer-fatigue cost of choice 1 without
       touching the artificial recall that actually matters.

    3. Suppression happens on CALIBRATED confidence, after temperature scaling,
       so the floor keeps a fixed meaning as the model changes. A floor on raw
       scores would silently drift every time the detector is retrained.
    """
    cls = normalise_class(model_class)
    confidence = calibrate(raw_score, settings)

    floor = (
        settings.review_floor_artificial
        if cls in ARTIFICIAL_CLASSES
        else settings.review_floor_natural
    )
    if confidence < floor:
        return None

    return cls, confidence, assess_uncertainty(confidence, settings)
