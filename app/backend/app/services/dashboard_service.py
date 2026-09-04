from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.detection import Detection
from app.models.enums import Priority, ReviewStatus
from app.models.processing_job import ProcessingJob
from app.models.survey import Survey
from app.schemas.dashboard import (
    ActiveJobSummary,
    ClassCount,
    CurrentSurvey,
    DashboardSummary,
    RecentDetection,
    TrendPoint,
)
from app.services.processing_service import ACTIVE_JOB_STATUSES


def build_dashboard_summary(db: Session) -> DashboardSummary:
    current_survey_row = db.query(Survey).order_by(Survey.updated_at.desc()).first()
    current_survey = (
        CurrentSurvey(
            id=current_survey_row.id,
            name=current_survey_row.name,
            status=current_survey_row.status,
            updated_at=current_survey_row.updated_at,
        )
        if current_survey_row
        else None
    )

    active_job_row = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.status.in_(ACTIVE_JOB_STATUSES))
        .order_by(ProcessingJob.created_at.desc())
        .first()
    )
    active_job = (
        ActiveJobSummary(
            id=active_job_row.id,
            survey_id=active_job_row.survey_id,
            status=active_job_row.status,
            stage=active_job_row.stage,
            progress=active_job_row.progress,
        )
        if active_job_row
        else None
    )

    frames_processed = db.scalar(select(func.coalesce(func.sum(ProcessingJob.frames_processed), 0))) or 0
    candidates = db.scalar(select(func.count()).select_from(Detection)) or 0
    confirmed_artificial = (
        db.scalar(
            select(func.count()).select_from(Detection).where(Detection.review_status == ReviewStatus.ACCEPTED_ARTIFICIAL)
        )
        or 0
    )
    high_priority = (
        db.scalar(
            select(func.count())
            .select_from(Detection)
            .where(Detection.priority.in_([Priority.HIGH, Priority.CRITICAL]))
        )
        or 0
    )
    needs_review = (
        db.scalar(select(func.count()).select_from(Detection).where(Detection.review_status == ReviewStatus.PENDING))
        or 0
    )
    rejected_natural = (
        db.scalar(
            select(func.count()).select_from(Detection).where(Detection.review_status == ReviewStatus.REJECTED_NATURAL)
        )
        or 0
    )

    class_rows = (
        db.query(Detection.detection_class, func.count().label("count"))
        .group_by(Detection.detection_class)
        .all()
    )
    class_distribution = [ClassCount(detection_class=row[0], count=row[1]) for row in class_rows]

    since = datetime.now(timezone.utc) - timedelta(days=13)
    trend_rows = (
        db.query(func.date(Detection.created_at).label("day"), func.count().label("count"))
        .filter(Detection.created_at >= since)
        .group_by(func.date(Detection.created_at))
        .order_by(func.date(Detection.created_at))
        .all()
    )
    detection_trend = [TrendPoint(date=str(row[0]), count=row[1]) for row in trend_rows]

    recent_rows = db.query(Detection).order_by(Detection.created_at.desc()).limit(10).all()
    recent_detections = [
        RecentDetection(
            id=d.id,
            detection_ref=d.detection_ref,
            detection_class=d.detection_class,
            calibrated_confidence=d.calibrated_confidence,
            priority=d.priority,
            created_at=d.created_at,
        )
        for d in recent_rows
    ]

    last_updated = current_survey_row.updated_at if current_survey_row else None

    return DashboardSummary(
        current_survey=current_survey,
        active_job=active_job,
        last_updated=last_updated,
        frames_processed=frames_processed,
        candidates=candidates,
        confirmed_artificial=confirmed_artificial,
        high_priority=high_priority,
        needs_review=needs_review,
        rejected_natural=rejected_natural,
        class_distribution=class_distribution,
        detection_trend=detection_trend,
        recent_detections=recent_detections,
    )
