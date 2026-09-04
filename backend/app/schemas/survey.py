import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import SurveyStatus


class SurveyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    source: str | None = None
    sonar_type: str | None = None


class SurveyUpdate(BaseModel):
    name: str | None = None
    source: str | None = None
    sonar_type: str | None = None
    status: SurveyStatus | None = None


class SurveyOut(BaseModel):
    id: uuid.UUID
    name: str
    source: str | None
    sonar_type: str | None
    status: SurveyStatus
    file_count: int = 0
    processed_count: int = 0
    detection_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SurveyDetailOut(SurveyOut):
    review_count: int = 0
