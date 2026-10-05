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


_STATE = ("_TEMPERATURE", "_CLASS_PARAMS", "_CALIBRATION_LOADED", "_CALIBRATION_WEIGHTS",
          "_CALIBRATION_ERROR", "_CALIBRATION_SHA256")


@pytest.fixture(autouse=True)
def _restore_calibration_state(monkeypatch):
    """Every test here loads calibrator files into decision's module state.
    Registering each global with monkeypatch means it is put back afterwards,
    so a per-class table loaded from a tmp file cannot leak into the next
    test -- or into test_decision's 'uncalibrated' fixture."""
    for name in _STATE:
        monkeypatch.setattr(decision, name, getattr(decision, name))
    # Start from "no per-class table": the older tests below set only the
    # global T, and were written when that was the whole state.
    decision._CLASS_PARAMS = {}
    decision._CALIBRATION_SHA256 = None


def _write(tmp_path: Path, blob) -> Settings:
    (tmp_path / "calibrator").mkdir(exist_ok=True)
    text = blob if isinstance(blob, str) else json.dumps(blob)
    (tmp_path / "calibrator" / "temperature.json").write_text(text)
    decision._CALIBRATION_LOADED = False
    return Settings(models_dir=tmp_path)


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


def test_a_corrupt_calibration_file_says_so_in_the_payload(cal, tmp_path, monkeypatch):
    """Falling back to raw scores silently is the actual danger.

    'No low uncertainty ever appears' looks identical to a model nobody has
    calibrated yet, so the fallback has to announce itself. The warning rides
    out on the channel infer.py already surfaces.
    """
    monkeypatch.setattr(decision, "_CALIBRATION_LOADED", False)
    monkeypatch.setattr(decision, "_TEMPERATURE", 1.0)
    monkeypatch.setattr(decision, "_CALIBRATION_ERROR", None)
    weights = tmp_path / "ghostnet.pt"
    weights.write_bytes(b"not really weights")
    settings = Settings(models_dir=tmp_path, weights_path=weights)
    (tmp_path / "calibrator").mkdir()
    (tmp_path / "calibrator" / "temperature.json").write_text("{ not json")

    warning = decision.calibration_mismatch(settings)
    assert warning is not None
    assert "could not be read" in warning
    assert "fit_calibration" in warning


def test_a_repaired_calibration_file_is_picked_up_without_a_restart(cal, tmp_path, monkeypatch):
    """A parse failure must not latch. Member 2 runs this inside a long-lived
    API process; requiring a restart to recover from a half-written file turns
    a fixable mistake into an outage."""
    monkeypatch.setattr(decision, "_CALIBRATION_LOADED", False)
    monkeypatch.setattr(decision, "_TEMPERATURE", 1.0)
    monkeypatch.setattr(decision, "_CALIBRATION_ERROR", None)
    settings = Settings(models_dir=tmp_path)
    (tmp_path / "calibrator").mkdir()
    target = tmp_path / "calibrator" / "temperature.json"

    target.write_text("{ truncated")
    assert decision.load_calibration(settings) == 1.0
    assert decision.calibration_mismatch(settings) is not None

    target.write_text(json.dumps({"temperature": 1.75, "fitted_on": "val"}))
    assert decision.load_calibration(settings) == pytest.approx(1.75)
    assert decision.calibration_mismatch(settings) is None


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


# --- per-class calibration (format 2) --------------------------------------

def _logit(p: float) -> float:
    return float(np.log(p / (1 - p)))


def _sig(z: float) -> float:
    return float(1 / (1 + np.exp(-z)))


V2 = {
    "format_version": 2,
    "method": "temperature",
    "temperature": 1.2,
    "classes": {
        "wreck": {"method": "temperature", "temperature": 0.9},
        "ghost_pot": {"method": "platt", "a": 0.8, "b": 0.5},
        "plane": {"fallback": True, "reason": "8 matched positives on val < 30"},
    },
}


def test_each_class_gets_its_own_map(tmp_path):
    settings = _write(tmp_path, V2)
    raw = 0.30
    assert decision.calibrate(raw, settings, model_class="wreck") == pytest.approx(_sig(_logit(raw) / 0.9))
    assert decision.calibrate(raw, settings, model_class="ghost_pot") == pytest.approx(
        _sig(0.8 * _logit(raw) + 0.5))
    # No class given, or a class the file does not list: the global T.
    assert decision.calibrate(raw, settings) == pytest.approx(_sig(_logit(raw) / 1.2))
    assert decision.calibrate(raw, settings, model_class="debris") == pytest.approx(_sig(_logit(raw) / 1.2))
    # The detector may spell a class differently; the key is normalised.
    assert decision.calibrate(raw, settings, model_class="Ghost-Pot") == pytest.approx(
        _sig(0.8 * _logit(raw) + 0.5))


