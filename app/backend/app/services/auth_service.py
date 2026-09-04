from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User

settings = get_settings()


def authenticate(db: Session, username: str, password: str) -> tuple[User, str]:
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        raise ApiError(401, "INVALID_CREDENTIALS", "Username or password is incorrect.")
    token = create_access_token(user.username)
    return user, token


def ensure_seed_admin(db: Session) -> None:
    existing = db.query(User).filter(User.username == settings.seed_admin_username).first()
    if existing:
        return
    user = User(
        username=settings.seed_admin_username,
        password_hash=hash_password(settings.seed_admin_password),
        display_name="Survey Operator",
    )
    db.add(user)
    db.commit()
