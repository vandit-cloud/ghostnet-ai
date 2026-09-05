import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.detection import Detection
from app.models.survey import Survey
from app.models.user import User
from app.schemas.common import Page
from app.schemas.detection import BBox, DetectionOut, DetectionReviewIn, DetectionReviewOut, Dimensions
from app.services import detection_service

router = APIRouter(prefix="/detections", tags=["detections"], dependencies=[Depends(get_current_user)])


def _to_out(d: Detection, survey_name: str | None = None) -> DetectionOut:
    return DetectionOut(
        id=d.id,
        detection_ref=d.detection_ref,
        survey_id=d.survey_id,
        survey_name=survey_name,
        frame_id=d.frame_id,
        detection_class=d.detection_class,
        raw_score=d.raw_score,
        calibrated_confidence=d.calibrated_confidence,
        uncertainty=d.uncertainty,
        bbox=BBox(x=d.bbox_x, y=d.bbox_y, w=d.bbox_w, h=d.bbox_h),
        mask_reference=d.mask_reference,
        latitude=d.latitude,
        longitude=d.longitude,
        position_error_m=d.position_error_m,
        localization_method=d.localization_method,
        depth=d.depth,
        dimensions=Dimensions(width=d.width, length=d.length, area=d.area, status=d.dimension_status),
        priority=d.priority,
        review_status=d.review_status,
        model_version=d.model_version,
        evidence_summary=d.evidence_summary,
        created_at=d.created_at,
        updated_at=d.updated_at,
    )


@router.get("", response_model=Page[DetectionOut])
def list_detections(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    survey_id: uuid.UUID | None = None,
    detection_class: str | None = None,
    min_confidence: float | None = Query(None, ge=0, le=1),
    priority: str | None = None,
    review_status: str | None = None,
    db: Session = Depends(get_db),
) -> Page[DetectionOut]:
    items, total = detection_service.list_detections(
        db, page, page_size, survey_id, detection_class, min_confidence, priority, review_status
    )
    # One query for the names on this page, rather than a lookup per row.
    survey_ids = {d.survey_id for d in items}
    names = (
        dict(db.query(Survey.id, Survey.name).filter(Survey.id.in_(survey_ids)).all())
        if survey_ids
        else {}
    )
    return Page(
        items=[_to_out(d, names.get(d.survey_id)) for d in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{detection_id}", response_model=DetectionOut)
def get_detection(detection_id: uuid.UUID, db: Session = Depends(get_db)) -> DetectionOut:
    detection = detection_service.get_detection_or_404(db, detection_id)
    survey = db.get(Survey, detection.survey_id)
    return _to_out(detection, survey.name if survey else None)


@router.post("/{detection_id}/review", response_model=DetectionReviewOut, status_code=201)
async def review_detection(
    detection_id: uuid.UUID,
    payload: DetectionReviewIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DetectionReviewOut:
    # The reviewer is the authenticated user, never `payload.reviewer`. The
    # token is the only thing we can verify, so it is the only thing we record
    # -- a decision must not be attributable to someone who did not make it.
    # Any client-supplied `reviewer` is deliberately ignored.

    review = await detection_service.add_review_and_broadcast(
        db, detection_id, payload.decision, user.username, payload.note
    )
    return DetectionReviewOut.model_validate(review)


@router.get("/{detection_id}/reviews", response_model=list[DetectionReviewOut])
def get_reviews(detection_id: uuid.UUID, db: Session = Depends(get_db)) -> list[DetectionReviewOut]:
    reviews = detection_service.list_reviews(db, detection_id)
    return [DetectionReviewOut.model_validate(r) for r in reviews]
