from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.auth import CurrentUser, LoginRequest, LoginResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user, token = auth_service.authenticate(db, payload.username, payload.password)
    return LoginResponse(access_token=token, display_name=user.display_name)


@router.get("/me", response_model=CurrentUser)
def me(current_user: User = Depends(get_current_user)) -> CurrentUser:
    return CurrentUser(username=current_user.username, display_name=current_user.display_name)
