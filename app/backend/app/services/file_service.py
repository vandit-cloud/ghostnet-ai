import json
import logging
import shutil
import uuid
from datetime import datetime, timezone
from typing import BinaryIO

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ApiError
from app.models.enums import FileValidationStatus
from app.models.sonar_frame import SonarFrame
from app.models.survey_file import SurveyFile
from app.storage.local import StorageBackend

logger = logging.getLogger(__name__)

settings = get_settings()

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
SONAR_LOG_EXTENSIONS = {".xtf", ".jsf"}


def _extension(filename: str) -> str:
    idx = filename.rfind(".")
    return filename[idx:].lower() if idx != -1 else ""


def validate_upload(filename: str, size: int) -> tuple[FileValidationStatus, str | None]:
    ext = _extension(filename)
    if ext not in settings.allowed_upload_extensions:
        return FileValidationStatus.INVALID, f"Unsupported file format '{ext}'."
    if size <= 0:
        return FileValidationStatus.INVALID, "File is empty."
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if size > max_bytes:
        return FileValidationStatus.INVALID, f"File exceeds {settings.max_upload_size_mb}MB limit."
    return FileValidationStatus.VALID, None


def validate_metadata(metadata_raw: str | None) -> tuple[FileValidationStatus, dict | None, str | None]:
    if not metadata_raw:
        return FileValidationStatus.PENDING, None, None
    try:
        metadata = json.loads(metadata_raw)
    except json.JSONDecodeError:
        return FileValidationStatus.INVALID, None, "Metadata is not valid JSON."

    lat = metadata.get("latitude")
    lon = metadata.get("longitude")
    if lat is not None and not (-90 <= lat <= 90):
        return FileValidationStatus.INVALID, None, "Latitude out of range."
    if lon is not None and not (-180 <= lon <= 180):
        return FileValidationStatus.INVALID, None, "Longitude out of range."

    return FileValidationStatus.VALID, metadata, None


def upload_survey_file(
    db: Session,
    storage: StorageBackend,
    survey_id: uuid.UUID,
    filename: str,
    stream: BinaryIO,
    metadata_raw: str | None,
) -> SurveyFile:
    storage_reference, size, checksum = storage.save(str(survey_id), filename, stream)

    validation_status, validation_message = validate_upload(filename, size)
    metadata_status, metadata, metadata_error = validate_metadata(metadata_raw)
    if metadata_error and not validation_message:
        validation_message = metadata_error

    survey_file = SurveyFile(
        survey_id=survey_id,
        filename=filename,
        storage_reference=storage_reference,
        format=_extension(filename).lstrip("."),
        size=size,
        checksum=checksum,
        validation_status=validation_status,
        validation_message=validation_message,
        metadata_status=metadata_status,
    )
    db.add(survey_file)
    db.flush()

    ext = _extension(filename)
    if validation_status == FileValidationStatus.VALID and ext in IMAGE_EXTENSIONS:
        frame_timestamp = None
        if metadata and metadata.get("timestamp"):
            try:
                frame_timestamp = datetime.fromisoformat(metadata["timestamp"])
            except ValueError:
                frame_timestamp = None

        frame = SonarFrame(
            survey_id=survey_id,
            file_id=survey_file.id,
            frame_id=f"FRAME-{uuid.uuid4().hex[:10].upper()}",
            ping_id=(metadata or {}).get("ping_id"),
            timestamp=frame_timestamp or datetime.now(timezone.utc),
            # storage.path_for(), NOT storage_reference -- the same distinction
            # the XTF branch below documents, and it was wrong here too.
            #
            # `processing_service` hands `image_reference` straight to the AI
            # adapter as a filesystem path. A storage-relative key
            # ("<survey_id>/<unique_name>") resolves against the server's
            # working directory instead, so cv2.imread returned None, detect()
            # reported "image not found" as a warning rather than an error, and
            # the job completed successfully with zero detections. An uploaded
            # PNG could therefore never produce a detection, and it looked like
            # a model that found nothing rather than a path that did not exist.
            #
            # The XTF branch already stores a resolved path here, so this also
            # makes the column mean one thing rather than two. Serving is
            # unaffected: `storage.open()` joins an absolute path unchanged.
            image_reference=str(storage.path_for(storage_reference)),
            latitude=(metadata or {}).get("latitude"),
            longitude=(metadata or {}).get("longitude"),
            heading=(metadata or {}).get("heading"),
            depth=(metadata or {}).get("depth"),
            range=(metadata or {}).get("range"),
            metadata_source="uploaded" if metadata else None,
            quality_status="ok",
        )
        db.add(frame)

    elif validation_status == FileValidationStatus.VALID and ext in SONAR_LOG_EXTENSIONS:
        # A raw sonar container is not one frame, it is thousands of pings. It
        # gets split into frames here, each carrying the position, heading and
        # timestamp read from its own ping headers -- which is what draws the
        # survey track and what lets detections be placed on a map at all.
        #
        # Detection is NOT run here. The frames land in the table and the
        # normal processing job scores them, so job stages, cancellation and
        # progress reporting all behave exactly as they do for image uploads.
        from app.services.xtf_ingest import ingest_xtf

        # storage.path_for(), NOT storage_reference. The reference is a
        # storage-relative key ("<survey_id>/<unique_name>"); resolving it to a
        # filesystem path is the storage backend's whole job. Passing the key
        # straight through made Path() interpret it relative to the server's
        # working directory, which raised FileNotFoundError inside ingest_xtf
        # and produced a file marked VALID with zero frames -- and the unit
        # tests could not see it, because they call ingest_xtf with a real path.
        created, ingest_warnings = ingest_xtf(
            db, survey_id, survey_file.id, storage.path_for(storage_reference)
        )
        if created:
            # The file carried its own metadata after all -- it was in the ping
            # headers, which is exactly the case `PENDING` was standing in for.
            survey_file.metadata_status = FileValidationStatus.VALID
        if ingest_warnings:
            # Appended rather than replacing: a metadata validation message
            # from earlier is still worth keeping.
            survey_file.validation_message = " ".join(
                m for m in [survey_file.validation_message, *ingest_warnings] if m
            )

    db.commit()
    db.refresh(survey_file)
    return survey_file


