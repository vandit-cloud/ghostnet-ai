"""Sonar geometry on sonar_frames, so detections can become coordinates.

Revision ID: 0002
Revises: 0001

The first real .xtf run placed all 40 frames on the vessel track and put ZERO
markers on the map: every detection came back with `latitude: None` and
`localization: "none"`. The AI needs nadir_col, range_resolution_m, altitude_m
and heading together with a lat/lon fix before it will emit a position, and
this table had nowhere to keep the first three -- so they were never passed,
and the detector correctly declined to invent coordinates.

All nullable. A frame from pings carrying no navigation genuinely has no
geometry, and an upload of pre-cut images never had any to begin with.
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

COLUMNS = (
    "nadir_col",
    "range_resolution_m",
    "altitude_m",
    "along_track_res_m",
    "layback_m",
    "nadir_row",
)


def upgrade() -> None:
    for name in COLUMNS:
        op.add_column("sonar_frames", sa.Column(name, sa.Float(), nullable=True))


def downgrade() -> None:
    for name in reversed(COLUMNS):
        op.drop_column("sonar_frames", name)
