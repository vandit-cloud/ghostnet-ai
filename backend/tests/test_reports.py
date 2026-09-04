import time

from tests.test_detections import _seed_detection


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
