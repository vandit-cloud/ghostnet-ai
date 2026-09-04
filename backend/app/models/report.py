import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, JSON, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import ReportFormat, ReportStatus, ReportType


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    survey_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[ReportType] = mapped_column(String(30), nullable=False)
    format: Mapped[ReportFormat] = mapped_column(String(10), nullable=False)
    status: Mapped[ReportStatus] = mapped_column(String(20), default=ReportStatus.QUEUED, nullable=False)
    filters: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    storage_reference: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    survey: Mapped["Survey"] = relationship(back_populates="reports")
