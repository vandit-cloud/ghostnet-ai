from app.models.sonar_frame import SonarFrame
from app.models.survey import Survey
from app.models.survey_file import SurveyFile
from app.schemas.ai_contract import AIDetection, AIDimensions
from app.services import detection_service


def _seed_detection(db_session, *, detection_id: str, klass: str = "ghost_net", confidence: float = 0.9):
    survey = Survey(name=f"Survey for {detection_id}")
    db_session.add(survey)
    db_session.flush()

    survey_file = SurveyFile(
        survey_id=survey.id,
        filename="f.png",
        storage_reference=f"{survey.id}/f.png",
        format="png",
        size=10,
        checksum="x",
        validation_status="VALID",
        metadata_status="VALID",
    )
    db_session.add(survey_file)
    db_session.flush()

    frame = SonarFrame(
        survey_id=survey.id,
        file_id=survey_file.id,
        frame_id=f"FRAME-{detection_id}",
        image_reference=survey_file.storage_reference,
        latitude=21.0,
        longitude=71.0,
    )
    db_session.add(frame)
    db_session.flush()

    ai_detection = AIDetection(
        detection_id=detection_id,
        class_=klass,
        calibrated_confidence=confidence,
        raw_score=confidence,
        latitude=21.0001,
        longitude=71.0001,
        dimensions=AIDimensions(width=1.0, length=2.0, status="estimated"),
        model_version="mock-ghostnet-dev-v0",
    )
    detection = detection_service.persist_ai_detection(db_session, survey.id, frame, ai_detection)
    db_session.commit()
    return survey, detection


def test_list_and_filter_detections(client, auth_headers, db_session):
    survey, detection = _seed_detection(db_session, detection_id="D-LIST-001", klass="ghost_net", confidence=0.92)

    response = client.get(f"/api/v1/detections?survey_id={survey.id}", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["detection_ref"] == "D-LIST-001"

    filtered = client.get(
        f"/api/v1/detections?survey_id={survey.id}&detection_class=debris", headers=auth_headers
    )
    assert filtered.json()["total"] == 0


def test_get_detection_detail_and_review(client, auth_headers, db_session):
    survey, detection = _seed_detection(db_session, detection_id="D-DETAIL-001")

    detail = client.get(f"/api/v1/detections/{detection.id}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["review_status"] == "pending"

    review = client.post(
        f"/api/v1/detections/{detection.id}/review",
        json={"decision": "accepted_artificial", "reviewer": "operator", "note": "Confirmed net."},
        headers=auth_headers,
    )
    assert review.status_code == 201

    detail_after = client.get(f"/api/v1/detections/{detection.id}", headers=auth_headers)
    assert detail_after.json()["review_status"] == "accepted_artificial"

    reviews = client.get(f"/api/v1/detections/{detection.id}/reviews", headers=auth_headers)
    assert len(reviews.json()) == 1


def test_map_markers(client, auth_headers, db_session):
    survey, detection = _seed_detection(db_session, detection_id="D-MAP-001")

    response = client.get(f"/api/v1/maps/surveys/{survey.id}/detections", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body["markers"]) == 1
    assert body["markers"][0]["detection_ref"] == "D-MAP-001"
    assert body["bounds"] is not None
