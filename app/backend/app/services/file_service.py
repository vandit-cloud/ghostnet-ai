import json
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
