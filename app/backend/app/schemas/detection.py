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
    # Which survey this came from, resolved for display. The detections list is
    # reachable from the sidebar with no survey scope at all, and without a name
    # every survey's rows arrive in one undifferentiated table -- see B2 in
    # docs/KNOWN_ISSUES.md.
    survey_name: str | None = None
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
    # No `reviewer` field: the server takes it from the access token. A client
    # cannot name the reviewer, and an extra key here is ignored rather than
    # honoured.
    decision: ReviewStatus
    note: str | None = None


class DetectionReviewOut(BaseModel):
    id: uuid.UUID
    detection_id: uuid.UUID
    reviewer: str | None
    decision: ReviewStatus
    note: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
