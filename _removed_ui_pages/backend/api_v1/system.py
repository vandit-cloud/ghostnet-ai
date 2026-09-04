from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import get_current_user
from app.schemas.system import SystemConfig, SystemStatus
from app.services import system_service

router = APIRouter(prefix="/system", tags=["system"], dependencies=[Depends(get_current_user)])


@router.get("/status", response_model=SystemStatus)
def get_status(db: Session = Depends(get_db)) -> SystemStatus:
    return system_service.get_system_status(db)


@router.get("/config", response_model=SystemConfig)
def get_config() -> SystemConfig:
    settings = get_settings()
    return SystemConfig(
        app_name=settings.app_name,
        max_upload_size_mb=settings.max_upload_size_mb,
        allowed_upload_extensions=list(settings.allowed_upload_extensions),
    )
