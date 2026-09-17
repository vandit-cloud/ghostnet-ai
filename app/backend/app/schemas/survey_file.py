import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import FileValidationStatus


class SurveyFileOut(BaseModel):
    id: uuid.UUID
    survey_id: uuid.UUID
    filename: str
    format: str
    size: int
    checksum: str
    validation_status: FileValidationStatus
    validation_message: str | None
    metadata_status: FileValidationStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
