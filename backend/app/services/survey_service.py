import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models.detection import Detection
from app.models.detection_review import DetectionReview
from app.models.enums import ReviewStatus, SurveyStatus
from app.models.survey import Survey
from app.models.survey_file import SurveyFile
from app.schemas.survey import SurveyCreate, SurveyUpdate


def create_survey(db: Session, payload: SurveyCreate) -> Survey:
    survey = Survey(name=payload.name, source=payload.source, sonar_type=payload.sonar_type)
    db.add(survey)
    db.commit()
    db.refresh(survey)
    return survey


def get_survey_or_404(db: Session, survey_id: uuid.UUID) -> Survey:
    survey = db.get(Survey, survey_id)
    if not survey:
        raise ApiError(404, "SURVEY_NOT_FOUND", "Survey was not found.")
    return survey


def list_surveys(db: Session, page: int, page_size: int) -> tuple[list[Survey], int]:
    total = db.scalar(select(func.count()).select_from(Survey)) or 0
    surveys = (
        db.query(Survey)
        .order_by(Survey.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return surveys, total


def update_survey(db: Session, survey_id: uuid.UUID, payload: SurveyUpdate) -> Survey:
    survey = get_survey_or_404(db, survey_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(survey, field, value)
    db.commit()
    db.refresh(survey)
    return survey


def survey_counts(db: Session, survey_id: uuid.UUID) -> dict:
    file_count = db.scalar(
        select(func.count()).select_from(SurveyFile).where(SurveyFile.survey_id == survey_id)
    ) or 0
    processed_count = db.scalar(
        select(func.count())
        .select_from(SurveyFile)
        .where(SurveyFile.survey_id == survey_id, SurveyFile.validation_status == "VALID")
    ) or 0
    detection_count = db.scalar(
        select(func.count()).select_from(Detection).where(Detection.survey_id == survey_id)
    ) or 0
    review_count = db.scalar(
        select(func.count())
        .select_from(Detection)
        .where(Detection.survey_id == survey_id, Detection.review_status == ReviewStatus.PENDING)
    ) or 0
    return {
        "file_count": file_count,
        "processed_count": processed_count,
        "detection_count": detection_count,
        "review_count": review_count,
    }
