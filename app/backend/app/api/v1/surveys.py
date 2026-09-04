import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.common import Page
from app.schemas.survey import SurveyCreate, SurveyDetailOut, SurveyOut, SurveyUpdate
from app.services import survey_service

router = APIRouter(prefix="/surveys", tags=["surveys"], dependencies=[Depends(get_current_user)])


def _to_out(db: Session, survey, detail: bool = False):
    counts = survey_service.survey_counts(db, survey.id)
    data = {
        "id": survey.id,
        "name": survey.name,
        "source": survey.source,
        "sonar_type": survey.sonar_type,
        "status": survey.status,
        "created_at": survey.created_at,
        "updated_at": survey.updated_at,
        "file_count": counts["file_count"],
        "processed_count": counts["processed_count"],
        "detection_count": counts["detection_count"],
    }
    if detail:
        data["review_count"] = counts["review_count"]
        return SurveyDetailOut(**data)
    return SurveyOut(**data)


@router.post("", response_model=SurveyOut, status_code=201)
def create_survey(payload: SurveyCreate, db: Session = Depends(get_db)) -> SurveyOut:
    survey = survey_service.create_survey(db, payload)
    return _to_out(db, survey)


@router.get("", response_model=Page[SurveyOut])
def list_surveys(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> Page[SurveyOut]:
    surveys, total = survey_service.list_surveys(db, page, page_size)
    return Page(items=[_to_out(db, s) for s in surveys], page=page, page_size=page_size, total=total)


@router.get("/{survey_id}", response_model=SurveyDetailOut)
def get_survey(survey_id: uuid.UUID, db: Session = Depends(get_db)) -> SurveyDetailOut:
    survey = survey_service.get_survey_or_404(db, survey_id)
    return _to_out(db, survey, detail=True)


@router.patch("/{survey_id}", response_model=SurveyDetailOut)
def update_survey(survey_id: uuid.UUID, payload: SurveyUpdate, db: Session = Depends(get_db)) -> SurveyDetailOut:
    survey = survey_service.update_survey(db, survey_id, payload)
    return _to_out(db, survey, detail=True)
