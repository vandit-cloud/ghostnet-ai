import json
import math
import time
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from app.models.enums import ReportType
from app.schemas.ai_contract import AIDetection
from app.services import detection_service
from app.services.report_service import _render_geojson
from tests.test_detections import _seed_detection


def _wait_for_report(client, auth_headers, report_id):
    final = None
    for _ in range(50):
        final = client.get(f"/api/v1/reports/{report_id}", headers=auth_headers).json()
        if final["status"] in ("COMPLETED", "FAILED"):
            break
        time.sleep(0.2)
    return final


def _fake_detection(ref, lat, lon, **overrides):
    # The renderer only reads attributes, so a namespace stands in for the ORM
    # row and the structure tests need no database.
    fields = dict(
        id=uuid.uuid4(),
        detection_ref=ref,
        survey_id=uuid.uuid4(),
        frame_id=uuid.uuid4(),
        detection_class="debris",
        raw_score=0.2,
        calibrated_confidence=0.37,
        uncertainty="high",
        latitude=lat,
        longitude=lon,
        position_error_m=3.76,
        localization_method="frame-level",
        width=13.8,
        length=113.84,
        area=1570.99,
        dimension_status="estimated",
        priority="low",
        review_status="pending",
        model_version="gv5-yolo11s",
        evidence_summary={"notes": "detector class: wreck"},
        created_at=datetime(2026, 9, 5, tzinfo=timezone.utc),
    )
    fields.update(overrides)
    return SimpleNamespace(**fields)


def _fake_report():
    return SimpleNamespace(survey_id=uuid.uuid4(), type=ReportType.FULL_SURVEY, filters={})


def _reject_nan(constant):
    raise ValueError(f"non-JSON constant {constant} in GeoJSON output")


def _assert_valid_feature_collection(doc):
    """RFC 7946 structure checks. No geojson/shapely lib is installed in the
    backend venv, so this is the validator."""
    assert doc["type"] == "FeatureCollection"
    assert isinstance(doc["features"], list)
    for f in doc["features"]:
        assert f["type"] == "Feature"
        assert isinstance(f["properties"], dict)
        assert "geometry" in f  # must be present, even when null
        g = f["geometry"]
        if g is not None:
            assert g["type"] == "Point"
            assert len(g["coordinates"]) == 2
            lon, lat = g["coordinates"]
            assert all(math.isfinite(v) for v in (lon, lat))
            assert -180 <= lon <= 180 and -90 <= lat <= 90


def test_generate_and_download_csv_report(client, auth_headers, db_session):
    survey, detection = _seed_detection(db_session, detection_id="D-REPORT-001")

    create = client.post(
        "/api/v1/reports",
        json={"survey_id": str(survey.id), "type": "full_survey", "format": "csv"},
        headers=auth_headers,
    )
    assert create.status_code == 202
    report = create.json()

    final = None
    for _ in range(50):
        response = client.get(f"/api/v1/reports/{report['id']}", headers=auth_headers)
        final = response.json()
        if final["status"] in ("COMPLETED", "FAILED"):
            break
        time.sleep(0.2)

    assert final["status"] == "COMPLETED"

    download = client.get(f"/api/v1/reports/{report['id']}/download", headers=auth_headers)
    assert download.status_code == 200
    assert "D-REPORT-001" in download.text


def test_generate_json_report(client, auth_headers, db_session):
    survey, detection = _seed_detection(db_session, detection_id="D-REPORT-002")

    create = client.post(
        "/api/v1/reports",
        json={"survey_id": str(survey.id), "type": "full_survey", "format": "json"},
        headers=auth_headers,
    )
    assert create.status_code == 202
    report_id = create.json()["id"]

    final = None
    for _ in range(50):
        response = client.get(f"/api/v1/reports/{report_id}", headers=auth_headers)
        final = response.json()
        if final["status"] in ("COMPLETED", "FAILED"):
            break
        time.sleep(0.2)

    assert final["status"] == "COMPLETED"
    download = client.get(f"/api/v1/reports/{report_id}/download", headers=auth_headers)
    assert download.status_code == 200
    assert "D-REPORT-002" in download.text


def test_geojson_lon_lat_order_and_properties():
    # Southern/western hemisphere values, so a swapped pair cannot pass by luck.
    doc = json.loads(
        _render_geojson(_fake_report(), [_fake_detection("D-1", -46.3461, -73.7274)]),
        parse_constant=_reject_nan,
    )
    _assert_valid_feature_collection(doc)
    feature = doc["features"][0]
    assert feature["geometry"]["coordinates"] == [-73.7274, -46.3461]
    props = feature["properties"]
    assert props["detection_id"] == "D-1"
    assert props["class"] == "debris"
    assert props["detector_class"] == "wreck"
    assert props["calibrated_confidence"] == 0.37
    assert props["position_error_m"] == 3.76
    assert props["position_status"] == "located"
    assert props["review_only"] is False
    assert props["width_m"] == 13.8 and props["length_m"] == 113.84
    assert doc["metadata"]["located_count"] == 1
    assert doc["metadata"]["unlocated_count"] == 0


