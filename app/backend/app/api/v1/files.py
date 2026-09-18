import uuid

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user, require_roles
from app.models.enums import Role
from app.models.user import User
from app.schemas.survey_file import SurveyFileOut
from app.services import audit_service, file_service, survey_service
from app.storage.local import StorageBackend, get_storage_backend

router = APIRouter(prefix="/surveys", tags=["files"], dependencies=[Depends(get_current_user)])


@router.post("/{survey_id}/files", response_model=SurveyFileOut, status_code=201)
def upload_file(
    request: Request,
    survey_id: uuid.UUID,
    file: UploadFile = File(...),
    metadata: str | None = Form(default=None),
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage_backend),
    user: User = Depends(require_roles(Role.ADMIN, Role.OPERATOR)),
) -> SurveyFileOut:
    survey_service.get_survey_or_404(db, survey_id)
    survey_file = file_service.upload_survey_file(
        db, storage, survey_id, file.filename or "upload", file.file, metadata
    )
    audit_service.log(
        db,
        actor=user,
        action="file.uploaded",
        entity_type="survey_file",
        entity_id=str(survey_file.id),
        detail={"survey_id": str(survey_id), "filename": survey_file.filename},
        request=request,
    )
    return SurveyFileOut.model_validate(survey_file)


@router.get("/{survey_id}/files", response_model=list[SurveyFileOut])
def list_files(survey_id: uuid.UUID, db: Session = Depends(get_db)) -> list[SurveyFileOut]:
    survey_service.get_survey_or_404(db, survey_id)
    files = file_service.list_survey_files(db, survey_id)
    return [SurveyFileOut.model_validate(f) for f in files]


@router.delete("/{survey_id}/files/{file_id}", status_code=204, response_class=Response)
def delete_file(
    request: Request,
    survey_id: uuid.UUID,
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage_backend),
    user: User = Depends(require_roles(Role.ADMIN, Role.OPERATOR)),
) -> Response:
    """Remove one uploaded file and everything derived from it.

    Same roles as upload: whoever can put a file on a survey can take it off
    again. 409 while the survey is processing -- see file_service for why.

    The file's identifying details are READ before the delete and LOGGED after
    it. Both halves of that matter. Read first, because once the row is gone
    there is nothing left to read them off, and an audit trail that can only say
    "some file was deleted" does not answer the question anyone asks of it.
    Log after, because the delete can still be refused -- a 409 while a job is
    running is the ordinary case -- and an entry written beforehand would record
    a deletion that never happened. That is worse than no entry at all: it is a
    trail that lies in exactly the situation it exists to explain.
    """
    survey_service.get_survey_or_404(db, survey_id)
    survey_file = file_service.get_survey_file_or_404(db, survey_id, file_id)

    # Snapshot before the cascade takes the row with it.
    detail = {
        "survey_id": str(survey_id),
        "filename": survey_file.filename,
        "format": survey_file.format,
        "size": survey_file.size,
        "checksum": survey_file.checksum,
    }

    file_service.delete_survey_file(db, storage, survey_id, file_id)

    audit_service.log(
        db,
        actor=user,
        action="file.deleted",
        entity_type="survey_file",
        entity_id=str(file_id),
        detail=detail,
        request=request,
    )
    return Response(status_code=204)
