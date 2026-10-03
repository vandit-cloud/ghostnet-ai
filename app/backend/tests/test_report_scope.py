"""Regressions for B3, B4, B5, C1 and C2 in docs/KNOWN_ISSUES.md: a report or a
map view must cover exactly the scope it claims."""

import csv
import io
import time
import uuid

from app.models.sonar_frame import SonarFrame
from app.schemas.ai_contract import AIDetection, AIDimensions
from app.services import detection_service
from tests.test_detections import _seed_detection


def _add_detection(db_session, survey, *, detection_id: str, klass: str, confidence: float):
    frame = db_session.query(SonarFrame).filter(SonarFrame.survey_id == survey.id).first()
    detection = detection_service.persist_ai_detection(
        db_session,
        survey.id,
        frame,
        AIDetection(
            detection_id=detection_id,
            class_=klass,
            calibrated_confidence=confidence,
            raw_score=confidence,
            latitude=21.0002,
            longitude=71.0002,
            dimensions=AIDimensions(width=1.0, length=2.0, status="estimated"),
            model_version="mock-ghostnet-dev-v0",
        ),
    )
    db_session.commit()
    return detection


def _two_detection_survey(db_session, tag: str):
    survey, net = _seed_detection(db_session, detection_id=f"D-{tag}-NET", klass="ghost_net")
    debris = _add_detection(db_session, survey, detection_id=f"D-{tag}-DEBRIS", klass="debris", confidence=0.5)
    return survey, net, debris


def _csv_refs(client, auth_headers, report_id: str) -> list[str]:
    final = None
    for _ in range(50):
        final = client.get(f"/api/v1/reports/{report_id}", headers=auth_headers).json()
        if final["status"] in ("COMPLETED", "FAILED"):
            break
        time.sleep(0.2)
    assert final["status"] == "COMPLETED"
    body = client.get(f"/api/v1/reports/{report_id}/download", headers=auth_headers).text
    return sorted(row["detection_id"] for row in csv.DictReader(io.StringIO(body)))


def _post_report(client, auth_headers, **payload):
    return client.post("/api/v1/reports", json={"format": "csv", **payload}, headers=auth_headers)


# --- B3 / C2: selected-detection reports ----------------------------------------


def test_selected_detection_report_contains_only_that_detection(client, auth_headers, db_session):
    survey, net, _ = _two_detection_survey(db_session, "B3")

    response = _post_report(
        client, auth_headers, survey_id=str(survey.id), type="selected_detection", detection_id=str(net.id)
    )
    assert response.status_code == 202
    assert _csv_refs(client, auth_headers, response.json()["id"]) == ["D-B3-NET"]


def test_selected_detection_report_without_an_id_is_refused(client, auth_headers, db_session):
    survey, _ = _seed_detection(db_session, detection_id="D-C2-001")

    response = _post_report(client, auth_headers, survey_id=str(survey.id), type="selected_detection")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "DETECTION_ID_REQUIRED"


def test_selected_detection_must_belong_to_the_survey(client, auth_headers, db_session):
    survey, _ = _seed_detection(db_session, detection_id="D-B3-A")
    _, other = _seed_detection(db_session, detection_id="D-B3-B")

    response = _post_report(
        client, auth_headers, survey_id=str(survey.id), type="selected_detection", detection_id=str(other.id)
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DETECTION_NOT_FOUND"


# --- B4: filtered reports --------------------------------------------------------


def test_filtered_report_applies_its_filters(client, auth_headers, db_session):
    survey, _, _ = _two_detection_survey(db_session, "B4")

    response = _post_report(
        client, auth_headers, survey_id=str(survey.id), type="filtered_detections", filters={"class": "debris"}
    )
    assert response.status_code == 202
    assert response.json()["filters"] == {"class": "debris"}
    assert _csv_refs(client, auth_headers, response.json()["id"]) == ["D-B4-DEBRIS"]


def test_filtered_report_refuses_an_unknown_filter_key(client, auth_headers, db_session):
    survey, _ = _seed_detection(db_session, detection_id="D-B4-KEY")

    response = _post_report(
        client, auth_headers, survey_id=str(survey.id), type="filtered_detections", filters={"klass": "debris"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNKNOWN_REPORT_FILTER"


def test_filtered_report_with_no_filters_is_refused(client, auth_headers, db_session):
    survey, _ = _seed_detection(db_session, detection_id="D-B4-EMPTY")

    response = _post_report(
        client, auth_headers, survey_id=str(survey.id), type="filtered_detections", filters={"class": ""}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "REPORT_FILTERS_REQUIRED"


# --- C1: unknown survey ----------------------------------------------------------


def test_report_for_an_unknown_survey_is_a_404_not_a_500(client, auth_headers):
    response = _post_report(client, auth_headers, survey_id=str(uuid.uuid4()), type="full_survey")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SURVEY_NOT_FOUND"


# --- B5: map bounds follow the filter --------------------------------------------


def _survey_with_a_distant_track_point(db_session, tag: str):
    survey, net = _seed_detection(db_session, detection_id=f"D-{tag}")
    first = db_session.query(SonarFrame).filter(SonarFrame.survey_id == survey.id).first()
    db_session.add(
        SonarFrame(
            survey_id=survey.id,
            file_id=first.file_id,
            frame_id=f"FRAME-{tag}-FAR",
            image_reference=first.image_reference,
            latitude=21.5,
            longitude=71.5,
        )
    )
    db_session.commit()
    return survey


def _bounds(client, auth_headers, survey, **params):
    response = client.get(f"/api/v1/maps/surveys/{survey.id}/detections", params=params, headers=auth_headers)
    assert response.status_code == 200
    return response.json()["bounds"]


def test_unfiltered_map_frames_the_whole_track(client, auth_headers, db_session):
    survey = _survey_with_a_distant_track_point(db_session, "B5-ALL")
    assert _bounds(client, auth_headers, survey)["max_lat"] == 21.5


def test_filtered_map_frames_only_the_kept_markers(client, auth_headers, db_session):
    survey = _survey_with_a_distant_track_point(db_session, "B5-CLASS")
    bounds = _bounds(client, auth_headers, survey, detection_class="ghost_net")
    assert bounds["max_lat"] < 21.01


def test_a_bbox_that_excludes_every_marker_frames_the_bbox(client, auth_headers, db_session):
    survey = _survey_with_a_distant_track_point(db_session, "B5-BBOX")
    box = {"min_lat": 10.0, "min_lon": 10.0, "max_lat": 10.1, "max_lon": 10.1}
    assert _bounds(client, auth_headers, survey, **box) == box
