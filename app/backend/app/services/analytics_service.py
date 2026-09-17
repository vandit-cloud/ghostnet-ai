from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.detection import Detection
from app.models.enums import ReviewStatus
from app.models.report import Report
from app.models.survey import Survey
from app.schemas.analytics import AnalyticsSummary, PriorityCount, ReviewFunnel
from app.schemas.dashboard import ClassCount, TrendPoint


def build_analytics_summary(db: Session) -> AnalyticsSummary:
    """Platform-wide aggregates across every survey -- unlike the dashboard
    summary, which is deliberately scoped to just the current one (see
    dashboard_service.py's own note on why global counts read as fabricated
    results there). Analytics is where the global view belongs."""

    total_surveys = db.scalar(select(func.count()).select_from(Survey)) or 0
    total_detections = db.scalar(select(func.count()).select_from(Detection)) or 0
    total_reports = db.scalar(select(func.count()).select_from(Report)) or 0
    average_confidence = db.scalar(select(func.avg(Detection.calibrated_confidence)))

    class_rows = db.query(Detection.detection_class, func.count().label("count")).group_by(
        Detection.detection_class
    ).all()
    class_distribution = [ClassCount(detection_class=row[0], count=row[1]) for row in class_rows]

    priority_rows = db.query(Detection.priority, func.count().label("count")).group_by(Detection.priority).all()
    priority_distribution = [PriorityCount(priority=row[0], count=row[1]) for row in priority_rows]

    def count_review(status: ReviewStatus) -> int:
        return db.scalar(
            select(func.count()).select_from(Detection).where(Detection.review_status == status)
        ) or 0

    review_funnel = ReviewFunnel(
        pending=count_review(ReviewStatus.PENDING),
        unknown=count_review(ReviewStatus.UNKNOWN),
        accepted_artificial=count_review(ReviewStatus.ACCEPTED_ARTIFICIAL),
        rejected_natural=count_review(ReviewStatus.REJECTED_NATURAL),
    )

    since = datetime.now(timezone.utc) - timedelta(days=13)
    trend_rows = (
        db.query(func.date(Detection.created_at).label("day"), func.count().label("count"))
        .filter(Detection.created_at >= since)
        .group_by(func.date(Detection.created_at))
        .order_by(func.date(Detection.created_at))
        .all()
    )
    detection_trend = [TrendPoint(date=str(row[0]), count=row[1]) for row in trend_rows]

    return AnalyticsSummary(
        total_surveys=total_surveys,
        total_detections=total_detections,
        total_reports=total_reports,
        average_calibrated_confidence=round(average_confidence, 3) if average_confidence is not None else None,
        class_distribution=class_distribution,
        priority_distribution=priority_distribution,
        review_funnel=review_funnel,
        detection_trend=detection_trend,
    )
