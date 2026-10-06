import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import JobStage, JobStatus


class ProcessingStartRequest(BaseModel):
    force_restart: bool = False


class ProcessingJobOut(BaseModel):
    id: uuid.UUID
    survey_id: uuid.UUID
    type: str
    status: JobStatus
    stage: JobStage
    progress: int
    frames_total: int
    frames_processed: int
    frames_failed: int
    detections_found: int
    started_at: datetime | None
    completed_at: datetime | None
    error_summary: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SurveyFrameOut(BaseModel):
    """One frame of a survey, positioned in processing order."""

    id: uuid.UUID
    index: int
    frame_id: str
