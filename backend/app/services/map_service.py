import uuid

from sqlalchemy.orm import Session

from app.models.detection import Detection
from app.models.sonar_frame import SonarFrame


def get_survey_markers(
    db: Session,
    survey_id: uuid.UUID,
    min_lat: float | None = None,
    min_lon: float | None = None,
    max_lat: float | None = None,
    max_lon: float | None = None,
    detection_class: str | None = None,
    priority: str | None = None,
    review_status: str | None = None,
) -> list[Detection]:
    query = db.query(Detection).filter(
        Detection.survey_id == survey_id,
        Detection.latitude.isnot(None),
        Detection.longitude.isnot(None),
    )
    if min_lat is not None:
        query = query.filter(Detection.latitude >= min_lat)
    if max_lat is not None:
        query = query.filter(Detection.latitude <= max_lat)
    if min_lon is not None:
        query = query.filter(Detection.longitude >= min_lon)
    if max_lon is not None:
        query = query.filter(Detection.longitude <= max_lon)
    if detection_class is not None:
        query = query.filter(Detection.detection_class == detection_class)
    if priority is not None:
        query = query.filter(Detection.priority == priority)
    if review_status is not None:
        query = query.filter(Detection.review_status == review_status)

    return query.order_by(Detection.created_at.desc()).limit(2000).all()


def get_survey_track(db: Session, survey_id: uuid.UUID) -> list[SonarFrame]:
    """Ordered vessel track from frame geotags (spec section 21 - 'survey track if
    available'). Only frames with a real position are included; never fabricated."""
    return (
        db.query(SonarFrame)
        .filter(
            SonarFrame.survey_id == survey_id,
            SonarFrame.latitude.isnot(None),
            SonarFrame.longitude.isnot(None),
        )
        .order_by(SonarFrame.timestamp.asc().nulls_last(), SonarFrame.created_at.asc())
        .limit(5000)
        .all()
    )
