import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import ReviewStatus


class DetectionReview(Base):
    __tablename__ = "detection_reviews"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    detection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("detections.id", ondelete="CASCADE"), nullable=False)
    reviewer: Mapped[str | None] = mapped_column(String(150), nullable=True)
    decision: Mapped[ReviewStatus] = mapped_column(String(30), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    detection: Mapped["Detection"] = relationship(back_populates="reviews")
