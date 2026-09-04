"""Frozen AI input/output/error contract shared with Member 1 (spec sections 7-9)."""

from pydantic import BaseModel, ConfigDict, Field


class AIFrameMetadata(BaseModel):
    timestamp: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    heading: float | None = None
    depth: float | None = None
    range: float | None = None


class AIInferRequest(BaseModel):
    survey_id: str
    frame_id: str
    image_reference: str
    metadata: AIFrameMetadata


class AIDimensions(BaseModel):
    width: float | None = None
    length: float | None = None
    status: str | None = None


class AIDetection(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    detection_id: str
    class_: str = Field(alias="class")
    raw_score: float | None = None
    calibrated_confidence: float | None = None
    uncertainty: str | None = None
    bbox: list[float] | None = None
    mask: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    position_error_m: float | None = None
    localization: str | None = None
    dimensions: AIDimensions | None = None
    review_status: str | None = None
    model_version: str | None = None
    evidence_summary: dict = {}


class AIInferResponse(BaseModel):
    survey_id: str
    frame_id: str
    detections: list[AIDetection]


class AIErrorResponse(BaseModel):
    status: str
    frame_id: str
    error_code: str
    message: str
