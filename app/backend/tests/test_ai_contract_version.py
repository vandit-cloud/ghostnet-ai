"""Tests for the AI contract MAJOR pin.

The agreement with Member 1 is semver: a MINOR bump adds an optional field and
this consumer keeps working untouched, a MAJOR bump renames or removes one, or
adds a new `class` / `uncertainty` value. A silent schema disagreement found
during integration week is the most expensive thing that can happen to this
project, so it is checked at adapter construction rather than discovered from
a wrong number on a map.

The important test here is the LAST one. Every other way the real adapter can
fail to initialise degrades to `MockAIAdapter`, which is correct -- it honestly
stands in for "no AI available". A schema mismatch is not that: the AI is
available and the two halves disagree about what its output means. Degrading
there would serve `mock-ghostnet-dev-v0` detections to an operator who believes
they are looking at real sonar analysis.
"""

import pytest

from app.schemas.ai_contract import (
    EXPECTED_CONTRACT_MAJOR,
    ContractMajorMismatch,
    contract_major,
)

ghostnet = pytest.importorskip("ghostnet", reason="Member 1's AI package is not installed")


class TestContractMajor:
    @pytest.mark.parametrize(
        "version,expected",
        [
            ("1.1.0", 1),
            ("1.0.0", 1),
            ("2.0.0", 2),
            ("10.2.3", 10),
            ("1", 1),
        ],
    )
    def test_it_reads_the_major(self, version, expected):
        assert contract_major(version) == expected

    @pytest.mark.parametrize("version", [None, "", "   ", "v1.1.0", "unreleased"])
    def test_unparseable_is_none_not_zero(self, version):
        """None means "cannot tell", which must NOT be confused with a mismatch:
        an AI build predating `contract_version` is a warning, not a refusal."""
        assert contract_major(version) is None


def test_the_installed_package_matches_the_pin():
    """The real reason this file exists. If Member 1 ships a MAJOR bump, this
    test fails on the next pull rather than at the demo."""
    found = contract_major(getattr(ghostnet, "CONTRACT_VERSION", None))
    assert found == EXPECTED_CONTRACT_MAJOR, (
        f"ghostnet speaks contract {ghostnet.CONTRACT_VERSION}; this backend is "
        f"pinned to MAJOR {EXPECTED_CONTRACT_MAJOR}. Reconcile "
        f"app/schemas/ai_contract.py against contracts/*.schema.json first."
    )


def test_a_minor_bump_is_transparent(monkeypatch):
    """The whole point of MINOR being safe: a new optional field needs no
    coordinated change here, so the adapter must still build."""
    monkeypatch.setattr(ghostnet, "CONTRACT_VERSION", f"{EXPECTED_CONTRACT_MAJOR}.99.0", raising=False)
    from app.services.ghostnet_adapter import try_build

    assert try_build() is not None


def test_a_major_bump_refuses_to_start_instead_of_serving_mock_detections(monkeypatch):
    """The one initialisation failure that must NOT degrade to the mock."""
    monkeypatch.setattr(ghostnet, "CONTRACT_VERSION", f"{EXPECTED_CONTRACT_MAJOR + 1}.0.0", raising=False)
    from app.services.ghostnet_adapter import try_build

    with pytest.raises(ContractMajorMismatch) as err:
        try_build()

    # The message has to tell whoever hits it what to do next.
    assert "contracts/*.schema.json" in str(err.value)
    assert "EXPECTED_CONTRACT_MAJOR" in str(err.value)
