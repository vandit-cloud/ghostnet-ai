import mimetypes
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.errors import ApiError
from app.models.sonar_frame import SonarFrame
from app.storage.local import StorageBackend, get_storage_backend

router = APIRouter(prefix="/frames", tags=["frames"], dependencies=[Depends(get_current_user)])


@router.get("/{frame_id}/image")
def get_frame_image(
    frame_id: uuid.UUID,
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage_backend),
) -> StreamingResponse:
    frame = db.get(SonarFrame, frame_id)
    if not frame:
        raise ApiError(404, "FRAME_NOT_FOUND", "Sonar frame was not found.")

    media_type = mimetypes.guess_type(frame.image_reference)[0] or "application/octet-stream"
    stream = storage.open(frame.image_reference)
    return StreamingResponse(stream, media_type=media_type)
