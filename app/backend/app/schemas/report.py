import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import ReportFormat, ReportStatus, ReportType


class ReportCreate(BaseModel):
    survey_id: uuid.UUID
    type: ReportType
    format: ReportFormat
    filters: dict = {}
    detection_id: uuid.UUID | None = None


class ReportOut(BaseModel):
    id: uuid.UUID
    survey_id: uuid.UUID
    type: ReportType
    format: ReportFormat
    status: ReportStatus
    filters: dict
    error_summary: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
