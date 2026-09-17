from pydantic import BaseModel

from app.schemas.dashboard import ClassCount, TrendPoint


class PriorityCount(BaseModel):
    priority: str
    count: int


class ReviewFunnel(BaseModel):
    pending: int
    unknown: int
    accepted_artificial: int
    rejected_natural: int


class AnalyticsSummary(BaseModel):
    total_surveys: int
    total_detections: int
    total_reports: int
    average_calibrated_confidence: float | None
    class_distribution: list[ClassCount]
    priority_distribution: list[PriorityCount]
    review_funnel: ReviewFunnel
    detection_trend: list[TrendPoint]
