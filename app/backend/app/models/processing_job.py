import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import JobStage, JobStatus


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    survey_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(50), default="detection", nullable=False)
    status: Mapped[JobStatus] = mapped_column(String(20), default=JobStatus.QUEUED, nullable=False)
    stage: Mapped[JobStage] = mapped_column(String(20), default=JobStage.QUEUED, nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    frames_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    frames_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    frames_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    detections_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    survey: Mapped["Survey"] = relationship(back_populates="jobs")
