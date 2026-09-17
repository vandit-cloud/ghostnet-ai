import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import Priority, ReviewStatus, Uncertainty


class MapMarker(BaseModel):
    detection_id: uuid.UUID
    detection_ref: str
    detection_class: str
    latitude: float
    longitude: float
    priority: Priority
    review_status: ReviewStatus
    calibrated_confidence: float | None
    uncertainty: Uncertainty | None
    position_error_m: float | None
    depth: float | None
    created_at: datetime


class MapBounds(BaseModel):
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float


class TrackPoint(BaseModel):
    latitude: float
    longitude: float
    timestamp: datetime | None
    range: float | None = None


class SurveyMapOut(BaseModel):
    survey_id: uuid.UUID
    bounds: MapBounds | None
    markers: list[MapMarker]
    track: list[TrackPoint]
