import logging
import shutil
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models.detection import Detection
from app.models.detection_review import DetectionReview
from app.models.enums import ReviewStatus, SurveyStatus
from app.models.survey import Survey
from app.models.survey_file import SurveyFile
from app.models.processing_job import ProcessingJob
from app.schemas.survey import SurveyCreate, SurveyUpdate
from app.storage.local import StorageBackend

logger = logging.getLogger("ghostnet.survey")


def create_survey(db: Session, payload: SurveyCreate, created_by_user_id: uuid.UUID | None = None) -> Survey:
    survey = Survey(
        name=payload.name,
        source=payload.source,
        sonar_type=payload.sonar_type,
        created_by_user_id=created_by_user_id,
    )
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


def delete_survey(db: Session, survey_id: uuid.UUID, storage: StorageBackend | None = None) -> None:
    """Delete a survey and everything hanging off it.

    Hard delete, deliberately. Every child table declares
    ``ondelete="CASCADE"`` on its survey_id, so the database removes files,
    frames, detections, jobs and reports in one statement -- and
    detection_reviews cascade off detections, so the review audit trail goes
    too. That is the accepted cost: the survey is being erased as a mistaken
    upload, and an audit trail for a survey that no longer exists has nothing
    to attest to. The UI gates this behind a typed-name confirmation.

    Two things the cascade cannot do, done here first:

    1. Stop a job that is still running. Its asyncio task holds its own Session
       and would keep writing to a row the delete has removed, which surfaces
       as a stream of foreign-key errors in the log after an apparently
       successful delete.
    2. Remove the uploaded bytes. Rows cascade; files on disk do not, and a
       storage root that only ever grows is how a demo machine runs out of
       space mid-run.
    """
    survey = get_survey_or_404(db, survey_id)

    # Import here: processing_service imports nothing from this module today,
    # but survey_service is imported by half the API and a cycle would be easy
    # to introduce at the top of the file.
    from app.services import processing_service

    for job in db.query(ProcessingJob).filter(ProcessingJob.survey_id == survey_id).all():
        processing_service.cancel_running_task(job.id)

    db.delete(survey)
    db.commit()

    if storage is not None:
        try:
            survey_dir = storage.path_for(str(survey_id))
            if survey_dir.is_dir():
                shutil.rmtree(survey_dir)
        except Exception:
            # The rows are already gone and that is the part that has to be
            # atomic. Orphaned bytes are a cleanup problem, not a failed
            # request -- do not turn a successful delete into a 500.
            logger.exception("Could not remove storage for deleted survey %s", survey_id)


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
