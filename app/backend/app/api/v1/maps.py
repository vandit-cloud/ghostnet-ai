import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.schemas.map import MapBounds, MapMarker, SurveyMapOut, TrackPoint
from app.services import map_service

router = APIRouter(prefix="/maps", tags=["maps"], dependencies=[Depends(get_current_user)])


@router.get("/surveys/{survey_id}/detections", response_model=SurveyMapOut)
def get_survey_detections(
    survey_id: uuid.UUID,
    min_lat: float | None = Query(None),
    min_lon: float | None = Query(None),
    max_lat: float | None = Query(None),
    max_lon: float | None = Query(None),
    detection_class: str | None = None,
    priority: str | None = None,
    review_status: str | None = None,
    db: Session = Depends(get_db),
) -> SurveyMapOut:
    detections = map_service.get_survey_markers(
        db, survey_id, min_lat, min_lon, max_lat, max_lon, detection_class, priority, review_status
    )
    frames = map_service.get_survey_track(db, survey_id)

    markers = [
        MapMarker(
            detection_id=d.id,
            detection_ref=d.detection_ref,
            detection_class=d.detection_class,
            latitude=d.latitude,
            longitude=d.longitude,
            priority=d.priority,
            review_status=d.review_status,
            calibrated_confidence=d.calibrated_confidence,
            uncertainty=d.uncertainty,
            position_error_m=d.position_error_m,
            depth=d.depth,
            created_at=d.created_at,
        )
        for d in detections
    ]

    track = [
        TrackPoint(latitude=f.latitude, longitude=f.longitude, timestamp=f.timestamp, range=f.range)
        for f in frames
    ]

    bounds_lats = [m.latitude for m in markers] + [t.latitude for t in track]
    bounds_lons = [m.longitude for m in markers] + [t.longitude for t in track]
    bounds = (
        MapBounds(min_lat=min(bounds_lats), min_lon=min(bounds_lons), max_lat=max(bounds_lats), max_lon=max(bounds_lons))
        if bounds_lats
        else None
    )

    return SurveyMapOut(survey_id=survey_id, bounds=bounds, markers=markers, track=track)
