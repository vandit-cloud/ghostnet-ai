from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.schemas.analytics import AnalyticsSummary
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"], dependencies=[Depends(get_current_user)])


@router.get("/summary", response_model=AnalyticsSummary)
def get_analytics_summary(db: Session = Depends(get_db)) -> AnalyticsSummary:
    return analytics_service.build_analytics_summary(db)
