import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AuditLog(Base):
    """Who did what, to what, when, and whether it succeeded.

    ``actor_username`` is a snapshot, not a join target: a user row can later
    be deleted (or renamed), and the audit record must still read correctly.
    ``detail`` is structured but must never carry secrets (passwords, raw
    tokens) -- callers are responsible for that, see audit_service.log.
    """

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
