def test_analytics_summary_requires_auth(client):
    response = client.get("/api/v1/analytics/summary")
    assert response.status_code == 401


def test_analytics_summary_shape(client, auth_headers):
    response = client.get("/api/v1/analytics/summary", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    for key in (
        "total_surveys",
        "total_detections",
        "total_reports",
        "class_distribution",
        "priority_distribution",
        "review_funnel",
        "detection_trend",
    ):
        assert key in body
    for key in ("pending", "unknown", "accepted_artificial", "rejected_natural"):
        assert key in body["review_funnel"]
