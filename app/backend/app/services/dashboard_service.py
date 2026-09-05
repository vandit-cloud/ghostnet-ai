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

    # Every number on this card sits beside `current_survey`'s name, so every
    # number is scoped to that survey. They used to be global counts: with four
    # surveys in the database the card credited one 40-frame survey with 160
    # frames and 20 detections, which reads as the app inventing results.
    # See B1 in docs/KNOWN_ISSUES.md.
    scope_id = current_survey_row.id if current_survey_row else None

    def count_detections(*conditions) -> int:
        if scope_id is None:
            return 0
        stmt = select(func.count()).select_from(Detection).where(Detection.survey_id == scope_id)
        for condition in conditions:
            stmt = stmt.where(condition)
        return db.scalar(stmt) or 0

    frames_processed = (
        db.scalar(
            select(func.coalesce(func.sum(ProcessingJob.frames_processed), 0)).where(
                ProcessingJob.survey_id == scope_id
            )
        )
        or 0
    ) if scope_id else 0
    candidates = count_detections()
    confirmed_artificial = count_detections(Detection.review_status == ReviewStatus.ACCEPTED_ARTIFICIAL)
    high_priority = count_detections(Detection.priority.in_([Priority.HIGH, Priority.CRITICAL]))
    needs_review = count_detections(Detection.review_status == ReviewStatus.PENDING)
    rejected_natural = count_detections(Detection.review_status == ReviewStatus.REJECTED_NATURAL)

    class_rows = (
        db.query(Detection.detection_class, func.count().label("count"))
        .filter(Detection.survey_id == scope_id)
        .group_by(Detection.detection_class)
        .all()
        if scope_id
        else []
    )
    class_distribution = [ClassCount(detection_class=row[0], count=row[1]) for row in class_rows]

    since = datetime.now(timezone.utc) - timedelta(days=13)
    trend_rows = (
        db.query(func.date(Detection.created_at).label("day"), func.count().label("count"))
        .filter(Detection.survey_id == scope_id, Detection.created_at >= since)
        .group_by(func.date(Detection.created_at))
        .order_by(func.date(Detection.created_at))
        .all()
        if scope_id
        else []
    )
    detection_trend = [TrendPoint(date=str(row[0]), count=row[1]) for row in trend_rows]

    recent_rows = (
        db.query(Detection)
        .filter(Detection.survey_id == scope_id)
        .order_by(Detection.created_at.desc())
        .limit(10)
        .all()
        if scope_id
        else []
    )
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
