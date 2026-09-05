"""The two guards that must hold before a gv7 run starts.

Both cover accidents that have already happened on this project, and both fail
silently in production rather than raising -- which is why they get tests
rather than a note in a runbook.

P1  fit_calibration.py wrote temperature.json to a hardcoded path while the
    READER honoured GHOSTNET_MODELS_DIR. Fitting calibration for an experiment
    therefore overwrote the SHIPPED model's temperature. In gv6 this paired
    gv5's weights with gv6's temperature and had to be reverted by hand.
    Required by EXPERIMENT_GV7_PLAN.md 1.1.

P2  The test split is the ruler, and a source with no split policy re-draws the
    random pool -- silently changing WHICH boxes are in test. Required by
    EXPERIMENT_GV7_PLAN.md 1.5.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))
sys.path.insert(0, str(AI_ROOT / "scripts"))

from _fingerprint import (  # noqa: E402
    check_test_split,
    fingerprint_dataset,
    fingerprint_split,
)


def _load(name: str):
    path = AI_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_test_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------- P1


def test_calibrator_dir_defaults_to_shipped_location(monkeypatch):
    monkeypatch.delenv("GHOSTNET_MODELS_DIR", raising=False)
    fit = _load("fit_calibration")
    assert fit.calibrator_dir() == AI_ROOT / "models" / "calibrator"


def test_calibrator_dir_honours_models_dir_override(monkeypatch, tmp_path):
    """The whole point of P1: the writer must follow the reader."""
    monkeypatch.setenv("GHOSTNET_MODELS_DIR", str(tmp_path))
    fit = _load("fit_calibration")

    resolved = fit.calibrator_dir()
    assert resolved == tmp_path / "calibrator"

    shipped = AI_ROOT / "models" / "calibrator"
    assert resolved.resolve() != shipped.resolve(), (
        "with GHOSTNET_MODELS_DIR set, fitting must not target the shipped calibrator"
    )


def test_calibrator_dir_is_resolved_at_call_time(monkeypatch, tmp_path):
    """Not captured at import, or an experiment env set later is ignored."""
    monkeypatch.delenv("GHOSTNET_MODELS_DIR", raising=False)
    fit = _load("fit_calibration")
    assert fit.calibrator_dir() == AI_ROOT / "models" / "calibrator"

    monkeypatch.setenv("GHOSTNET_MODELS_DIR", str(tmp_path))
    assert fit.calibrator_dir() == tmp_path / "calibrator"


def test_fit_calibration_exposes_an_out_override():
    fit = _load("fit_calibration")
    parser = [a for a in dir(fit) if a == "main"]
    assert parser, "fit_calibration must still expose main()"
    source = (AI_ROOT / "scripts" / "fit_calibration.py").read_text(encoding="utf-8")
    assert '"--out"' in source, "an explicit --out escape hatch must exist"
    assert "CALIBRATOR = AI_ROOT" not in source, (
        "the hardcoded CALIBRATOR constant is the P1 bug; it must not come back"
    )


# --------------------------------------------------------------- P2


def _make_split(root: Path, split: str, frames: dict[str, str]) -> None:
    (root / split / "images").mkdir(parents=True, exist_ok=True)
    (root / split / "labels").mkdir(parents=True, exist_ok=True)
    for stem, label in frames.items():
        (root / split / "images" / f"{stem}.png").write_bytes(b"\x89PNG fake")
        (root / split / "labels" / f"{stem}.txt").write_text(label, encoding="utf-8")


def test_fingerprint_is_stable_for_identical_input(tmp_path):
    for name in ("a", "b"):
        _make_split(tmp_path / name, "test", {"f1": "0 0.5 0.5 0.1 0.1\n", "f2": ""})
    first = fingerprint_split(tmp_path / "a", "test")
    second = fingerprint_split(tmp_path / "b", "test")
    assert first == second


def test_added_frame_changes_the_image_list_digest(tmp_path):
    _make_split(tmp_path, "test", {"f1": "0 0.5 0.5 0.1 0.1\n"})
    before = fingerprint_split(tmp_path, "test")

    _make_split(tmp_path, "test", {"f2": "0 0.2 0.2 0.1 0.1\n"})
    after = fingerprint_split(tmp_path, "test")

    assert before["image_list"] != after["image_list"], (
        "this is the split-perturbation failure: PLANE-HAND moved wreck 836 -> 837"
    )
    assert after["n_images"] == 2


def test_reannotation_changes_only_the_label_digest(tmp_path):
    """A label audit keeps the frames and moves the boxes. Catch that separately."""
    _make_split(tmp_path, "test", {"f1": "0 0.5 0.5 0.1 0.1\n"})
    before = fingerprint_split(tmp_path, "test")

    (tmp_path / "test" / "labels" / "f1.txt").write_text(
        "0 0.4 0.4 0.2 0.2\n", encoding="utf-8")
    after = fingerprint_split(tmp_path, "test")

    assert before["image_list"] == after["image_list"]
    assert before["label_content"] != after["label_content"]


def test_moving_a_box_between_frames_is_detected(tmp_path):
    """Concatenating label bodies alone would miss this; the name is in the digest."""
    _make_split(tmp_path, "test", {"f1": "0 0.5 0.5 0.1 0.1\n", "f2": ""})
    before = fingerprint_split(tmp_path, "test")

    (tmp_path / "test" / "labels" / "f1.txt").write_text("", encoding="utf-8")
    (tmp_path / "test" / "labels" / "f2.txt").write_text(
        "0 0.5 0.5 0.1 0.1\n", encoding="utf-8")
    after = fingerprint_split(tmp_path, "test")

    assert before["label_content"] != after["label_content"]


def test_background_frames_are_counted(tmp_path):
    _make_split(tmp_path, "test", {"f1": "0 0.5 0.5 0.1 0.1\n", "f2": "", "f3": "\n"})
    assert fingerprint_split(tmp_path, "test")["n_background"] == 2


def test_dataset_version_keys_on_test_only(tmp_path):
    """train may grow -- gv6 added 1,364 synthetic frames -- without invalidating."""
    _make_split(tmp_path, "test", {"t1": "0 0.5 0.5 0.1 0.1\n"})
    _make_split(tmp_path, "train", {"a": ""})
    before = fingerprint_dataset(tmp_path)["dataset_version"]

    _make_split(tmp_path, "train", {"b": "", "c": ""})
    after = fingerprint_dataset(tmp_path)["dataset_version"]

    assert before == after, "growing train must not change dataset_version"


def test_check_reports_missing_fingerprints_as_a_problem(tmp_path):
    _make_split(tmp_path, "test", {"f1": ""})
    (tmp_path / "build_report.json").write_text(json.dumps({"sources": []}), encoding="utf-8")

    ok, problems = check_test_split(tmp_path)
    assert not ok
    assert any("no `fingerprints` block" in p for p in problems)


def test_check_passes_then_fails_after_drift(tmp_path):
    _make_split(tmp_path, "test", {"f1": "0 0.5 0.5 0.1 0.1\n"})
    report = {"sources": [], "fingerprints": fingerprint_dataset(tmp_path)}
    (tmp_path / "build_report.json").write_text(json.dumps(report), encoding="utf-8")

    ok, problems = check_test_split(tmp_path)
    assert ok, problems

    _make_split(tmp_path, "test", {"f2": "0 0.1 0.1 0.1 0.1\n"})
    ok, problems = check_test_split(tmp_path)
    assert not ok
    assert any("CHANGED" in p for p in problems)


def test_train_refuses_to_start_on_drift_without_the_flag():
    source = (AI_ROOT / "scripts" / "train.py").read_text(encoding="utf-8")
    assert "check_test_split" in source, "train.py must assert the ruler before training"
    assert "--allow-dataset-drift" in source, "there must be a declared escape hatch"


@pytest.mark.skipif(not (AI_ROOT / "data" / "processed" / "test").is_dir(),
                    reason="real dataset not present")
def test_real_dataset_matches_its_recorded_fingerprint():
    ok, problems = check_test_split(AI_ROOT / "data" / "processed")
    assert ok, "the shipped dataset drifted from its build_report: " + "; ".join(problems)
