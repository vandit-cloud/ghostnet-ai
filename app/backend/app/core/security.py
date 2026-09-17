import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings

settings = get_settings()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(subject: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expires_minutes)
    payload = {"sub": subject, "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload.get("sub")
    except JWTError:
        return None


def _new_opaque_token() -> tuple[str, str, datetime]:
    """A random opaque token plus its stored hash and the current time.

    Used for both refresh tokens and admin-issued password-reset tokens.
    Only the SHA-256 hash is ever persisted -- same reasoning as bcrypt for
    passwords, minus the deliberate slowness, which isn't needed for a
    high-entropy random token that can't be brute-forced offline the way a
    human-chosen password can.
    """
    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return raw, token_hash, datetime.now(timezone.utc)


def hash_opaque_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def new_refresh_token() -> tuple[str, str, datetime, datetime]:
    """Returns (raw_token, token_hash, created_at, expires_at)."""
    raw, token_hash, created_at = _new_opaque_token()
    expires_at = created_at + timedelta(days=settings.refresh_token_expires_days)
    return raw, token_hash, created_at, expires_at


def new_password_reset_token() -> tuple[str, str, datetime, datetime]:
    """Returns (raw_token, token_hash, created_at, expires_at)."""
    raw, token_hash, created_at = _new_opaque_token()
    expires_at = created_at + timedelta(minutes=settings.password_reset_expires_minutes)
    return raw, token_hash, created_at, expires_at
