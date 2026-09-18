import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, BigInteger, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import FileValidationStatus


class SurveyFile(Base):
    __tablename__ = "survey_files"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    survey_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_reference: Mapped[str] = mapped_column(String(1000), nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    validation_status: Mapped[FileValidationStatus] = mapped_column(
        String(20), default=FileValidationStatus.PENDING, nullable=False
    )
    validation_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metadata_status: Mapped[FileValidationStatus] = mapped_column(
        String(20), default=FileValidationStatus.PENDING, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    survey: Mapped["Survey"] = relationship(back_populates="files")
  # passive_deletes: let the DATABASE do the cascade.
    #
    # The FK already carries ON DELETE CASCADE (see migrations 0001), so
    # without this SQLAlchemy does the work twice: it SELECTs every child row
    # into the session and emits one DELETE per row, then the database cascades
    # anyway. On a real .xtf that is thousands of frames and tens of thousands
    # of detections loaded into memory and deleted one statement at a time,
    # inside a synchronous request holding its locks the whole way.
    frames: Mapped[list["SonarFrame"]] = relationship(
        back_populates="source_file", cascade="all, delete-orphan", passive_deletes=True
    )
