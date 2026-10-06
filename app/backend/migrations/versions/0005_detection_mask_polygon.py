"""Detection outline polygon and review_only flag.

Revision ID: 0005
Revises: 0004

Adds:
- detections.mask_polygon (JSON, nullable) -- the outline polygon the AI
  contract's `mask` field carries from 1.3.0, filled for ghost_net when the
  net segmentation model runs. A new column rather than mask_reference: that
  is a String(1000), and a polygon of up to 200 vertices does not fit.
- detections.review_only (bool, default false) -- contract 1.2.0 marks nets
  as review candidates rather than claims; the backend dropped the flag on
  ingest until now.

Existing rows: mask_polygon is NULL (they never had one) and review_only is
false via server_default. Pre-existing ghost_net rows were review candidates
too but are not backfilled here -- re-processing a survey rewrites them with
the flag, and guessing it in a migration would be the kind of silent
data change this project avoids.

mask_reference is left in place and no longer written. Dropping it is a
separate, destructive migration, deliberately not bundled with this one.
"""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("detections", sa.Column("mask_polygon", sa.JSON(), nullable=True))
    op.add_column(
        "detections",
        sa.Column("review_only", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("detections", "review_only")
    op.drop_column("detections", "mask_polygon")
