import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core import db as db_module
from app.core.errors import ApiError
from app.models.enums import JobStage, JobStatus, SurveyStatus
from app.models.processing_job import ProcessingJob
from app.models.sonar_frame import SonarFrame
from app.models.survey import Survey
from app.realtime.manager import manager
from app.schemas.ai_contract import AIFrameMetadata
from app.services import detection_service
from app.services.ai_service import AIServiceAdapter, get_ai_adapter

logger = logging.getLogger("ghostnet.processing")

_running_tasks: dict[str, asyncio.Task] = {}
_cancel_flags: set[str] = set()

ACTIVE_JOB_STATUSES = (JobStatus.QUEUED, JobStatus.VALIDATING, JobStatus.PROCESSING)


def get_job_or_404(db: Session, job_id: uuid.UUID) -> ProcessingJob:
    job = db.get(ProcessingJob, job_id)
    if not job:
        raise ApiError(404, "JOB_NOT_FOUND", "Processing job was not found.")
    return job


def get_active_job_for_survey(db: Session, survey_id: uuid.UUID) -> ProcessingJob | None:
    return (
        db.query(ProcessingJob)
        .filter(ProcessingJob.survey_id == survey_id, ProcessingJob.status.in_(ACTIVE_JOB_STATUSES))
        .order_by(ProcessingJob.created_at.desc())
        .first()
    )


def start_processing(db: Session, survey_id: uuid.UUID) -> ProcessingJob:
    """Idempotent: if a job is already running for this survey, return it
    instead of starting a duplicate (spec section 17 - refresh must not
    restart processing)."""
    existing = get_active_job_for_survey(db, survey_id)
    if existing:
        return existing

    frames_total = db.query(SonarFrame).filter(SonarFrame.survey_id == survey_id).count()

    job = ProcessingJob(survey_id=survey_id, frames_total=frames_total)
    db.add(job)
    db.commit()
    db.refresh(job)

    task = asyncio.create_task(_run_job(job.id))
    _running_tasks[str(job.id)] = task
    return job


def cancel_job(db: Session, job_id: uuid.UUID) -> ProcessingJob:
    job = get_job_or_404(db, job_id)
    if job.status not in ACTIVE_JOB_STATUSES:
        return job
    _cancel_flags.add(str(job_id))
    return job


async def _emit(survey_id: str, event: str, payload: dict) -> None:
    try:
        await manager.broadcast(survey_id, event, payload)
    except Exception:
        logger.exception("Failed to broadcast realtime event %s", event)


async def _run_job(job_id: uuid.UUID) -> None:
    db = db_module.SessionLocal()
    try:
        job = db.get(ProcessingJob, job_id)
        if not job:
            return
        survey_id = job.survey_id
        survey = db.get(Survey, survey_id)

        job.status = JobStatus.VALIDATING
        job.stage = JobStage.VALIDATING
        job.started_at = datetime.now(timezone.utc)
        if survey:
            survey.status = SurveyStatus.PROCESSING
        db.commit()
        await _emit(str(survey_id), "job.updated", {"job_id": str(job_id), "status": job.status, "stage": job.stage})

        frames = db.query(SonarFrame).filter(SonarFrame.survey_id == survey_id).all()
        adapter: AIServiceAdapter = get_ai_adapter()

        for stage in (JobStage.DECODING, JobStage.PREPROCESSING):
            job.stage = stage
            db.commit()
            await _emit(str(survey_id), "job.updated", {"job_id": str(job_id), "status": job.status, "stage": job.stage})
            await asyncio.sleep(0.05)

        job.status = JobStatus.PROCESSING

        for frame in frames:
            if str(job_id) in _cancel_flags:
                job.status = JobStatus.CANCELLED
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
                await _emit(str(survey_id), "job.updated", {"job_id": str(job_id), "status": job.status, "stage": job.stage})
                _cancel_flags.discard(str(job_id))
                return

            for stage in (JobStage.DETECTION, JobStage.VERIFICATION, JobStage.CALIBRATION, JobStage.GEOTAGGING):
                job.stage = stage
                db.commit()
                await asyncio.sleep(0.02)

            try:
                metadata = AIFrameMetadata(
                    timestamp=frame.timestamp.isoformat() if frame.timestamp else None,
                    latitude=frame.latitude,
                    longitude=frame.longitude,
                    heading=frame.heading,
                    depth=frame.depth,
                    range=frame.range,
                    # Sonar geometry. Passing these is what lets the AI turn a
                    # bounding box into a coordinate; without them it reports
                    # the detection with localization "none" rather than
                    # guessing, and the map draws a track with no markers.
                    # NULL on image uploads, which never had ping headers.
                    nadir_col=frame.nadir_col,
                    range_resolution_m=frame.range_resolution_m,
                    altitude_m=frame.altitude_m,
                    along_track_res_m=frame.along_track_res_m,
                    layback_m=frame.layback_m,
                    nadir_row=frame.nadir_row,
                )
                result = adapter.analyze_frame(
                    survey_id=str(survey_id),
                    frame_id=frame.frame_id,
                    image_path=frame.image_reference,
                    metadata=metadata,
                )

                job.stage = JobStage.SAVING
                for ai_detection in result.detections:
                    try:
                        detection = detection_service.persist_ai_detection(db, survey_id, frame, ai_detection)
                        job.detections_found += 1
                        db.commit()
                        await _emit(
                            str(survey_id),
                            "detection.created",
                            {"detection_id": str(detection.id)},
                        )
                    except detection_service.DetectionValidationError as exc:
                        logger.warning("Rejected invalid AI detection for frame %s: %s", frame.frame_id, exc.reason)
                        db.rollback()

                job.frames_processed += 1
            except Exception:
                logger.exception("Frame processing failed for %s", frame.frame_id)
                job.frames_failed += 1

            job.progress = int(((job.frames_processed + job.frames_failed) / max(job.frames_total, 1)) * 100)
            db.commit()
            await _emit(
                str(survey_id),
                "frame.processed",
                {
                    "job_id": str(job_id),
                    "frames_processed": job.frames_processed,
                    "frames_failed": job.frames_failed,
                    "progress": job.progress,
                },
            )

        job.stage = JobStage.DONE
        job.completed_at = datetime.now(timezone.utc)
        if job.frames_failed == 0:
            job.status = JobStatus.COMPLETED
            if survey:
                survey.status = SurveyStatus.COMPLETED
        elif job.frames_processed > 0:
            job.status = JobStatus.PARTIAL
            if survey:
                survey.status = SurveyStatus.PARTIAL
        else:
            job.status = JobStatus.FAILED
            job.error_summary = "All frames failed processing."
            if survey:
                survey.status = SurveyStatus.FAILED
        db.commit()
        await _emit(str(survey_id), "job.updated", {"job_id": str(job_id), "status": job.status, "stage": job.stage})
    except Exception:
        logger.exception("Processing job %s crashed", job_id)
        db.rollback()
        job = db.get(ProcessingJob, job_id)
        if job:
            job.status = JobStatus.FAILED
            job.error_summary = "Processing job failed unexpectedly."
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        _running_tasks.pop(str(job_id), None)
        db.close()
