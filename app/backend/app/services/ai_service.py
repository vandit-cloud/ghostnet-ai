"""AI service adapter (spec sections 51-52, Member 1 interface spec section 33).

`AIServiceAdapter` is the seam between the backend and Member 1's model.
`MockAIAdapter` produces contract-valid, clearly-labelled synthetic
detections so the rest of the application (DB, GIS, review, reports) can be
built and tested while Member 1's model is trained. Swapping in the real
service later means implementing `analyze_frame` against a real inference
call (e.g. POST /ai/v1/infer) - no other module needs to change.
"""

import hashlib
import logging
import random
from pathlib import Path
from typing import Protocol

from app.schemas.ai_contract import AIDetection, AIDimensions, AIFrameMetadata, AIInferResponse

logger = logging.getLogger("ghostnet.ai")

MOCK_MODEL_VERSION = "mock-ghostnet-dev-v0"


class AIServiceAdapter(Protocol):
    def analyze_frame(
        self,
        survey_id: str,
        frame_id: str,
        image_path: str,
        metadata: AIFrameMetadata,
    ) -> AIInferResponse: ...


class MockAIAdapter:
    """Development-only stand-in for Member 1's AI pipeline.

    NOT real AI output - deterministic per-frame so demos/tests are
    reproducible. Must be replaced before production/company-grade use.
    """

    def analyze_frame(
        self,
        survey_id: str,
        frame_id: str,
        image_path: str,
        metadata: AIFrameMetadata,
    ) -> AIInferResponse:
        seed = int(hashlib.sha256(f"{survey_id}:{frame_id}".encode()).hexdigest(), 16)
        rng = random.Random(seed)

        detections: list[AIDetection] = []
        detection_count = rng.choices([0, 1, 2], weights=[0.35, 0.5, 0.15])[0]

        for i in range(detection_count):
            raw_score = round(rng.uniform(0.45, 0.98), 3)
            calibrated = round(min(0.99, max(0.01, raw_score + rng.uniform(-0.05, 0.05))), 3)
            uncertainty = "low" if calibrated >= 0.85 else "medium" if calibrated >= 0.6 else "high"
            klass = rng.choices(
                ["ghost_net", "debris", "natural_object", "unknown"],
                weights=[0.45, 0.2, 0.2, 0.15],
            )[0]

            lat = metadata.latitude
            lon = metadata.longitude
            position_error = None
            if lat is not None and lon is not None:
                lat = lat + rng.uniform(-0.0003, 0.0003)
                lon = lon + rng.uniform(-0.0003, 0.0003)
                position_error = round(rng.uniform(1.5, 8.0), 1)

            detections.append(
                AIDetection(
                    detection_id=f"D-{seed % 100000:05d}{i}",
                    class_=klass,
                    raw_score=raw_score,
                    calibrated_confidence=calibrated,
                    uncertainty=uncertainty,
                    bbox=[
                        round(rng.uniform(0, 500), 1),
                        round(rng.uniform(0, 300), 1),
                        round(rng.uniform(40, 220), 1),
                        round(rng.uniform(30, 160), 1),
                    ],
                    mask=None,
                    latitude=lat,
                    longitude=lon,
                    position_error_m=position_error,
                    localization="frame-level" if lat is not None else None,
                    dimensions=AIDimensions(
                        width=round(rng.uniform(1.0, 5.0), 1),
                        length=round(rng.uniform(2.0, 12.0), 1),
                        status="estimated",
                    ),
                    review_status="pending",
                    model_version=MOCK_MODEL_VERSION,
                    evidence_summary={"note": "mock/development detection", "source": "MockAIAdapter"},
                )
            )

        return AIInferResponse(survey_id=survey_id, frame_id=frame_id, detections=detections)


def get_ai_adapter() -> AIServiceAdapter:
    """Real detector when it is installed, mock otherwise.

    Auto-detecting rather than config-flagged on purpose: a developer with no
    AI environment gets a working backend without setting anything, and the
    demo machine gets the real model without anyone remembering to flip a flag.
    Which one is active is logged, and every payload carries
    `provenance.model_version` -- "mock-ghostnet-dev-v0" for the mock, the run
    name (e.g. "gv5-yolo11s") for the real one -- so a stored detection can
    never be mistaken for the other kind later.
    """
    from app.services.ghostnet_adapter import try_build

    real = try_build()
    if real is not None:
        logger.info("AI adapter: ghostnet (weights loaded=%s)", real.loaded)
        return real
    logger.warning("AI adapter: MockAIAdapter -- these are NOT real detections")
    return MockAIAdapter()
