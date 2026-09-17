from datetime import datetime, timezone

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.security import (
    create_access_token,
    hash_opaque_token,
    hash_password,
    new_refresh_token,
    verify_password,
)
from app.models.enums import Role
from app.models.password_reset_token import PasswordResetToken
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services import audit_service

settings = get_settings()


def authenticate(db: Session, username: str, password: str, request: Request | None = None) -> tuple[User, str, str]:
    """Returns (user, access_token, raw_refresh_token).

    Brute-force protection: N failed logins for this username inside the
    trailing window blocks further attempts, derived from audit_logs rather
    than a second counter table.
    """
    recent_failures = audit_service.count_recent_login_failures(db, username, settings.login_failure_window_minutes)
    if recent_failures >= settings.login_failure_limit:
        raise ApiError(
            429,
            "TOO_MANY_ATTEMPTS",
            f"Too many failed login attempts for this account. Try again in "
            f"{settings.login_failure_window_minutes} minutes.",
        )

    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash) or not user.is_active:
        audit_service.log(
            db,
            actor=None,
            actor_username=username,
            action="auth.login",
            entity_type="user",
            outcome="failure",
            request=request,
        )
        raise ApiError(401, "INVALID_CREDENTIALS", "Username or password is incorrect.")

    access_token = create_access_token(user.username)
    raw_refresh, refresh_hash, _created_at, expires_at = new_refresh_token()
    db.add(RefreshToken(user_id=user.id, token_hash=refresh_hash, expires_at=expires_at))

    audit_service.log(db, actor=user, action="auth.login", entity_type="user", entity_id=str(user.id), request=request)
    db.commit()
    return user, access_token, raw_refresh


def refresh_access_token(db: Session, raw_refresh_token: str, request: Request | None = None) -> tuple[User, str, str]:
    """Returns (user, new_access_token, new_raw_refresh_token). Rotates the
    refresh token: the presented one is revoked and a new one issued, so a
    stolen-but-unused token can't be replayed indefinitely."""
    token_hash = hash_opaque_token(raw_refresh_token)
    token = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    now = datetime.now(timezone.utc)
    if not token or token.revoked_at is not None or token.expires_at < now:
        raise ApiError(401, "INVALID_REFRESH_TOKEN", "Refresh token is invalid, expired or revoked.")

    user = db.get(User, token.user_id)
    if not user or not user.is_active:
        raise ApiError(401, "INVALID_REFRESH_TOKEN", "Refresh token is invalid, expired or revoked.")

    token.revoked_at = now
    new_raw, new_hash, _created_at, new_expires_at = new_refresh_token()
    db.add(RefreshToken(user_id=user.id, token_hash=new_hash, expires_at=new_expires_at))

    access_token = create_access_token(user.username)
    audit_service.log(db, actor=user, action="auth.refresh", entity_type="user", entity_id=str(user.id), request=request)
    db.commit()
    return user, access_token, new_raw


def logout(db: Session, raw_refresh_token: str | None, actor: User, request: Request | None = None) -> None:
    if raw_refresh_token:
        token_hash = hash_opaque_token(raw_refresh_token)
        token = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
        if token and token.revoked_at is None:
            token.revoked_at = datetime.now(timezone.utc)
    audit_service.log(db, actor=actor, action="auth.logout", entity_type="user", entity_id=str(actor.id), request=request)
    db.commit()


def reset_password(db: Session, raw_token: str, new_password: str, request: Request | None = None) -> None:
    token_hash = hash_opaque_token(raw_token)
    token = db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == token_hash).first()
    now = datetime.now(timezone.utc)
    if not token or token.used_at is not None or token.expires_at < now:
        raise ApiError(400, "INVALID_RESET_TOKEN", "Reset token is invalid, expired or already used.")

    user = db.get(User, token.user_id)
    if not user:
        raise ApiError(400, "INVALID_RESET_TOKEN", "Reset token is invalid, expired or already used.")

    user.password_hash = hash_password(new_password)
    token.used_at = now
    # A password reset invalidates any standing sessions -- otherwise a
    # compromised account stays reachable via a refresh token minted before
    # the reset.
    db.query(RefreshToken).filter(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)).update(
        {"revoked_at": now}
    )
    audit_service.log(
        db, actor=user, action="auth.password_reset_completed", entity_type="user", entity_id=str(user.id), request=request
    )
    db.commit()


def change_own_password(
    db: Session, actor: User, current_password: str, new_password: str, request: Request | None = None
) -> None:
    if not verify_password(current_password, actor.password_hash):
        raise ApiError(401, "INVALID_CREDENTIALS", "Current password is incorrect.")
    actor.password_hash = hash_password(new_password)
    now = datetime.now(timezone.utc)
    # Same reasoning as an admin-issued reset: changing the password
    # invalidates standing refresh tokens rather than leaving old ones live.
    db.query(RefreshToken).filter(RefreshToken.user_id == actor.id, RefreshToken.revoked_at.is_(None)).update(
        {"revoked_at": now}
    )
    audit_service.log(
        db, actor=actor, action="auth.password_changed", entity_type="user", entity_id=str(actor.id), request=request
    )
    db.commit()


def ensure_seed_admin(db: Session) -> None:
    existing = db.query(User).filter(User.username == settings.seed_admin_username).first()
    if existing:
        # Reconciliation for a seed user created by an earlier version of this
        # app, before RBAC existed: the row is already there, so the "create"
        # branch below never runs and it would otherwise stay stuck at
        # whatever the role/is_active column defaults were at migration time.
        if existing.role != Role.ADMIN or not existing.is_active:
            existing.role = Role.ADMIN
            existing.is_active = True
            db.commit()
        return
    user = User(
        username=settings.seed_admin_username,
        password_hash=hash_password(settings.seed_admin_password),
        display_name="Survey Operator",
        role=Role.ADMIN,
        is_active=True,
    )
    db.add(user)
    db.commit()
