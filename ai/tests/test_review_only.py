"""D5: `ghost_net` is offered for review, never claimed.

The two halves of this policy are one decision and the tests treat them that
way. A lower floor WITHOUT the `review_only` flag would be overclaiming a class
that measured recall 0.000 on gv5 and gv6; the flag WITHOUT the lower floor
would suppress the class entirely and flag nothing. Either half alone is a bug.

See docs/EXPERIMENT_GV7_PLAN.md section 10.5, Tier 1.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

from ghostnet.config import Settings
from ghostnet.contract import CONTRACT_VERSION, Detection, validate
from ghostnet.decision import REVIEW_ONLY_CLASSES, apply_decision_policy, is_review_only


@pytest.fixture
def uncal() -> Settings:
    """Settings with T == 1.0 so raw scores pass through as calibrated ones."""
    return Settings()


def test_only_ghost_net_is_review_only():
    assert is_review_only("ghost_net")
    for other in ("debris", "natural", "unknown"):
        assert not is_review_only(other), f"{other} must remain a claimable class"
    assert REVIEW_ONLY_CLASSES == frozenset({"ghost_net"})


def test_net_raw_gate_is_lower_than_everyone_elses(uncal):
    assert uncal.raw_conf_threshold_net < uncal.raw_conf_threshold


def test_a_weak_net_survives_the_raw_gate_that_suppresses_other_artificials(uncal):
    """The whole point of D5: a raw score that drops `debris` keeps a net."""
    weak = (uncal.raw_conf_threshold_net + uncal.raw_conf_threshold) / 2

    assert apply_decision_policy("ghost_net", weak, uncal) is not None
    assert apply_decision_policy("debris", weak, uncal) is None


def test_a_net_below_its_own_raw_gate_is_still_suppressed(uncal):
    """Lenient is not unbounded."""
    assert apply_decision_policy("ghost_net", uncal.raw_conf_threshold_net / 2, uncal) is None


def test_other_classes_are_completely_unchanged_by_d5(uncal):
    """The guardrail. gv6's damage was inflicted on the classes that WORK, so
    D5 must be provably inert outside REVIEW_ONLY_CLASSES -- otherwise the
    published background-activation rates stop being quotable."""
    just_under = uncal.raw_conf_threshold - 1e-6
    just_over = uncal.raw_conf_threshold + 1e-6
    for cls in ("debris", "natural", "unknown"):
        assert apply_decision_policy(cls, just_under, uncal) is None, cls

    # Above the raw gate the artificial classes report, exactly as before.
    for cls in ("debris", "unknown"):
        assert apply_decision_policy(cls, just_over, uncal) is not None, cls

    # `natural` still does NOT, and that is pre-existing behaviour worth
    # pinning: its calibrated floor of 0.45 is genuinely live (unlike the
    # artificial one), so a barely-above-gate raw score is still suppressed.
    assert apply_decision_policy("natural", just_over, uncal) is None


def test_the_calibrated_net_floor_is_documented_as_non_binding(uncal):
    """Guards the finding, not the code: with raw_conf_threshold = 0.10 and the
    fitted T, the lowest calibrated confidence that can reach the policy is
    already above every artificial floor. If this ever fails, calibration
    changed and the floors became live again -- re-read decision.py note 5."""
    from ghostnet.decision import calibrate

    lowest_reachable = calibrate(uncal.raw_conf_threshold, uncal)
    assert lowest_reachable > uncal.review_floor_net
    assert lowest_reachable > uncal.review_floor_artificial


def test_review_only_flag_reaches_the_payload_and_defaults_off():
    net = Detection(
        detection_id="D-1", cls="ghost_net", raw_score=0.2,
        calibrated_confidence=0.2, uncertainty="high", bbox=[0, 0, 4, 4],
        review_only=True,
    )
    assert net.to_dict()["review_only"] is True

    debris = Detection(
        detection_id="D-2", cls="debris", raw_score=0.9,
        calibrated_confidence=0.9, uncertainty="low", bbox=[0, 0, 4, 4],
    )
    assert debris.to_dict()["review_only"] is False, "claims must not default to candidates"


def test_review_only_payload_still_satisfies_the_contract():
    """Additive field: an existing consumer must not start failing validation."""
    payload = {
        "survey_id": "S1", "frame_id": "F1", "contract_version": CONTRACT_VERSION,
        "detections": [Detection(
            detection_id="D-1", cls="ghost_net", raw_score=0.2,
            calibrated_confidence=0.2, uncertainty="high", bbox=[0, 0, 4, 4],
            review_only=True,
        ).to_dict()],
    }
    assert validate(payload) == []


def test_contract_version_was_bumped_for_the_new_field():
    """A field added without a version bump is how a consumer breaks silently."""
    assert CONTRACT_VERSION >= "1.2.0"
