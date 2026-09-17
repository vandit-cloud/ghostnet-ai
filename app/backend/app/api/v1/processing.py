import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import get_current_user, require_roles
from app.core.errors import ApiError
from app.models.enums import Role
from app.models.user import User
from app.schemas.processing import ProcessingJobOut, ProcessingStartRequest
from app.services import audit_service, processing_service, survey_service

settings = get_settings()
router = APIRouter(tags=["processing"], dependencies=[Depends(get_current_user)])


@router.post("/surveys/{survey_id}/process", response_model=ProcessingJobOut, status_code=202)
async def start_processing(
    request: Request,
    survey_id: uuid.UUID,
    payload: ProcessingStartRequest = ProcessingStartRequest(),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN, Role.OPERATOR)),
) -> ProcessingJobOut:
    survey_service.get_survey_or_404(db, survey_id)

    active_count = processing_service.count_active_jobs_for_user(db, user.id)
    if active_count >= settings.max_concurrent_jobs_per_user:
        raise ApiError(
            429,
            "JOB_QUOTA_EXCEEDED",
            f"You already have {active_count} survey(s) processing. Wait for one to "
            f"finish before starting another (limit: {settings.max_concurrent_jobs_per_user}).",
        )

    # force_restart was declared on the request schema and never read, so a
    # second Process on a finished survey silently appended a duplicate set of
    # detections instead of being refused.
    job = processing_service.start_processing(db, survey_id, payload.force_restart)
    audit_service.log(
        db,
        actor=user,
        action="processing.started",
        entity_type="survey",
        entity_id=str(survey_id),
        detail={"job_id": str(job.id), "force_restart": payload.force_restart},
        request=request,
    )
    return ProcessingJobOut.model_validate(job)


@router.get("/jobs/{job_id}", response_model=ProcessingJobOut)
def get_job(job_id: uuid.UUID, db: Session = Depends(get_db)) -> ProcessingJobOut:
    job = processing_service.get_job_or_404(db, job_id)
    return ProcessingJobOut.model_validate(job)


@router.get("/surveys/{survey_id}/jobs/active", response_model=ProcessingJobOut | None)
def get_active_job(survey_id: uuid.UUID, db: Session = Depends(get_db)) -> ProcessingJobOut | None:
    job = processing_service.get_active_job_for_survey(db, survey_id)
    return ProcessingJobOut.model_validate(job) if job else None


@router.get("/surveys/{survey_id}/jobs/latest", response_model=ProcessingJobOut | None)
def get_latest_job(survey_id: uuid.UUID, db: Session = Depends(get_db)) -> ProcessingJobOut | None:
    """The survey's most recent job regardless of status -- see A1 in
    docs/KNOWN_ISSUES.md. Unlike /jobs/active this keeps answering after the
    run finishes, which is what lets the processing page show a result instead
    of claiming nothing ran. 404s for a survey that does not exist rather than
    returning null, so a bad id is distinguishable from "never processed"."""
    survey_service.get_survey_or_404(db, survey_id)
    job = processing_service.get_latest_job_for_survey(db, survey_id)
    return ProcessingJobOut.model_validate(job) if job else None


@router.get("/surveys/{survey_id}/jobs", response_model=list[ProcessingJobOut])
def list_survey_jobs(
    survey_id: uuid.UUID,
    limit: int = Query(10, ge=1, le=processing_service.MAX_JOB_HISTORY),
    db: Session = Depends(get_db),
) -> list[ProcessingJobOut]:
    """This survey's run history, newest first.

    `/jobs/latest` returns only the current run, so a re-processed survey could
    not say how this run compares with the one it replaced -- the previous job
    row was there but unreachable. 404s for an unknown survey rather than
    returning an empty list, so a bad id stays distinguishable from a survey
    that has simply never been processed.
    """
    survey_service.get_survey_or_404(db, survey_id)
    jobs = processing_service.list_jobs_for_survey(db, survey_id, limit)
    return [ProcessingJobOut.model_validate(j) for j in jobs]


@router.post("/jobs/{job_id}/cancel", response_model=ProcessingJobOut)
def cancel_job(
    request: Request,
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN, Role.OPERATOR)),
) -> ProcessingJobOut:
    job = processing_service.cancel_job(db, job_id)
    audit_service.log(
        db, actor=user, action="processing.cancelled", entity_type="job", entity_id=str(job_id), request=request
    )
    return ProcessingJobOut.model_validate(job)
