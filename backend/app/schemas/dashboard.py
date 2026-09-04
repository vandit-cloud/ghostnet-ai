import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import JobStatus, SurveyStatus


class ClassCount(BaseModel):
    detection_class: str
    count: int


class TrendPoint(BaseModel):
    date: str
    count: int


class RecentDetection(BaseModel):
    id: uuid.UUID
    detection_ref: str
    detection_class: str
    calibrated_confidence: float | None
    priority: str
    created_at: datetime


class CurrentSurvey(BaseModel):
    id: uuid.UUID
    name: str
    status: SurveyStatus
    updated_at: datetime


class ActiveJobSummary(BaseModel):
    id: uuid.UUID
    survey_id: uuid.UUID
    status: JobStatus
    stage: str
    progress: int


class DashboardSummary(BaseModel):
    current_survey: CurrentSurvey | None
    active_job: ActiveJobSummary | None
    last_updated: datetime | None
    frames_processed: int
    candidates: int
    confirmed_artificial: int
    high_priority: int
    needs_review: int
    rejected_natural: int
    class_distribution: list[ClassCount]
    detection_trend: list[TrendPoint]
    recent_detections: list[RecentDetection]
