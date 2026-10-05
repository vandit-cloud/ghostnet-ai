import asyncio
import csv
import io
import json
import logging
import math
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core import db as db_module
from app.core.errors import ApiError
from app.models.detection import Detection
from app.models.enums import ReportFormat, ReportStatus, ReportType
from app.models.report import Report
from app.realtime.manager import manager
from app.schemas.report import ReportCreate
from app.services import survey_service
from app.storage.local import StorageBackend

logger = logging.getLogger("ghostnet.reports")
settings = get_settings()

CSV_FIELDS = [
    "detection_id",
    "survey_id",
    "frame_id",
    "classification",
    "confidence",
    "uncertainty",
    "latitude",
    "longitude",
    "position_error_m",
    "width",
    "length",
    "priority",
    "review_status",
    "model_version",
    "timestamp",
]


#: Download metadata per format. One table, read by both the generator (file
#: extension on disk) and the download endpoint (media type + filename), so a
#: new format cannot be half-wired. `application/geo+json` is the IANA type
#: RFC 7946 registers; GIS tools key on it and on the `.geojson` extension.
FORMAT_MEDIA = {
    ReportFormat.CSV: ("text/csv", "csv"),
    ReportFormat.JSON: ("application/json", "json"),
    ReportFormat.GEOJSON: ("application/geo+json", "geojson"),
}

# infer.py folds the detector's finer class into evidence_summary.notes as
# "detector class: wreck" when the contract vocabulary is coarser (a wreck
# reports as `debris`). Pulled out so a GIS user can style on it.
_DETECTOR_CLASS_RE = re.compile(r"detector class:\s*([A-Za-z0-9_\-]+)")


def get_report_or_404(db: Session, report_id: uuid.UUID) -> Report:
    report = db.get(Report, report_id)
    if not report:
        raise ApiError(404, "REPORT_NOT_FOUND", "Report was not found.")
    return report


def list_reports(db: Session, survey_id: uuid.UUID | None = None) -> list[Report]:
    query = db.query(Report)
    if survey_id is not None:
        query = query.filter(Report.survey_id == survey_id)
    return query.order_by(Report.created_at.desc()).all()


# The filter keys a "filtered_detections" report understands. Anything else is
# refused rather than ignored: an ignored key produces a report that says it is
# filtered and is not (B4 in docs/KNOWN_ISSUES.md).
REPORT_FILTER_KEYS = frozenset({"class", "priority", "review_status", "min_confidence"})


def _validated_filters(db: Session, payload: ReportCreate) -> dict:
    """The `filters` a report row should store, or an ApiError.

    The report's scope has to survive the trip to the background generator,
    which only sees the stored row. A selected-detection report therefore keeps
    its detection id inside `filters` -- the column that already records what a
    report covers -- instead of in a new `reports.detection_id` column (B3).
    """
    if payload.type == ReportType.SELECTED_DETECTION:
        if payload.detection_id is None:
            raise ApiError(422, "DETECTION_ID_REQUIRED", "A selected-detection report needs a detection_id.")
        detection = db.get(Detection, payload.detection_id)
        if detection is None or detection.survey_id != payload.survey_id:
            raise ApiError(404, "DETECTION_NOT_FOUND", "Detection was not found in this survey.")
        return {"detection_id": str(payload.detection_id)}

    if payload.type == ReportType.FILTERED_DETECTIONS:
        filters = {k: v for k, v in (payload.filters or {}).items() if v not in (None, "")}
        unknown = sorted(set(filters) - REPORT_FILTER_KEYS)
        if unknown:
            raise ApiError(422, "UNKNOWN_REPORT_FILTER", f"Unknown report filter(s): {', '.join(unknown)}.")
        if not filters:
            raise ApiError(422, "REPORT_FILTERS_REQUIRED", "A filtered report needs at least one filter.")
        return filters

    return {}


