import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, String, DateTime, ForeignKey, Float, JSON, UniqueConstraint, func
from sqlalchemy import false as sa_false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import Priority, ReviewStatus, Uncertainty


class Detection(Base):
    __tablename__ = "detections"
    __table_args__ = (
        UniqueConstraint("frame_id", "detection_ref", name="uq_detections_frame_ref"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Unique WITHIN A FRAME, not globally -- that is exactly what the AI
    # contract promises for `detection_id` ("Stable per-detection identifier,
    # unique within a frame", contracts/ai-output.schema.json).
    #
    # It used to be `unique=True`, a global constraint the contract never
    # backed. ghostnet mints these as "D-" + uuid4().hex[:8], i.e. 32 bits, so
    # a global constraint fails on the birthday problem rather than on any bug:
    # about a 1% chance of a collision by 10,000 stored detections, 25% by
    # 50,000 and 69% by 100,000. The symptom would have been an unhandled
    # IntegrityError killing a processing job part-way through, at a scale this
    # system is meant to reach.
    #
    # The ref is display-only -- every lookup in this codebase goes through the
    # UUID primary key -- so the global constraint bought nothing.
    detection_ref: Mapped[str] = mapped_column(String(50), nullable=False)
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
    #: Outline polygon [[x, y], ...] in frame pixels (AI contract 1.3.0).
    #: JSON, not mask_reference: a polygon does not fit a 1000-char string.
    mask_polygon: Mapped[list | None] = mapped_column(JSON, nullable=True)
    #: A review candidate, not a claim. Nets are review-only (contract 1.2.0).
    review_only: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sa_false(), nullable=False)

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
