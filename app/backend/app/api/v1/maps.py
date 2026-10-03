import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.schemas.map import MapBounds, MapMarker, SurveyMapOut, TrackPoint
from app.services import map_service, survey_service

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
    # 404 on an unknown survey rather than an empty payload: an empty map reads
    # as "nothing was found here", which is a different and misleading claim.
    survey_service.get_survey_or_404(db, survey_id)

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

    # Unfiltered, the view frames the whole survey: markers plus the track.
    # Filtered, it frames what the filter kept -- the track is never filtered,
    # so including it would zoom out to the entire survey around an empty
    # result (B5 in docs/KNOWN_ISSUES.md). A filter that keeps nothing falls
    # back to the requested bbox, then to the track.
    bbox = (min_lat, min_lon, max_lat, max_lon)
    filtered = any(v is not None for v in bbox) or any((detection_class, priority, review_status))
    if not filtered:
        points = [(m.latitude, m.longitude) for m in markers] + [(t.latitude, t.longitude) for t in track]
    elif markers:
        points = [(m.latitude, m.longitude) for m in markers]
    elif all(v is not None for v in bbox):
        points = [(min_lat, min_lon), (max_lat, max_lon)]
    else:
        points = [(t.latitude, t.longitude) for t in track]

    bounds = (
        MapBounds(
            min_lat=min(p[0] for p in points),
            min_lon=min(p[1] for p in points),
            max_lat=max(p[0] for p in points),
            max_lon=max(p[1] for p in points),
        )
        if points
        else None
    )

    return SurveyMapOut(survey_id=survey_id, bounds=bounds, markers=markers, track=track)
