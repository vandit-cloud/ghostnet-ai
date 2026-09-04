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

    # --- sonar geometry: what turns a detection into a coordinate -----------
    #
    # A detection is placed on the map only when nadir_col, range_resolution_m,
    # altitude_m and heading are ALL present alongside a lat/lon fix. Without
    # them the AI reports the detection with no position rather than inventing
    # one, and `markers` on the map endpoint comes back empty while the vessel
    # `track` still draws -- which is exactly what happened on the first real
    # .xtf run, because these columns did not exist.
    #
    # They are NOT derivable from `depth` and `range` above:
    #   altitude_m          towfish height ABOVE THE SEABED (depth is water depth)
    #   range_resolution_m  metres per PIXEL (range is the whole swath width)
    #
    # Stored PER FRAME, not per ping: `nadir_col` shifts as the waterfall is cut
    # across-track (1024 for the first tile of a ping block, 384 for the next),
    # so one value per ping would misplace every tile but the first.
    #
    # ghostnet.iter_survey_frames already returns all six on `frame.meta`, read
    # from the ping headers -- nobody types them in.
    nadir_col: Mapped[float | None] = mapped_column(Float, nullable=True)
    range_resolution_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    altitude_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    along_track_res_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    layback_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    nadir_row: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    metadata_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    source_file: Mapped["SurveyFile"] = relationship(back_populates="frames")
    detections: Mapped[list["Detection"]] = relationship(back_populates="frame", cascade="all, delete-orphan")
