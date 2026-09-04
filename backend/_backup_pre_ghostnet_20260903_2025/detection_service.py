import uuid

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models.detection import Detection
from app.models.detection_review import DetectionReview
from app.models.enums import Priority, ReviewStatus
from app.models.sonar_frame import SonarFrame
from app.schemas.ai_contract import AIDetection

VALID_CLASSES = {"ghost_net", "debris", "natural_object", "unknown"}
VALID_UNCERTAINTY = {"low", "medium", "high"}


class DetectionValidationError(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def validate_ai_detection(detection: AIDetection) -> None:
    """Spec section 52 - reject invalid AI output before it touches the DB."""
    if not detection.detection_id:
        raise DetectionValidationError("Missing detection_id.")
    if detection.class_ not in VALID_CLASSES:
        raise DetectionValidationError(f"Unrecognized class '{detection.class_}'.")
    for score_name, score in (
        ("raw_score", detection.raw_score),
        ("calibrated_confidence", detection.calibrated_confidence),
    ):
        if score is not None and not (0.0 <= score <= 1.0):
            raise DetectionValidationError(f"{score_name} out of range: {score}.")
    if detection.uncertainty is not None and detection.uncertainty not in VALID_UNCERTAINTY:
        raise DetectionValidationError(f"Unrecognized uncertainty '{detection.uncertainty}'.")
    if detection.bbox is not None:
        if len(detection.bbox) != 4 or any(v < 0 for v in detection.bbox):
            raise DetectionValidationError("Invalid bbox values.")
    if detection.latitude is not None and not (-90 <= detection.latitude <= 90):
        raise DetectionValidationError("Latitude out of range.")
    if detection.longitude is not None and not (-180 <= detection.longitude <= 180):
        raise DetectionValidationError("Longitude out of range.")
    if detection.dimensions is not None:
        for dim_name, dim_value in (
            ("width", detection.dimensions.width),
            ("length", detection.dimensions.length),
        ):
            if dim_value is not None and dim_value < 0:
                raise DetectionValidationError(f"Invalid dimension {dim_name}.")
    if not detection.model_version:
        raise DetectionValidationError("Missing model_version.")


def _priority_for(calibrated_confidence: float | None, detection_class: str) -> Priority:
    if detection_class == "ghost_net" and calibrated_confidence is not None:
        if calibrated_confidence >= 0.85:
            return Priority.CRITICAL
        if calibrated_confidence >= 0.65:
            return Priority.HIGH
    if calibrated_confidence is not None and calibrated_confidence >= 0.8:
        return Priority.HIGH
    if calibrated_confidence is not None and calibrated_confidence >= 0.5:
        return Priority.MEDIUM
    return Priority.LOW


def persist_ai_detection(
    db: Session,
    survey_id: uuid.UUID,
    frame: SonarFrame,
    ai_detection: AIDetection,
) -> Detection:
    validate_ai_detection(ai_detection)

    bbox = ai_detection.bbox or [None, None, None, None]
    dims = ai_detection.dimensions

    width = dims.width if dims else None
    length = dims.length if dims else None
    area = round(width * length, 2) if width is not None and length is not None else None

    location_wkt = None
    if ai_detection.latitude is not None and ai_detection.longitude is not None:
        location_wkt = f"SRID=4326;POINT({ai_detection.longitude} {ai_detection.latitude})"

    detection = Detection(
        detection_ref=ai_detection.detection_id,
        survey_id=survey_id,
        frame_id=frame.id,
        source_file_id=frame.file_id,
        detection_class=ai_detection.class_,
        raw_score=ai_detection.raw_score,
        calibrated_confidence=ai_detection.calibrated_confidence,
        uncertainty=ai_detection.uncertainty,
        bbox_x=bbox[0],
        bbox_y=bbox[1],
        bbox_w=bbox[2],
        bbox_h=bbox[3],
        mask_reference=ai_detection.mask,
        latitude=ai_detection.latitude,
        longitude=ai_detection.longitude,
        location=location_wkt,
        position_error_m=ai_detection.position_error_m,
        localization_method=ai_detection.localization,
        depth=frame.depth,
        width=width,
        length=length,
        area=area,
        dimension_status=dims.status if dims else None,
        priority=_priority_for(ai_detection.calibrated_confidence, ai_detection.class_),
        review_status=ReviewStatus.PENDING,
        model_version=ai_detection.model_version,
        evidence_summary=ai_detection.evidence_summary or {},
    )
    db.add(detection)
    db.flush()
    return detection


def get_detection_or_404(db: Session, detection_id: uuid.UUID) -> Detection:
    detection = db.get(Detection, detection_id)
    if not detection:
        raise ApiError(404, "DETECTION_NOT_FOUND", "Detection was not found.")
    return detection


def list_detections(
    db: Session,
    page: int,
    page_size: int,
    survey_id: uuid.UUID | None = None,
    detection_class: str | None = None,
    min_confidence: float | None = None,
    priority: str | None = None,
    review_status: str | None = None,
) -> tuple[list[Detection], int]:
    conditions = []
    if survey_id is not None:
        conditions.append(Detection.survey_id == survey_id)
    if detection_class is not None:
        conditions.append(Detection.detection_class == detection_class)
    if min_confidence is not None:
        conditions.append(Detection.calibrated_confidence >= min_confidence)
    if priority is not None:
        conditions.append(Detection.priority == priority)
    if review_status is not None:
        conditions.append(Detection.review_status == review_status)

    where_clause = and_(*conditions) if conditions else True

    total = db.scalar(select(func.count()).select_from(Detection).where(where_clause)) or 0
    items = (
        db.query(Detection)
        .where(where_clause)
        .order_by(Detection.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def add_review(db: Session, detection_id: uuid.UUID, decision: ReviewStatus, reviewer: str | None, note: str | None) -> DetectionReview:
    detection = get_detection_or_404(db, detection_id)
    review = DetectionReview(detection_id=detection.id, decision=decision, reviewer=reviewer, note=note)
    db.add(review)
    detection.review_status = decision
    db.commit()
    db.refresh(review)
    return review


async def add_review_and_broadcast(
    db: Session, detection_id: uuid.UUID, decision: ReviewStatus, reviewer: str | None, note: str | None
) -> DetectionReview:
    """Same as add_review but also emits detection.updated so GIS map, detection
    list and sonar viewer on other connected clients pick up the review change
    without a reload (spec: map<->sonar sync is one investigation workflow)."""
    from app.realtime.manager import manager

    detection = get_detection_or_404(db, detection_id)
    survey_id = detection.survey_id
    review = add_review(db, detection_id, decision, reviewer, note)
    await manager.broadcast(str(survey_id), "detection.updated", {"detection_id": str(detection_id)})
    return review


def list_reviews(db: Session, detection_id: uuid.UUID) -> list[DetectionReview]:
    return (
        db.query(DetectionReview)
        .filter(DetectionReview.detection_id == detection_id)
        .order_by(DetectionReview.created_at.desc())
        .all()
    )
