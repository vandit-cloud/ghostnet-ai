"""detect() must not raise. These are the tests for that promise.

docs/HANDOFF.md tells Member 2, in as many words, "You do not need try/except
around it" -- so every way a caller can hand this package something unusable
has to come back as a payload with warnings, not an exception. A raise here is
a 500 in their API, and the failure arrives during integration week when it is
most expensive.

The cases below are not hypothetical. Survey metadata is a hand-filled JSON
sidecar today and will be a form or a database row later, and all three produce
"" and "n/a" where a number was expected. The old guard tested `is not None`,
which every one of those values passes.

The geometry helpers are exercised directly rather than through detect(),
because detect() returns early when no weights are present -- so a
model-shaped test would never reach the metadata path at all on a machine
without the .pt file.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

from ghostnet import infer  # noqa: E402
from ghostnet.config import Settings  # noqa: E402
from ghostnet.contract import validate  # noqa: E402

GOOD = {
    "nadir_col": 500,
    "range_resolution_m": 0.05,
    "altitude_m": 3.0,
    "heading_deg": 0.0,
    "latitude": 18.922,
    "longitude": 72.8347,
}

REQUIRED = ("nadir_col", "range_resolution_m", "altitude_m", "heading_deg")


# --- reading numbers off unvalidated metadata ------------------------------

@pytest.mark.parametrize("bad", ["", "n/a", "north", "unknown", [], {}, "12.3.4"])
@pytest.mark.parametrize("key", REQUIRED)
def test_an_unreadable_required_field_yields_no_geometry_rather_than_an_exception(key, bad):
    """The whole point: a present-but-unusable value is treated exactly like a
    missing one, because there is nothing else honest to do with it."""
    assert infer._geometry_from_meta({**GOOD, key: bad}) is None


def test_numeric_strings_are_accepted_because_json_and_forms_produce_them():
    """Rejecting "0.05" would break the realistic case while fixing the broken
    one -- a sidecar written by hand, or any HTML form, sends numbers as text."""
    geom = infer._geometry_from_meta({k: str(v) for k, v in GOOD.items()})
    assert geom is not None
    assert geom.range_resolution_m == pytest.approx(0.05)
    assert geom.nadir_col == pytest.approx(500.0)


def test_a_malformed_optional_field_falls_back_to_its_default():
    """layback_m is optional, so an unreadable one means 'no layback known',
    not 'no position'. Losing the whole frame over an optional field would be
    the overcorrection."""
    geom = infer._geometry_from_meta({**GOOD, "layback_m": "", "along_track_res_m": "n/a"})
    assert geom is not None
    assert geom.layback_m == 0.0
    assert geom.along_track_res_m is None


def test_malformed_keys_are_named_so_the_warning_can_be_acted_on():
    """'incomplete sonar geometry' sends someone hunting for a missing field.
    A heading that arrived as "north" needs a different fix, and the payload is
    the only place that difference is visible."""
    bad = infer.malformed_meta_keys({**GOOD, "heading_deg": "north", "nadir_col": ""})
    assert set(bad) == {"heading_deg", "nadir_col"}


def test_absent_keys_are_not_reported_as_malformed():
    """Missing metadata is the normal case for a survey with no nav data. It
    must not be dressed up as an error."""
    assert infer.malformed_meta_keys({}) == []
    assert infer.malformed_meta_keys({"heading_deg": None}) == []


def test_every_numeric_key_the_package_reads_is_covered_by_the_check():
    """A guard against the next field: anything read with _num must appear in
    NUMERIC_META_KEYS, or it can raise again without a test noticing."""
    for key in REQUIRED + ("layback_m", "along_track_res_m", "latitude",
                           "longitude", "nadir_row"):
        assert key in infer.NUMERIC_META_KEYS


# --- weights that exist but will not load ----------------------------------

@pytest.fixture
def no_cached_model(monkeypatch):
    """load_model caches globally; these tests each need a cold load."""
    monkeypatch.setattr(infer, "_MODEL", None)
    monkeypatch.setattr(infer, "_MODEL_ERROR", None)


def test_a_corrupt_checkpoint_does_not_take_down_warmup(no_cached_model, tmp_path):
    """warmup() is called from Member 2's FastAPI lifespan handler. A raise
    here is not a degraded response, it is an API that will not start."""
    junk = tmp_path / "ghostnet.pt"
    junk.write_bytes(b"not a checkpoint")
    settings = Settings(weights_path=junk)

    assert infer.warmup(settings) is False
    assert infer._MODEL_ERROR is not None
    assert "could not be loaded" in infer._MODEL_ERROR


def test_a_corrupt_checkpoint_still_returns_a_valid_payload(no_cached_model, tmp_path):
    junk = tmp_path / "ghostnet.pt"
    junk.write_bytes(b"not a checkpoint")
    image = tmp_path / "frame.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)

    payload = infer.detect(image, GOOD, Settings(weights_path=junk))

    assert validate(payload) == []
    assert payload["detections"] == []
    assert any("could not be loaded" in w for w in payload["warnings"])


def test_broken_weights_are_distinguished_from_no_weights(no_cached_model, tmp_path):
    """"Set GHOSTNET_WEIGHTS" is useless advice when the variable is already
    set and the file it points at is broken."""
    image = tmp_path / "frame.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")

    absent = infer.detect(image, GOOD, Settings(weights_path=tmp_path / "nope.pt"))
    assert any("no trained weights available" in w for w in absent["warnings"])

    junk = tmp_path / "ghostnet.pt"
    junk.write_bytes(b"not a checkpoint")
    broken = infer.detect(image, GOOD, Settings(weights_path=junk))
    assert not any("no trained weights available" in w for w in broken["warnings"])


def test_a_missing_image_is_reported_not_raised(no_cached_model, tmp_path):
    payload = infer.detect(tmp_path / "absent.png", GOOD, Settings(weights_path=None))
    assert validate(payload) == []
    assert any("image not found" in w for w in payload["warnings"])