def list_survey_files(db: Session, survey_id: uuid.UUID) -> list[SurveyFile]:
    return (
        db.query(SurveyFile)
        .filter(SurveyFile.survey_id == survey_id)
        .order_by(SurveyFile.created_at.desc())
        .all()
    )


def get_survey_file_or_404(
    db: Session, survey_id: uuid.UUID, file_id: uuid.UUID
) -> SurveyFile:
    """Fetch a file, scoped to its survey.

    Scoped on purpose: an id alone would let a caller delete a file out of a
    survey they were not looking at by pasting the wrong URL, and the 404 for
    "exists, but not here" should be indistinguishable from "does not exist".
    """
    survey_file = (
        db.query(SurveyFile)
        .filter(SurveyFile.id == file_id, SurveyFile.survey_id == survey_id)
        .one_or_none()
    )
    if survey_file is None:
        raise ApiError(404, "FILE_NOT_FOUND", "Survey file was not found.")
    return survey_file


def delete_survey_file(
    db: Session,
    storage: StorageBackend,
    survey_id: uuid.UUID,
    file_id: uuid.UUID,
) -> None:
    """Remove one uploaded file from a survey, with whatever was derived from it.

    This exists for the ordinary mistake -- the wrong file dragged into the
    dropzone -- so the common case is a file with nothing hanging off it yet.
    But it deliberately also works once a file HAS been processed, because
    "I uploaded the wrong survey and only noticed after it ran" is the same
    mistake caught later, and leaving it un-deletable would mean the operator's
    only recovery is deleting the whole survey.

    What that costs is real and the UI states it before asking: `sonar_frames`
    cascades off `survey_files.file_id` and `detections` off BOTH `frame_id`
    and `source_file_id`, so every frame, detection and review belonging to this
    file goes with it. Detections from OTHER files in the survey are untouched,
    which is the whole point of doing this per-file rather than per-survey.

    Refused outright while a job is running. The cascade would pull rows out
    from under a task that is still writing to them, which surfaces as a stream
    of foreign-key errors after an apparently successful delete -- the same trap
    `survey_service.delete_survey` documents, except that one can cancel the job
    because it is removing everything. Here the job is still legitimately
    working on the survey's other files, so the honest answer is "not now".
    """
    from app.services import processing_service, survey_service

    # Serialize against a job starting concurrently -- see lock_survey_or_404.
    # Taken BEFORE the active-job read so the answer cannot go stale between
    # the check and the commit below.
    survey_service.lock_survey_or_404(db, survey_id)

    survey_file = get_survey_file_or_404(db, survey_id, file_id)

    active = processing_service.get_active_job_for_survey(db, survey_id)
    if active is not None:
        raise ApiError(
            409,
            "SURVEY_PROCESSING",
            "This survey is being processed. Wait for the job to finish, or "
            "cancel it, before removing a file.",
        )

    # Read the paths off the row before it is gone.
    storage_reference = survey_file.storage_reference

    db.delete(survey_file)
    db.commit()

    # Rows cascade; bytes do not. Same ordering and same forgiveness as
    # delete_survey: the delete has already succeeded by this point, so a
    # failure to unlink is a cleanup problem and must not become a 500.
    try:
        path = storage.path_for(storage_reference)
        # Frames were tiled to <survey_dir>/frames/<file_stem>/ (xtf_ingest's
        # FRAME_SUBDIR). Remove that directory, not the survey's whole frames/
        # tree, which holds the other files' frames too.
        frame_dir = path.parent / "frames" / path.stem
        if frame_dir.is_dir():
            shutil.rmtree(frame_dir)
        if path.is_file():
            path.unlink()
    except Exception:
        logger.exception(
            "Could not remove storage for deleted survey file %s", file_id
        )
