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


def test_a_net_outline_and_review_flag_survive_ingest(db_session):
    """Contract 1.3.0 fills `mask` with a polygon. The backend typed it as a
    string while the AI only ever sent null, so the first real polygon would
    have failed validation. Pin the whole path: raw AI dict -> adapter ->
    persisted row."""
    from app.services.ghostnet_adapter import _to_detection

    frame = _make_frame(db_session)
    polygon = [[330, 290], [345, 298], [508, 192], [494, 182]]
    ai_detection = _to_detection({
        "detection_id": "D-NET-001", "class": "ghost_net", "raw_score": 0.9,
        "calibrated_confidence": 0.9, "uncertainty": "medium",
        "bbox": [320, 180, 190, 120], "mask": polygon, "review_only": True,
        "dimensions": {}, "evidence_summary": {}, "model_version": "gv9r-test",
    })
    assert ai_detection.mask == polygon and ai_detection.review_only is True

    detection = detection_service.persist_ai_detection(db_session, frame.survey_id, frame, ai_detection)
    db_session.commit()
    db_session.refresh(detection)
    assert detection.mask_polygon == polygon
    assert detection.review_only is True


def test_a_box_only_detection_has_no_outline_and_is_not_review_only(db_session):
    from app.services.ghostnet_adapter import _to_detection

    frame = _make_frame(db_session)
    ai_detection = _to_detection({
        "detection_id": "D-BOX-001", "class": "debris", "raw_score": 0.8,
        "calibrated_confidence": 0.8, "uncertainty": "medium",
        "bbox": [10, 20, 30, 40], "mask": None, "dimensions": {}, "evidence_summary": {}, "model_version": "gv9r-test",
    })
    detection = detection_service.persist_ai_detection(db_session, frame.survey_id, frame, ai_detection)
    db_session.commit()
    db_session.refresh(detection)
    assert detection.mask_polygon is None
    assert detection.review_only is False


def test_a_natural_detection_from_the_ai_is_stored_not_rejected(db_session):
    """The contract calls the class `natural`; the backend has always stored
    `natural_object`. Without the adapter's translation the validator rejected
    every natural detection as an unrecognised class, so the natural-vs-
    artificial evidence the AI produces never reached a reviewer."""
    from app.services.ghostnet_adapter import _to_detection

    frame = _make_frame(db_session)
    ai_detection = _to_detection({
        "detection_id": "D-NAT-001", "class": "natural", "raw_score": 0.7,
        "calibrated_confidence": 0.7, "uncertainty": "medium",
        "bbox": [10, 20, 30, 40], "mask": None, "dimensions": {}, "evidence_summary": {}, "model_version": "gv5-test",
    })
    assert ai_detection.class_ == "natural_object"

    detection = detection_service.persist_ai_detection(db_session, frame.survey_id, frame, ai_detection)
    db_session.commit()
    db_session.refresh(detection)
    assert detection.detection_class == "natural_object"


def test_the_other_ai_classes_pass_through_unchanged():
    from app.services.ghostnet_adapter import _to_detection

    for cls in ("ghost_net", "debris", "unknown"):
        d = _to_detection({"detection_id": "D-" + cls, "class": cls, "dimensions": {}, "evidence_summary": {}})
        assert d.class_ == cls