def test_a_fallback_class_uses_the_global_temperature(tmp_path):
    """plane is LISTED, with the reason it has no map -- and must not be
    treated as if the listing were a map."""
    settings = _write(tmp_path, V2)
    assert decision.calibrate(0.4, settings, model_class="plane") == pytest.approx(_sig(_logit(0.4) / 1.2))


def test_the_policy_calibrates_by_detector_class_not_contract_class(tmp_path):
    """wreck and ghost_pot both report as `debris`; their confidences must
    still come from their own maps."""
    settings = _write(tmp_path, V2)
    wreck = decision.apply_decision_policy("wreck", 0.5, settings)
    pot = decision.apply_decision_policy("ghost_pot", 0.5, settings)
    assert wreck[0] == pot[0] == "debris"
    assert wreck[1] == pytest.approx(_sig(0.0 / 0.9))           # logit(0.5) = 0
    assert pot[1] == pytest.approx(_sig(0.5))
    assert wreck[1] != pot[1]


def test_old_single_temperature_file_still_loads(tmp_path):
    """Format 1 has no format_version and no classes: every class, named or
    not, gets the one temperature, exactly as before."""
    settings = _write(tmp_path, {"temperature": 2.722031, "fitted_on": "val", "n_predictions": 1604})
    assert decision.load_calibration(settings) == pytest.approx(2.722031)
    assert decision.calibration_mismatch(settings) is None
    for cls in (None, "wreck", "ghost_pot"):
        assert decision.calibrate(0.10, settings, model_class=cls) == pytest.approx(0.309, abs=1e-3)
    assert decision.is_calibrated(settings)
    assert Settings(models_dir=tmp_path).calibration_version == "T2.7220-val-n1604"


def test_calibration_version_names_the_classes_with_their_own_map(tmp_path):
    _write(tmp_path, {**V2, "fitted_on": "val", "n_predictions": 1239})
    assert Settings(models_dir=tmp_path).calibration_version == "T1.2000+ghost_pot+wreck-val-n1239"


def test_a_per_class_table_alone_counts_as_calibrated(tmp_path):
    settings = _write(tmp_path, {**V2, "temperature": 1.0})
    assert decision.is_calibrated(settings)
    assert decision.assess_uncertainty(0.99, settings) == "low"


@pytest.mark.parametrize("bad", [
    {**V2, "format_version": 3},                                           # from the future
    {**V2, "classes": {"wreck": {"method": "isotonic"}}},                  # unknown method
    {**V2, "classes": {"wreck": {"method": "platt", "a": -1.0, "b": 0}}},  # inverts ranking
    {**V2, "classes": {"wreck": {"method": "temperature", "temperature": 0}}},
])
def test_a_calibrator_this_code_cannot_apply_is_refused_whole(tmp_path, bad):
    """All-or-nothing, and loud: scores go raw, the cap goes on, and the
    payload says why. Half-applying a file would leave some classes raw and
    others calibrated on one map with nothing saying which."""
    weights = tmp_path / "w.pt"
    weights.write_bytes(b"w")
    settings = _write(tmp_path, bad)
    settings = Settings(models_dir=tmp_path, weights_path=weights)
    assert decision.load_calibration(settings) == 1.0
    assert decision._CLASS_PARAMS == {}
    assert decision.calibrate(0.3, settings, model_class="ghost_pot") == pytest.approx(0.3)
    assert decision.assess_uncertainty(0.99, settings) == "medium"
    assert "could not be read" in decision.calibration_mismatch(settings)


def test_recorded_digest_catches_different_weights_at_the_same_path(tmp_path):
    """The path check alone passes here -- same file name, same location --
    but the bytes are a different model. Only the recorded digest knows."""
    weights = tmp_path / "ghostnet.pt"
    weights.write_bytes(b"model A")
    import hashlib
    digest_a = hashlib.sha256(b"model A").hexdigest()
    _write(tmp_path, {**V2, "weights": str(weights), "weights_sha256": digest_a})
    settings = Settings(models_dir=tmp_path, weights_path=weights)
    assert decision.calibration_mismatch(settings) is None

    weights.write_bytes(b"model B, retrained")
    decision._CALIBRATION_LOADED = False
    warning = decision.calibration_mismatch(settings)
    assert warning is not None and "may be miscalibrated" in warning


def test_recorded_digest_accepts_the_same_weights_at_another_path(tmp_path):
    """Fitted on another machine: the recorded path does not exist here, but
    the content is identical, so there is nothing to warn about."""
    weights = tmp_path / "deployed" / "ghostnet.pt"
    weights.parent.mkdir()
    weights.write_bytes(b"model A")
    import hashlib
    _write(tmp_path, {**V2, "weights": "E:/elsewhere/best.pt",
                      "weights_sha256": hashlib.sha256(b"model A").hexdigest()})
    settings = Settings(models_dir=tmp_path, weights_path=weights)
    assert decision.calibration_mismatch(settings) is None


