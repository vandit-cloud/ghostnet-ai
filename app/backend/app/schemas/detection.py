import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import Priority, ReviewStatus, Uncertainty


class BBox(BaseModel):
    x: float | None
    y: float | None
    w: float | None
    h: float | None


class Dimensions(BaseModel):
    width: float | None
    length: float | None
    area: float | None
    status: str | None


class DetectionOut(BaseModel):
    id: uuid.UUID
    detection_ref: str
    survey_id: uuid.UUID
    frame_id: uuid.UUID
    detection_class: str
    raw_score: float | None
    calibrated_confidence: float | None
    uncertainty: Uncertainty | None
    bbox: BBox
    mask_reference: str | None
    latitude: float | None
    longitude: float | None
    position_error_m: float | None
    localization_method: str | None
    depth: float | None
    dimensions: Dimensions
    priority: Priority
    review_status: ReviewStatus
    model_version: str | None
    evidence_summary: dict
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DetectionReviewIn(BaseModel):
    decision: ReviewStatus
    reviewer: str | None = None
    note: str | None = None


class DetectionReviewOut(BaseModel):
    id: uuid.UUID
    detection_id: uuid.UUID
    reviewer: str | None
    decision: ReviewStatus
    note: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
