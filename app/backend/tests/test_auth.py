import uuid

import pytest

from app.core.errors import ApiError
from app.core.security import hash_password
from app.models.user import User
from app.services import auth_service


def test_login_success(client, db_session):
    db_session.add(User(username="alice", password_hash=hash_password("secret123"), display_name="Alice"))
    db_session.commit()

    response = client.post("/api/v1/auth/login", json={"username": "alice", "password": "secret123"})
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["display_name"] == "Alice"
    assert body["role"] == "operator"


def test_login_invalid_credentials(client):
    response = client.post("/api/v1/auth/login", json={"username": "nobody", "password": "wrong"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_protected_route_requires_auth(client):
    response = client.get("/api/v1/surveys")
    assert response.status_code == 401


def test_refresh_and_logout_flow(client, db_session):
    db_session.add(User(username="bob", password_hash=hash_password("secret123"), display_name="Bob"))
    db_session.commit()

    login = client.post("/api/v1/auth/login", json={"username": "bob", "password": "secret123"})
    refresh_token = login.json()["refresh_token"]

    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refreshed.status_code == 200
    new_access_token = refreshed.json()["access_token"]
    new_refresh_token = refreshed.json()["refresh_token"]

    # Rotation: the original refresh token no longer works.
    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert replay.status_code == 401

    logout = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {new_access_token}"},
        json={"refresh_token": new_refresh_token},
    )
    assert logout.status_code == 204

    after_logout = client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh_token})
    assert after_logout.status_code == 401


def test_account_lockout_after_repeated_failures(db_session):
    """Service-layer, bypassing HTTP/slowapi -- isolates the brute-force
    lockout (audit-log-derived) from the separate IP rate limit tested below."""
    username = f"lockout-{uuid.uuid4().hex[:8]}"
    db_session.add(User(username=username, password_hash=hash_password("correct-pass"), display_name=username))
    db_session.commit()

    for _ in range(5):
        with pytest.raises(ApiError) as excinfo:
            auth_service.authenticate(db_session, username, "wrong-pass")
        assert excinfo.value.code == "INVALID_CREDENTIALS"

    with pytest.raises(ApiError) as excinfo:
        auth_service.authenticate(db_session, username, "correct-pass")
    assert excinfo.value.code == "TOO_MANY_ATTEMPTS"
    assert excinfo.value.status_code == 429


def test_change_own_password(client, db_session):
    username = f"changer-{uuid.uuid4().hex[:8]}"
    db_session.add(User(username=username, password_hash=hash_password("old-password1"), display_name=username))
    db_session.commit()

    login = client.post("/api/v1/auth/login", json={"username": username, "password": "old-password1"})
    access_token = login.json()["access_token"]

    changed = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"current_password": "old-password1", "new_password": "new-password2"},
    )
    assert changed.status_code == 204

    wrong_current = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"current_password": "still-old", "new_password": "whatever2"},
    )
    assert wrong_current.status_code == 401

    relogin = client.post("/api/v1/auth/login", json={"username": username, "password": "new-password2"})
    assert relogin.status_code == 200


def test_login_endpoint_rate_limited_by_ip(client):
    # Distinct usernames per request so this exercises the IP-keyed slowapi
    # limit specifically, not the per-username lockout above.
    responses = [
        client.post("/api/v1/auth/login", json={"username": f"rl-{i}-{uuid.uuid4().hex[:6]}", "password": "x"})
        for i in range(8)
    ]
    assert any(r.status_code == 429 for r in responses)