def _detections_for_report(db: Session, payload: ReportCreate) -> list[Detection]:
    query = db.query(Detection).filter(Detection.survey_id == payload.survey_id)
    filters = payload.filters or {}

    if payload.type == ReportType.SELECTED_DETECTION:
        # A selected report without its id must come out empty, never as the
        # whole survey under a single-detection label.
        detection_id = filters.get("detection_id")
        query = query.filter(Detection.id == (uuid.UUID(detection_id) if detection_id else None))
    elif payload.type == ReportType.FILTERED_DETECTIONS:
        if "class" in filters:
            query = query.filter(Detection.detection_class == filters["class"])
        if "priority" in filters:
            query = query.filter(Detection.priority == filters["priority"])
        if "review_status" in filters:
            query = query.filter(Detection.review_status == filters["review_status"])
        if "min_confidence" in filters:
            query = query.filter(Detection.calibrated_confidence >= filters["min_confidence"])

    return query.order_by(Detection.created_at.asc()).all()


def create_report(db: Session, payload: ReportCreate) -> Report:
    # Checked here, not left to the foreign key: a failed commit reaches the
    # generic handler as a 500 (C1 in docs/KNOWN_ISSUES.md).
    survey_service.get_survey_or_404(db, payload.survey_id)
    filters = _validated_filters(db, payload)

    report = Report(
        survey_id=payload.survey_id,
        type=payload.type,
        format=payload.format,
        filters=filters,
        status=ReportStatus.QUEUED,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    asyncio.create_task(_generate_report(report.id))
    return report


def _render_csv(detections: list[Detection]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for d in detections:
        writer.writerow(
            {
                "detection_id": d.detection_ref,
                "survey_id": str(d.survey_id),
                "frame_id": str(d.frame_id),
                "classification": d.detection_class,
                "confidence": d.calibrated_confidence,
                "uncertainty": d.uncertainty,
                "latitude": d.latitude,
                "longitude": d.longitude,
                "position_error_m": d.position_error_m,
                "width": d.width,
                "length": d.length,
                "priority": d.priority,
                "review_status": d.review_status,
                "model_version": d.model_version,
                "timestamp": d.created_at.isoformat(),
            }
        )
    return buffer.getvalue().encode("utf-8")


def _render_json(report: Report, detections: list[Detection]) -> bytes:
    payload = {
        "survey_id": str(report.survey_id),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "report_type": report.type,
        "filters": report.filters,
        "detections": [
            {
                "detection_id": d.detection_ref,
                "frame_id": str(d.frame_id),
                "class": d.detection_class,
                "raw_score": d.raw_score,
                "calibrated_confidence": d.calibrated_confidence,
                "uncertainty": d.uncertainty,
                "latitude": d.latitude,
                "longitude": d.longitude,
                "position_error_m": d.position_error_m,
                "dimensions": {"width": d.width, "length": d.length, "status": d.dimension_status},
                "priority": d.priority,
                "review_status": d.review_status,
                "model_version": d.model_version,
                "evidence_summary": d.evidence_summary,
                "created_at": d.created_at.isoformat(),
            }
            for d in detections
        ],
    }
    return json.dumps(payload, indent=2).encode("utf-8")


def _detector_class(d: Detection) -> str | None:
    notes = (d.evidence_summary or {}).get("notes")
    if not isinstance(notes, str):
        return None
    match = _DETECTOR_CLASS_RE.search(notes)
    return match.group(1) if match else None


def _point_geometry(d: Detection) -> tuple[dict | None, str]:
    """The feature geometry and why it is (or is not) there.

    A detection with no usable position still goes in the file with
    `geometry: null` (RFC 7946 sec. 3.2 allows it). Dropping it would make a
    target vanish from the map with nothing to say it was ever found.
    """
    lat, lon = d.latitude, d.longitude
    if lat is None or lon is None:
        return None, "no_position"
    if not (math.isfinite(lat) and math.isfinite(lon)) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None, "invalid_position"
    # RFC 7946 sec. 3.1.1: longitude FIRST, WGS84 -- the reverse of how every
    # other report column orders them.
    return {"type": "Point", "coordinates": [lon, lat]}, "located"


def _finite_or_none(value: float | None) -> float | None:
    # json.dumps writes NaN as a bare `NaN`, which is not JSON and breaks
    # strict GeoJSON parsers.
    return value if value is None or math.isfinite(value) else None


def _geojson_feature(d: Detection) -> dict:
    geometry, position_status = _point_geometry(d)
    return {
        "type": "Feature",
        "id": str(d.id),
        "geometry": geometry,
        "properties": {
            "detection_id": d.detection_ref,
            "class": d.detection_class,
            "detector_class": _detector_class(d),
            "raw_score": _finite_or_none(d.raw_score),
            "calibrated_confidence": _finite_or_none(d.calibrated_confidence),
            "uncertainty": d.uncertainty,
            "priority": d.priority,
            "review_status": d.review_status,
            "review_only": d.review_only,
            # Kept as plain properties too, so a null-geometry row still says
            # what was stored. position_error_m is the radius a GIS user
            # buffers the point by to draw its uncertainty circle.
            "latitude": _finite_or_none(d.latitude),
            "longitude": _finite_or_none(d.longitude),
            "position_error_m": _finite_or_none(d.position_error_m),
            "position_status": position_status,
            "localization_method": d.localization_method,
            "width_m": _finite_or_none(d.width),
            "length_m": _finite_or_none(d.length),
            "area_m2": _finite_or_none(d.area),
            "dimension_status": d.dimension_status,
            "survey_id": str(d.survey_id),
            "frame_id": str(d.frame_id),
            "model_version": d.model_version,
            "evidence_summary": d.evidence_summary,
            "created_at": d.created_at.isoformat(),
        },
    }


def _render_geojson(report: Report, detections: list[Detection]) -> bytes:
    # Points only. Mask polygons (mask_reference) are future work: they live in
    # pixel space and need the frame's geo transform to become WGS84 rings.
    features = [_geojson_feature(d) for d in detections]
    unlocated = [f for f in features if f["geometry"] is None]
    payload = {
        "type": "FeatureCollection",
        # A foreign member (RFC 7946 sec. 6.1): parsers ignore it, people
        # reading the file do not. The counts make a short map obvious --
        # "12 detections, 9 on the map" -- instead of silently short.
        "metadata": {
            "survey_id": str(report.survey_id),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "report_type": report.type,
            "filters": report.filters,
            "crs": "WGS84 (EPSG:4326), coordinates [longitude, latitude]",
            "detection_count": len(features),
            "located_count": len(features) - len(unlocated),
            "unlocated_count": len(unlocated),
            "unlocated_detection_ids": [f["properties"]["detection_id"] for f in unlocated],
        },
        "features": features,
    }
    return json.dumps(payload, indent=2).encode("utf-8")


async def _generate_report(report_id: uuid.UUID) -> None:
    db = db_module.SessionLocal()
    try:
        report = db.get(Report, report_id)
        if not report:
            return
        report.status = ReportStatus.PROCESSING
        db.commit()

        payload = ReportCreate(
            survey_id=report.survey_id,
            type=report.type,
            format=report.format,
            filters=report.filters or {},
        )
        detections = _detections_for_report(db, payload)

        if report.format == ReportFormat.CSV:
            content = _render_csv(detections)
        elif report.format == ReportFormat.GEOJSON:
            content = _render_geojson(report, detections)
        else:
            content = _render_json(report, detections)
        _, ext = FORMAT_MEDIA[ReportFormat(report.format)]

        from app.storage.local import get_storage_backend

        storage: StorageBackend = get_storage_backend()
        filename = f"report-{report.id}.{ext}"
        storage_reference, _, _ = storage.save(f"reports/{report.survey_id}", filename, io.BytesIO(content))

        report.storage_reference = storage_reference
        report.status = ReportStatus.COMPLETED
        report.completed_at = datetime.now(timezone.utc)
        db.commit()

        await manager.broadcast(str(report.survey_id), "report.completed", {"report_id": str(report.id)})
    except Exception:
        logger.exception("Report generation failed for %s", report_id)
        db.rollback()
        report = db.get(Report, report_id)
        if report:
            report.status = ReportStatus.FAILED
            report.error_summary = "Report generation failed."
            db.commit()
    finally:
        db.close()