def test_geojson_keeps_unlocated_detections_with_null_geometry():
    detections = [
        _fake_detection("D-OK", 21.0, 71.0),
        _fake_detection("D-NOPOS", None, None, localization_method="none"),
        _fake_detection("D-NAN", float("nan"), 71.0, position_error_m=float("nan")),
        _fake_detection("D-RANGE", 95.0, 71.0, detection_class="ghost_net", evidence_summary={}),
    ]
    # Strict parse: a bare NaN anywhere in the output fails here.
    doc = json.loads(_render_geojson(_fake_report(), detections), parse_constant=_reject_nan)
    _assert_valid_feature_collection(doc)
    assert len(doc["features"]) == 4
    by_ref = {f["properties"]["detection_id"]: f for f in doc["features"]}
    assert by_ref["D-NOPOS"]["geometry"] is None
    assert by_ref["D-NOPOS"]["properties"]["position_status"] == "no_position"
    assert by_ref["D-NAN"]["geometry"] is None
    assert by_ref["D-NAN"]["properties"]["latitude"] is None
    assert by_ref["D-NAN"]["properties"]["position_error_m"] is None
    assert by_ref["D-RANGE"]["properties"]["position_status"] == "invalid_position"
    assert by_ref["D-RANGE"]["properties"]["review_only"] is True
    assert by_ref["D-RANGE"]["properties"]["detector_class"] is None
    meta = doc["metadata"]
    assert meta["detection_count"] == 4
    assert meta["located_count"] == 1
    assert meta["unlocated_count"] == 3
    assert sorted(meta["unlocated_detection_ids"]) == ["D-NAN", "D-NOPOS", "D-RANGE"]


def test_geojson_report_endpoint(client, auth_headers, db_session):
    survey, detection = _seed_detection(db_session, detection_id="D-REPORT-GEO")
    # A second, position-less detection: it must arrive with null geometry.
    detection_service.persist_ai_detection(
        db_session,
        survey.id,
        detection.frame,
        AIDetection(detection_id="D-REPORT-GEO-NOPOS", class_="debris", calibrated_confidence=0.5, raw_score=0.5, model_version="mock"),
    )
    db_session.commit()

    create = client.post(
        "/api/v1/reports",
        json={"survey_id": str(survey.id), "type": "full_survey", "format": "geojson"},
        headers=auth_headers,
    )
    assert create.status_code == 202
    report_id = create.json()["id"]
    assert _wait_for_report(client, auth_headers, report_id)["status"] == "COMPLETED"

    download = client.get(f"/api/v1/reports/{report_id}/download", headers=auth_headers)
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("application/geo+json")
    assert f'report-{report_id}.geojson"' in download.headers["content-disposition"]
    doc = json.loads(download.text, parse_constant=_reject_nan)
    _assert_valid_feature_collection(doc)
    by_ref = {f["properties"]["detection_id"]: f for f in doc["features"]}
    # _seed_detection stores latitude 21.0001, longitude 71.0001.
    assert by_ref["D-REPORT-GEO"]["geometry"]["coordinates"] == [71.0001, 21.0001]
    assert by_ref["D-REPORT-GEO-NOPOS"]["geometry"] is None
    assert doc["metadata"]["detection_count"] == 2
    assert doc["metadata"]["unlocated_detection_ids"] == ["D-REPORT-GEO-NOPOS"]


def test_geojson_report_with_zero_detections(client, auth_headers, db_session):
    survey, _ = _seed_detection(db_session, detection_id="D-REPORT-GEO-EMPTY")

    # A filter nothing matches gives an empty but still valid collection.
    create = client.post(
        "/api/v1/reports",
        json={
            "survey_id": str(survey.id),
            "type": "filtered_detections",
            "format": "geojson",
            "filters": {"class": "no_such_class"},
        },
        headers=auth_headers,
    )
    report_id = create.json()["id"]
    assert _wait_for_report(client, auth_headers, report_id)["status"] == "COMPLETED"
    doc = client.get(f"/api/v1/reports/{report_id}/download", headers=auth_headers).json()
    _assert_valid_feature_collection(doc)
    assert doc["features"] == []
    assert doc["metadata"]["detection_count"] == 0
    assert doc["metadata"]["unlocated_count"] == 0


def test_selected_detection_report_exports_only_that_detection(client, auth_headers, db_session):
    survey, wanted = _seed_detection(db_session, detection_id="D-REPORT-SEL-1")
    detection_service.persist_ai_detection(
        db_session,
        survey.id,
        wanted.frame,
        AIDetection(detection_id="D-REPORT-SEL-2", class_="debris", calibrated_confidence=0.5, raw_score=0.5, model_version="mock"),
    )
    db_session.commit()

    create = client.post(
        "/api/v1/reports",
        json={
            "survey_id": str(survey.id),
            "type": "selected_detection",
            "format": "geojson",
            "detection_id": str(wanted.id),
        },
        headers=auth_headers,
    )
    report_id = create.json()["id"]
    assert _wait_for_report(client, auth_headers, report_id)["status"] == "COMPLETED"
    doc = client.get(f"/api/v1/reports/{report_id}/download", headers=auth_headers).json()
    # Before detection_id was persisted in the report's filters, this exported
    # both detections in the survey.
    assert [f["properties"]["detection_id"] for f in doc["features"]] == ["D-REPORT-SEL-1"]
