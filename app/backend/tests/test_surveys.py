def test_create_and_list_survey(client, auth_headers):
    response = client.post(
        "/api/v1/surveys",
        json={"name": "Gulf Survey 1", "source": "vessel-a", "sonar_type": "side-scan"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    survey = response.json()
    assert survey["name"] == "Gulf Survey 1"
    assert survey["status"] == "UPLOADED"

    response = client.get("/api/v1/surveys", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert any(s["id"] == survey["id"] for s in body["items"])


def test_get_survey_not_found(client, auth_headers):
    response = client.get("/api/v1/surveys/00000000-0000-0000-0000-000000000000", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SURVEY_NOT_FOUND"


def test_update_survey(client, auth_headers):
    created = client.post("/api/v1/surveys", json={"name": "Survey X"}, headers=auth_headers).json()
    response = client.patch(
        f"/api/v1/surveys/{created['id']}", json={"status": "ARCHIVED"}, headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ARCHIVED"
