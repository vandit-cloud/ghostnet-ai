from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import ApiError
from app.core.security import decode_access_token
from app.models.enums import Role
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise ApiError(401, "NOT_AUTHENTICATED", "Authentication is required.")

    username = decode_access_token(credentials.credentials)
    if not username:
        raise ApiError(401, "INVALID_TOKEN", "Session token is invalid or expired.")

    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise ApiError(401, "INVALID_TOKEN", "Session token is invalid or expired.")

    if not user.is_active:
        raise ApiError(401, "ACCOUNT_DISABLED", "This account has been deactivated.")

    return user


def require_roles(*roles: Role):
    """Dependency factory: 403s unless the authenticated user's role is one of
    `roles`. Authorization is enforced here, on the backend -- hiding a
    frontend button is never sufficient (spec E23)."""

    def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise ApiError(
                403,
                "FORBIDDEN",
                f"Role '{current_user.role}' is not permitted to perform this action.",
            )
        return current_user

    return _check
