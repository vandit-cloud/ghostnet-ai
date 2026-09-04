import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import String, DateTime, ForeignKey, Float, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import Priority, ReviewStatus, Uncertainty


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    detection_ref: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    survey_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False)
    frame_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sonar_frames.id", ondelete="CASCADE"), nullable=False)
    source_file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("survey_files.id", ondelete="CASCADE"), nullable=False)

    detection_class: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    calibrated_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    uncertainty: Mapped[Uncertainty | None] = mapped_column(String(20), nullable=True)

    bbox_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_w: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_h: Mapped[float | None] = mapped_column(Float, nullable=True)
    mask_reference: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    location: Mapped[str | None] = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=True)
    position_error_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    localization_method: Mapped[str | None] = mapped_column(String(50), nullable=True)

    depth: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[float | None] = mapped_column(Float, nullable=True)
    length: Mapped[float | None] = mapped_column(Float, nullable=True)
    area: Mapped[float | None] = mapped_column(Float, nullable=True)
    dimension_status: Mapped[str | None] = mapped_column(String(20), nullable=True)

    priority: Mapped[Priority] = mapped_column(String(20), default=Priority.MEDIUM, nullable=False)
    review_status: Mapped[ReviewStatus] = mapped_column(
        String(30), default=ReviewStatus.PENDING, nullable=False
    )
    model_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    evidence_summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    frame: Mapped["SonarFrame"] = relationship(back_populates="detections")
    reviews: Mapped[list["DetectionReview"]] = relationship(
        back_populates="detection", cascade="all, delete-orphan"
    )
