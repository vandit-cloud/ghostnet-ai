"""The contract's own regression tests.

These exist to catch the single most expensive failure mode in a two-person,
two-machine project: the AI and the backend quietly disagreeing about the
payload shape, and nobody noticing until integration week.

Three things are asserted:
  1. the generated schemas are valid JSON Schema at all;
  2. they are not stale with respect to ghostnet/contract.py;
  3. real pipeline output -- not just the hand-written fixtures -- satisfies them.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

AI_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = AI_ROOT.parent
CONTRACTS = REPO_ROOT / "contracts"
FIXTURES = AI_ROOT / "fixtures"

sys.path.insert(0, str(AI_ROOT))

jsonschema = pytest.importorskip("jsonschema")
from jsonschema import Draft202012Validator  # noqa: E402

from ghostnet import detect  # noqa: E402
from ghostnet.contract import CONTRACT_VERSION  # noqa: E402

SCHEMA_NAMES = ["ai-input.schema.json", "ai-output.schema.json", "ai-error.schema.json"]


def load(name: str) -> dict:
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def output_validator() -> Draft202012Validator:
    return Draft202012Validator(load("ai-output.schema.json"))


@pytest.mark.parametrize("name", SCHEMA_NAMES)
def test_schema_file_exists_and_is_valid_json_schema(name):
    assert (CONTRACTS / name).exists(), f"{name} missing -- run ai/scripts/export_schemas.py"
    Draft202012Validator.check_schema(load(name))


def test_schemas_are_not_stale():
    """The generator is the source of truth. If this fails, someone edited
    contract.py without regenerating, and Member 2's validator is about to
    reject payloads that are actually correct."""
    proc = subprocess.run(
        [sys.executable, str(AI_ROOT / "scripts" / "export_schemas.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, "contracts/ are stale:\n" + proc.stdout + proc.stderr


def test_contract_version_is_pinned_across_schemas():
    assert load("ai-error.schema.json")["properties"]["contract_version"]["const"] == CONTRACT_VERSION
    assert CONTRACT_VERSION in load("ai-output.schema.json")["description"]


@pytest.mark.parametrize("fixture", sorted(p.name for p in FIXTURES.glob("*.json")))
def test_fixtures_validate(fixture, output_validator):
    """Member 2 builds the entire UI against these. If one drifts out of spec,
    the mock and the real service diverge silently."""
    errors = sorted(output_validator.iter_errors(json.loads((FIXTURES / fixture).read_text())), key=str)
    assert not errors, fixture + ": " + "; ".join(e.message for e in errors[:3])


# --- live output, which is the assertion that actually matters -------------

def test_live_output_validates_with_no_weights(output_validator, tmp_path):
    """The degraded path is the one Member 2 will hit first, before any model
    exists. It must still return a contract-valid payload, not an error."""
    img = tmp_path / "frame_0001.png"
    img.write_bytes(b"not really a png")
    out = detect(img, {"survey_id": "SURVEY-TEST"})
    assert not list(output_validator.iter_errors(out))
    assert out["detections"] == []
    assert out["warnings"], "a degraded result must explain itself"


def test_live_output_validates_for_a_missing_image(output_validator):
    out = detect("no_such_file.png", {"survey_id": "SURVEY-TEST"})
    assert not list(output_validator.iter_errors(out))
    assert any("not found" in w for w in out["warnings"])


def test_required_keys_are_exactly_what_member_2_can_rely_on(output_validator):
    """Guards against a field quietly becoming optional. Member 2's DB schema
    declares these NOT NULL."""
    required = set(load("ai-output.schema.json")["required"])
    assert required == {"survey_id", "frame_id"}

    det = load("ai-output.schema.json")["$defs"]["Detection"]["required"]
    assert set(det) == {
        "detection_id",
        "class",
        "raw_score",
        "calibrated_confidence",
        "uncertainty",
        "bbox",
    }


def test_class_and_uncertainty_are_closed_vocabularies():
    """Adding a member here is a breaking change for Member 2's enum columns."""
    det = load("ai-output.schema.json")["$defs"]["Detection"]["properties"]
    assert det["class"]["enum"] == ["ghost_net", "debris", "natural", "unknown"]
    assert det["uncertainty"]["enum"] == ["low", "medium", "high"]


def test_nullable_position_fields_are_actually_nullable():
    """The honesty rule expressed in the schema: a missing position is a legal
    value, so Member 2 must render it rather than treat it as corrupt data."""
    det = load("ai-output.schema.json")["$defs"]["Detection"]["properties"]
    for field in ("latitude", "longitude", "position_error_m"):
        assert "null" in det[field]["type"], field + " must be nullable"
