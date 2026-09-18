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


def _headers_for_role(role):
    """A token for a user with a specific role.

    conftest's `auth_headers` is always an OPERATOR, which is exactly the role
    that is ALLOWED to mutate surveys -- so it can never catch a missing role
    check. Testing authorization needs a principal that should be refused.
    """
    import uuid as _uuid

    from app.core import db as db_module
    from app.core.security import create_access_token, hash_password
    from app.models.user import User

    session = db_module.SessionLocal()
    username = f"viewer-{_uuid.uuid4().hex[:8]}"
    session.add(
        User(
            username=username,
            password_hash=hash_password("password123"),
            display_name="Read Only",
            role=role,
        )
    )
    session.commit()
    session.close()
    return {"Authorization": f"Bearer {create_access_token(username)}"}


def test_viewer_cannot_delete_or_modify_a_survey(client, auth_headers):
    """Read-only roles must not reach the destructive endpoints.

    DELETE /surveys/{id} is the single most destructive call in the API -- it
    cascades to every file, frame, detection and review the survey owns -- and
    it shipped with no role check at all beyond the router's "is signed in",
    so any authenticated VIEWER could issue it and leave no audit entry. PATCH
    was equally open: a viewer could rename a survey or force its status.
    """
    from app.models.enums import Role

    survey = client.post(
        "/api/v1/surveys", json={"name": "Protected"}, headers=auth_headers
    ).json()
    viewer = _headers_for_role(Role.VIEWER)

    assert client.delete(f"/api/v1/surveys/{survey['id']}", headers=viewer).status_code == 403
    assert (
        client.patch(
            f"/api/v1/surveys/{survey['id']}", json={"name": "Renamed"}, headers=viewer
        ).status_code
        == 403
    )

    # Still there, still called what it was called.
    still = client.get(f"/api/v1/surveys/{survey['id']}", headers=auth_headers)
    assert still.status_code == 200
    assert still.json()["name"] == "Protected"


def test_operator_can_still_delete_a_survey(client, auth_headers):
    """The guard must not have locked out the role that is supposed to do this."""
    survey = client.post(
        "/api/v1/surveys", json={"name": "Disposable"}, headers=auth_headers
    ).json()
    assert client.delete(f"/api/v1/surveys/{survey['id']}", headers=auth_headers).status_code == 204
    assert client.get(f"/api/v1/surveys/{survey['id']}", headers=auth_headers).status_code == 404
