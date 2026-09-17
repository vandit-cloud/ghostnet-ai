from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.limiter import limiter
from app.core.config import get_settings
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    CurrentUser,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    RefreshRequest,
    ResetPasswordRequest,
)
from app.services import auth_service

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
@limiter.limit(settings.rate_limit_login)
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user, access_token, refresh_token = auth_service.authenticate(db, payload.username, payload.password, request)
    return LoginResponse(
        access_token=access_token, refresh_token=refresh_token, display_name=user.display_name, role=user.role
    )


@router.post("/refresh", response_model=LoginResponse)
def refresh(request: Request, payload: RefreshRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user, access_token, refresh_token = auth_service.refresh_access_token(db, payload.refresh_token, request)
    return LoginResponse(
        access_token=access_token, refresh_token=refresh_token, display_name=user.display_name, role=user.role
    )


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    payload: LogoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    auth_service.logout(db, payload.refresh_token, current_user, request)


@router.post("/reset-password", status_code=204)
def reset_password(request: Request, payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> None:
    auth_service.reset_password(db, payload.token, payload.new_password, request)


@router.post("/change-password", status_code=204)
def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    auth_service.change_own_password(db, current_user, payload.current_password, payload.new_password, request)


@router.get("/me", response_model=CurrentUser)
def me(current_user: User = Depends(get_current_user)) -> CurrentUser:
    return CurrentUser(
        username=current_user.username,
        display_name=current_user.display_name,
        role=current_user.role,
        is_active=current_user.is_active,
    )
