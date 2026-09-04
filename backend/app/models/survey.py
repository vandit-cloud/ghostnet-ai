import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import SurveyStatus


class Survey(Base):
    __tablename__ = "surveys"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sonar_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[SurveyStatus] = mapped_column(
        String(20), default=SurveyStatus.UPLOADED, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    files: Mapped[list["SurveyFile"]] = relationship(back_populates="survey", cascade="all, delete-orphan")
    jobs: Mapped[list["ProcessingJob"]] = relationship(back_populates="survey", cascade="all, delete-orphan")
    reports: Mapped[list["Report"]] = relationship(back_populates="survey", cascade="all, delete-orphan")
