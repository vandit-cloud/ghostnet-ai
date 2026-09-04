import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.schemas.processing import ProcessingJobOut, ProcessingStartRequest
from app.services import processing_service, survey_service

router = APIRouter(tags=["processing"], dependencies=[Depends(get_current_user)])


@router.post("/surveys/{survey_id}/process", response_model=ProcessingJobOut, status_code=202)
async def start_processing(
    survey_id: uuid.UUID,
    payload: ProcessingStartRequest = ProcessingStartRequest(),
    db: Session = Depends(get_db),
) -> ProcessingJobOut:
    survey_service.get_survey_or_404(db, survey_id)
    job = processing_service.start_processing(db, survey_id)
    return ProcessingJobOut.model_validate(job)


@router.get("/jobs/{job_id}", response_model=ProcessingJobOut)
def get_job(job_id: uuid.UUID, db: Session = Depends(get_db)) -> ProcessingJobOut:
    job = processing_service.get_job_or_404(db, job_id)
    return ProcessingJobOut.model_validate(job)


@router.get("/surveys/{survey_id}/jobs/active", response_model=ProcessingJobOut | None)
def get_active_job(survey_id: uuid.UUID, db: Session = Depends(get_db)) -> ProcessingJobOut | None:
    job = processing_service.get_active_job_for_survey(db, survey_id)
    return ProcessingJobOut.model_validate(job) if job else None


@router.post("/jobs/{job_id}/cancel", response_model=ProcessingJobOut)
def cancel_job(job_id: uuid.UUID, db: Session = Depends(get_db)) -> ProcessingJobOut:
    job = processing_service.cancel_job(db, job_id)
    return ProcessingJobOut.model_validate(job)
