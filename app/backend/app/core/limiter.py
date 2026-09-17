from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.core.security import decode_access_token

settings = get_settings()


def _rate_limit_key(request: Request) -> str:
    """Per-user where a valid token is presented, falling back to IP for
    unauthenticated requests (login, refresh, reset-password)."""
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        username = decode_access_token(auth_header[7:])
        if username:
            return f"user:{username}"
    return get_remote_address(request)


# In-memory store: correct for the single-uvicorn-worker deployment this repo
# ships (docker-compose.yml has no Redis). A multi-worker/multi-instance
# deployment would need a shared backend (slowapi supports Redis) instead.
limiter = Limiter(key_func=_rate_limit_key, default_limits=[settings.rate_limit_default])