# --- fitting per class ------------------------------------------------------

def _synthetic(rng, n, true_t, acc_shift=0.0):
    logits = rng.normal(-1, 2.5, n)
    labels = (rng.random(n) < 1 / (1 + np.exp(-(logits / true_t + acc_shift)))).astype(float)
    return 1 / (1 + np.exp(-logits)), labels


def test_build_calibrator_recovers_a_temperature_per_class(cal):
    rng = np.random.default_rng(4)
    s0, y0 = _synthetic(rng, 20000, 0.8)
    s1, y1 = _synthetic(rng, 20000, 2.5)
    s = np.concatenate([s0, s1])
    y = np.concatenate([y0, y1])
    c = np.array([0] * len(s0) + [1] * len(s1))
    out = cal.build_calibrator(s, c, y, ["wreck", "debris"], "temperature", 30)
    assert out["format_version"] == 2
    assert out["classes"]["wreck"]["temperature"] == pytest.approx(0.8, rel=0.1)
    assert out["classes"]["debris"]["temperature"] == pytest.approx(2.5, rel=0.1)
    # And the file it describes is one decision.py can read.
    temperature, classes = decision.parse_calibrator(out)
    assert set(classes) == {"wreck", "debris"}


def test_a_class_with_too_few_positives_falls_back_and_says_why(cal):
    rng = np.random.default_rng(5)
    s0, y0 = _synthetic(rng, 5000, 1.5)
    s = np.concatenate([s0, np.full(40, 0.3)])
    y = np.concatenate([y0, np.array([1.0] * 9 + [0.0] * 31)])
    c = np.array([0] * len(s0) + [1] * 40)
    out = cal.build_calibrator(s, c, y, ["wreck", "plane"], "temperature", 30)
    plane = out["classes"]["plane"]
    assert plane["fallback"] is True
    assert "9 matched positives" in plane["reason"] and "< 30" in plane["reason"]
    assert "global temperature" in plane["reason"]
    assert "temperature" not in plane
    # A fallback class reads back as "use the global T".
    assert decision.calibrator_for(out, "plane") == {"method": "temperature",
                                                     "temperature": out["temperature"]}


def test_a_degenerate_class_falls_back_and_is_kept_out_of_the_global_fit(cal):
    """The ghost_pot case: val boxes correct ~70% of the time at raw ~0.1. No
    temperature can produce that; the fit runs to the search wall. That class
    must not get its wall-T, and must not drag the global T toward it either."""
    rng = np.random.default_rng(6)
    s0, y0 = _synthetic(rng, 5000, 1.1)
    pot_s = rng.uniform(0.05, 0.3, 3000)
    pot_y = (rng.random(3000) < 0.7).astype(float)
    s = np.concatenate([s0, pot_s])
    y = np.concatenate([y0, pot_y])
    c = np.array([0] * len(s0) + [1] * len(pot_s))
    out = cal.build_calibrator(s, c, y, ["wreck", "ghost_pot"], "temperature", 30)
    pot = out["classes"]["ghost_pot"]
    assert pot["fallback"] is True and "search bound" in pot["reason"]
    assert pot["rejected_fit"]["temperature"] == pytest.approx(cal.T_BOUNDS[1], rel=0.02)
    assert out["global_fitted_on"] == ["wreck"]
    assert out["temperature"] == pytest.approx(1.1, rel=0.15)


def test_platt_recovers_a_known_slope_and_intercept(cal):
    rng = np.random.default_rng(7)
    z = rng.normal(-1, 2.5, 40000)
    y = (rng.random(z.size) < 1 / (1 + np.exp(-(0.6 * z + 0.4)))).astype(float)
    a, b = cal.fit_platt(1 / (1 + np.exp(-z)), y)
    assert a == pytest.approx(0.6, abs=0.05)
    assert b == pytest.approx(0.4, abs=0.08)


def test_shipped_calibrator_is_per_class_and_names_its_weights():
    """The file in the repository is the one the app serves. It must be
    format 2, carry the global T at the top level for older readers, and
    record the weights digest the mismatch check relies on."""
    path = AI_ROOT / "models" / "calibrator" / "temperature.json"
    blob = json.loads(path.read_text())
    assert blob["format_version"] == 2
    assert blob["temperature"] > 0
    assert len(blob["weights_sha256"]) == 64
    temperature, classes = decision.parse_calibrator(blob)
    for name, entry in blob["classes"].items():
        assert entry.get("fallback") or name in classes
        if entry.get("fallback"):
            assert entry["reason"]
