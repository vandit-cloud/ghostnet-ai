"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-30

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(100), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(150), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "surveys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("source", sa.String(200), nullable=True),
        sa.Column("sonar_type", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="UPLOADED"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "survey_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("survey_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("storage_reference", sa.String(1000), nullable=False),
        sa.Column("format", sa.String(20), nullable=False),
        sa.Column("size", sa.BigInteger, nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("validation_status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("validation_message", sa.String(500), nullable=True),
        sa.Column("metadata_status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_survey_files_survey_id", "survey_files", ["survey_id"])

    op.create_table(
        "sonar_frames",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("survey_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("survey_files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("frame_id", sa.String(100), nullable=False),
        sa.Column("ping_id", sa.String(100), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("image_reference", sa.String(1000), nullable=False),
        sa.Column("latitude", sa.Float, nullable=True),
        sa.Column("longitude", sa.Float, nullable=True),
        sa.Column("heading", sa.Float, nullable=True),
        sa.Column("depth", sa.Float, nullable=True),
        sa.Column("range", sa.Float, nullable=True),
        sa.Column("resolution", sa.String(50), nullable=True),
        sa.Column("quality_status", sa.String(50), nullable=True),
        sa.Column("metadata_source", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_sonar_frames_survey_id", "sonar_frames", ["survey_id"])

    op.create_table(
        "processing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("survey_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(50), nullable=False, server_default="detection"),
        sa.Column("status", sa.String(20), nullable=False, server_default="QUEUED"),
        sa.Column("stage", sa.String(20), nullable=False, server_default="QUEUED"),
        sa.Column("progress", sa.Integer, nullable=False, server_default="0"),
        sa.Column("frames_total", sa.Integer, nullable=False, server_default="0"),
        sa.Column("frames_processed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("frames_failed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("detections_found", sa.Integer, nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_summary", sa.Text, nullable=True),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_processing_jobs_survey_id", "processing_jobs", ["survey_id"])

    op.create_table(
        "detections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("detection_ref", sa.String(50), nullable=False, unique=True),
        sa.Column("survey_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False),
        sa.Column("frame_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sonar_frames.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("survey_files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("detection_class", sa.String(50), nullable=False),
        sa.Column("raw_score", sa.Float, nullable=True),
        sa.Column("calibrated_confidence", sa.Float, nullable=True),
        sa.Column("uncertainty", sa.String(20), nullable=True),
        sa.Column("bbox_x", sa.Float, nullable=True),
        sa.Column("bbox_y", sa.Float, nullable=True),
        sa.Column("bbox_w", sa.Float, nullable=True),
        sa.Column("bbox_h", sa.Float, nullable=True),
        sa.Column("mask_reference", sa.String(1000), nullable=True),
        sa.Column("latitude", sa.Float, nullable=True),
        sa.Column("longitude", sa.Float, nullable=True),
        sa.Column("location", geoalchemy2.Geometry(geometry_type="POINT", srid=4326), nullable=True),
        sa.Column("position_error_m", sa.Float, nullable=True),
        sa.Column("localization_method", sa.String(50), nullable=True),
        sa.Column("depth", sa.Float, nullable=True),
        sa.Column("width", sa.Float, nullable=True),
        sa.Column("length", sa.Float, nullable=True),
        sa.Column("area", sa.Float, nullable=True),
        sa.Column("dimension_status", sa.String(20), nullable=True),
        sa.Column("priority", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("review_status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("model_version", sa.String(100), nullable=True),
        sa.Column("evidence_summary", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_detections_survey_id", "detections", ["survey_id"])
    op.create_index("ix_detections_frame_id", "detections", ["frame_id"])
    op.create_index("ix_detections_review_status", "detections", ["review_status"])
    op.execute("CREATE INDEX ix_detections_location ON detections USING GIST (location)")

    op.create_table(
        "detection_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("detection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("detections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer", sa.String(150), nullable=True),
        sa.Column("decision", sa.String(30), nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_detection_reviews_detection_id", "detection_reviews", ["detection_id"])

    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("survey_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("format", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="QUEUED"),
        sa.Column("filters", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("storage_reference", sa.String(1000), nullable=True),
        sa.Column("error_summary", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_reports_survey_id", "reports", ["survey_id"])


def downgrade() -> None:
    op.drop_table("reports")
    op.drop_table("detection_reviews")
    op.drop_table("detections")
    op.drop_table("processing_jobs")
    op.drop_table("sonar_frames")
    op.drop_table("survey_files")
    op.drop_table("surveys")
    op.drop_table("users")
