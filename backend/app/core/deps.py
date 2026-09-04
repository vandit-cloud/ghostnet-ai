from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import ApiError
from app.core.security import decode_access_token
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

    return user
