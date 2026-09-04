from tests.test_detections import _seed_detection


def test_dashboard_summary(client, auth_headers, db_session):
    _seed_detection(db_session, detection_id="D-DASH-001", confidence=0.95)

    response = client.get("/api/v1/dashboard/summary", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["candidates"] >= 1
    assert "class_distribution" in body
    assert "recent_detections" in body
