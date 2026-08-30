"""Emit example contract payloads so Member 2 can build the whole web app today.

    python scripts/make_fixtures.py

Writes ai/fixtures/*.json. These are SYNTHETIC illustrations of the payload
shape -- never present these numbers as measured results (plan §25, E16, E54).
The real pipeline emits the identical shape, so nothing on Member 2's side has
to change when the trained model arrives.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ghostnet.contract import (  # noqa: E402
    Detection,
    Dimensions,
    EvidenceSummary,
    FrameResult,
    validate,
)

OUT = Path(__file__).resolve().parent.parent / "fixtures"


def example_full() -> FrameResult:
    """Best case: geometry and a nav fix were both available."""
    return FrameResult(
        survey_id="SURVEY-001",
        frame_id="PING-18452",
        provenance={
            "model_id": "ghostnet-yolo11s",
            "model_version": "v0-stub",
            "dataset_version": "none",
            "preprocessing_version": "v0",
            "calibration_version": "none",
        },
        detections=[
            Detection(
                detection_id="D-00027AB1",
                cls="ghost_net",
                raw_score=0.91,
                calibrated_confidence=0.83,
                uncertainty="low",
                bbox=[320, 180, 190, 120],
                latitude=20.123456,
                longitude=70.123456,
                position_error_m=4.5,
                localization="frame-level",
                dimensions=Dimensions(width=3.2, length=8.4, status="estimated"),
                model_version="v0-stub",
                evidence_summary=EvidenceSummary(
                    artificial_verification="positive",
                    shadow_context="supportive",
                ),
            ),
            Detection(
                detection_id="D-00027AB2",
                cls="natural",
                raw_score=0.64,
                calibrated_confidence=0.55,
                uncertainty="medium",
                bbox=[40, 500, 260, 140],
                latitude=20.123901,
                longitude=70.122880,
                position_error_m=6.1,
                localization="frame-level",
                dimensions=Dimensions(width=11.0, length=6.2, status="estimated"),
                model_version="v0-stub",
                evidence_summary=EvidenceSummary(artificial_verification="negative"),
            ),
        ],
    )


def example_no_metadata() -> FrameResult:
    """Common case: an image with no navigation data. Positions are withheld,
    NOT invented. Member 2 must render this without crashing."""
    return FrameResult(
        survey_id="SURVEY-002",
        frame_id="frame_0007",
        provenance={"model_id": "ghostnet-yolo11s", "model_version": "v0-stub"},
        detections=[
            Detection(
                detection_id="D-00031CC0",
                cls="debris",
                raw_score=0.47,
                calibrated_confidence=0.39,
                uncertainty="high",
                bbox=[600, 210, 70, 55],
                model_version="v0-stub",
            )
        ],
        warnings=["incomplete sonar geometry; detections reported without coordinates"],
    )


def example_empty() -> FrameResult:
    """Clean seabed, or no model loaded yet. The empty state the UI needs."""
    return FrameResult(
        survey_id="SURVEY-002",
        frame_id="frame_0008",
        provenance={"model_id": "ghostnet-yolo11s", "model_version": "v0-stub"},
        warnings=["no trained weights available; returning empty detections."],
    )


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    cases = {
        "example_full.json": example_full(),
        "example_no_metadata.json": example_no_metadata(),
        "example_empty.json": example_empty(),
    }
    failed = False
    for name, res in cases.items():
        payload = res.to_dict()
        problems = validate(payload)
        if problems:
            failed = True
            print("INVALID " + name)
            for p in problems:
                print("   - " + p)
        (OUT / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print("wrote " + str((OUT / name).relative_to(OUT.parent)) + " (" + str(len(payload["detections"])) + " detections)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
