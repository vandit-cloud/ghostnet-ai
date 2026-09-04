from app.core.security import hash_password
from app.models.user import User


def test_login_success(client, db_session):
    db_session.add(User(username="alice", password_hash=hash_password("secret123"), display_name="Alice"))
    db_session.commit()

    response = client.post("/api/v1/auth/login", json={"username": "alice", "password": "secret123"})
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["display_name"] == "Alice"


def test_login_invalid_credentials(client):
    response = client.post("/api/v1/auth/login", json={"username": "nobody", "password": "wrong"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_protected_route_requires_auth(client):
    response = client.get("/api/v1/surveys")
    assert response.status_code == 401
