"""detection_ref is unique per FRAME, not globally.

Revision ID: 0003
Revises: 0002

`detections.detection_ref` carried a global UNIQUE constraint. The AI contract
only ever promised uniqueness within a frame -- contracts/ai-output.schema.json
describes detection_id as "Stable per-detection identifier, unique within a
frame" -- so the database was enforcing a guarantee its producer does not make.

ghostnet mints the ref as "D-" + uuid4().hex[:8]: 32 bits. Against a GLOBAL
constraint that is a birthday problem, not a bug -- roughly 1% chance of a
collision by 10,000 stored detections, 25% by 50,000, 69% by 100,000. The
failure would have been an unhandled IntegrityError aborting a processing job
mid-survey, and it gets more likely the more the system is used.

The ref is display-only; every lookup goes through the UUID primary key.
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("detections_detection_ref_key", "detections", type_="unique")
    op.create_unique_constraint(
        "uq_detections_frame_ref", "detections", ["frame_id", "detection_ref"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_detections_frame_ref", "detections", type_="unique")
    op.create_unique_constraint(
        "detections_detection_ref_key", "detections", ["detection_ref"]
    )
