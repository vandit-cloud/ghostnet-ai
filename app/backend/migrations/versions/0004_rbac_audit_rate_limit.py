"""RBAC, audit trail, refresh/reset tokens, per-user job quota.

Revision ID: 0004
Revises: 0003

Adds:
- users.role / users.is_active (RBAC -- remaning.md item 2)
- refresh_tokens, password_reset_tokens (auth: logout/refresh/admin-issued
  password reset -- remaning.md item 2)
- audit_logs (remaning.md item 3)
- surveys.created_by_user_id (per-user concurrent-job quota -- item 10)

Existing rows: the seeded operator account is promoted to ADMIN in code
(app.services.auth_service.ensure_seed_admin), not here -- it is created at
application startup, not by a migration. Any other pre-existing user row
gets the column default (OPERATOR, active) via server_default.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("role", sa.String(20), nullable=False, server_default="operator"))
    op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))

    op.add_column(
        "surveys",
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False, unique=True),
        sa.Column(
            "issued_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("actor_username", sa.String(100), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("entity_id", sa.String(100), nullable=True),
        sa.Column("outcome", sa.String(20), nullable=False, server_default="success"),
        sa.Column("detail", sa.JSON, nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("password_reset_tokens")
    op.drop_table("refresh_tokens")
    op.drop_column("surveys", "created_by_user_id")
    op.drop_column("users", "is_active")
    op.drop_column("users", "role")
