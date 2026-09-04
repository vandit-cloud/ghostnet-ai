import asyncio
import csv
import io
import json
import logging
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


def _detections_for_report(db: Session, payload: ReportCreate) -> list[Detection]:
    query = db.query(Detection).filter(Detection.survey_id == payload.survey_id)

    if payload.type == ReportType.SELECTED_DETECTION and payload.detection_id:
        query = query.filter(Detection.id == payload.detection_id)
    elif payload.type == ReportType.FILTERED_DETECTIONS:
        filters = payload.filters or {}
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
    report = Report(
        survey_id=payload.survey_id,
        type=payload.type,
        format=payload.format,
        filters=payload.filters,
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
            ext = "csv"
        else:
            content = _render_json(report, detections)
            ext = "json"

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
