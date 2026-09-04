import uuid

import pytest

from app.models.enums import ReviewStatus
from app.models.sonar_frame import SonarFrame
from app.models.survey import Survey
from app.models.survey_file import SurveyFile
from app.schemas.ai_contract import AIDetection, AIDimensions
from app.services import detection_service


def _make_frame(db_session) -> SonarFrame:
    survey = Survey(name="Detection Test Survey")
    db_session.add(survey)
    db_session.flush()

    survey_file = SurveyFile(
        survey_id=survey.id,
        filename="frame.png",
        storage_reference=f"{survey.id}/frame.png",
        format="png",
        size=100,
        checksum="abc123",
        validation_status="VALID",
        metadata_status="VALID",
    )
    db_session.add(survey_file)
    db_session.flush()

    frame = SonarFrame(
        survey_id=survey.id,
        file_id=survey_file.id,
        frame_id="FRAME-TEST-1",
        image_reference=survey_file.storage_reference,
        latitude=20.5,
        longitude=70.5,
        depth=12.0,
    )
    db_session.add(frame)
    db_session.flush()
    return frame


def test_persist_valid_ai_detection(db_session):
    frame = _make_frame(db_session)

    ai_detection = AIDetection(
        detection_id="D-TEST-001",
        class_="ghost_net",
        raw_score=0.91,
        calibrated_confidence=0.93,
        uncertainty="low",
        bbox=[10, 20, 100, 80],
        latitude=20.5001,
        longitude=70.5001,
        position_error_m=4.5,
        localization="frame-level",
        dimensions=AIDimensions(width=3.2, length=8.4, status="estimated"),
        review_status="pending",
        model_version="mock-ghostnet-dev-v0",
        evidence_summary={},
    )

    detection = detection_service.persist_ai_detection(db_session, frame.survey_id, frame, ai_detection)
    db_session.commit()

    assert detection.detection_ref == "D-TEST-001"
    assert detection.review_status == ReviewStatus.PENDING
    assert detection.priority == "critical"
    assert detection.area == pytest.approx(3.2 * 8.4, rel=1e-3)


def test_reject_invalid_class(db_session):
    frame = _make_frame(db_session)
    ai_detection = AIDetection(
        detection_id="D-TEST-002",
        class_="not_a_real_class",
        model_version="mock-ghostnet-dev-v0",
    )
    with pytest.raises(detection_service.DetectionValidationError):
        detection_service.persist_ai_detection(db_session, frame.survey_id, frame, ai_detection)


def test_reject_out_of_range_confidence(db_session):
    frame = _make_frame(db_session)
    ai_detection = AIDetection(
        detection_id="D-TEST-003",
        class_="ghost_net",
        calibrated_confidence=1.5,
        model_version="mock-ghostnet-dev-v0",
    )
    with pytest.raises(detection_service.DetectionValidationError):
        detection_service.persist_ai_detection(db_session, frame.survey_id, frame, ai_detection)
