import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.schemas.survey_file import SurveyFileOut
from app.services import file_service, survey_service
from app.storage.local import StorageBackend, get_storage_backend

router = APIRouter(prefix="/surveys", tags=["files"], dependencies=[Depends(get_current_user)])


@router.post("/{survey_id}/files", response_model=SurveyFileOut, status_code=201)
def upload_file(
    survey_id: uuid.UUID,
    file: UploadFile = File(...),
    metadata: str | None = Form(default=None),
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage_backend),
) -> SurveyFileOut:
    survey_service.get_survey_or_404(db, survey_id)
    survey_file = file_service.upload_survey_file(
        db, storage, survey_id, file.filename or "upload", file.file, metadata
    )
    return SurveyFileOut.model_validate(survey_file)


@router.get("/{survey_id}/files", response_model=list[SurveyFileOut])
def list_files(survey_id: uuid.UUID, db: Session = Depends(get_db)) -> list[SurveyFileOut]:
    survey_service.get_survey_or_404(db, survey_id)
    files = file_service.list_survey_files(db, survey_id)
    return [SurveyFileOut.model_validate(f) for f in files]
