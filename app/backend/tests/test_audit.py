"""There is no /audit viewing endpoint (it was removed along with the Audit
page); audit_service.log() still runs on every login/RBAC/survey/etc. action,
so these tests check the AuditLog table directly rather than through an API."""

import uuid

from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.user import User


def test_survey_creation_is_audited(client, db_session, auth_headers, auth_identity):
    created = client.post("/api/v1/surveys", headers=auth_headers, json={"name": "Audited Survey"})
    assert created.status_code == 201
    survey_id = created.json()["id"]

    entries = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "survey.created", AuditLog.entity_id == survey_id)
        .all()
    )
    assert len(entries) == 1
    assert entries[0].actor_username == auth_identity["username"]


def test_failed_login_is_audited_without_leaking_the_password(client, db_session):
    victim_username = f"victim-{uuid.uuid4().hex[:8]}"
    db_session.add(
        User(username=victim_username, password_hash=hash_password("correct-horse"), display_name=victim_username)
    )
    db_session.commit()

    response = client.post("/api/v1/auth/login", json={"username": victim_username, "password": "wrong-guess"})
    assert response.status_code == 401

    entries = db_session.query(AuditLog).filter(AuditLog.actor_username == victim_username).all()
    login_attempts = [e for e in entries if e.action == "auth.login"]
    assert len(login_attempts) == 1
    assert login_attempts[0].outcome == "failure"
    assert "wrong-guess" not in str(login_attempts[0].detail)
