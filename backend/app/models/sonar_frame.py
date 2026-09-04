import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Float, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class SonarFrame(Base):
    __tablename__ = "sonar_frames"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    survey_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False)
    file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("survey_files.id", ondelete="CASCADE"), nullable=False)
    frame_id: Mapped[str] = mapped_column(String(100), nullable=False)
    ping_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    image_reference: Mapped[str] = mapped_column(String(1000), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    heading: Mapped[float | None] = mapped_column(Float, nullable=True)
    depth: Mapped[float | None] = mapped_column(Float, nullable=True)
    range: Mapped[float | None] = mapped_column(Float, nullable=True)
    resolution: Mapped[str | None] = mapped_column(String(50), nullable=True)
    quality_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    metadata_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    source_file: Mapped["SurveyFile"] = relationship(back_populates="frames")
    detections: Mapped[list["Detection"]] = relationship(back_populates="frame", cascade="all, delete-orphan")
