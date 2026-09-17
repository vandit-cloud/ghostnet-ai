from datetime import datetime, timedelta, timezone

from fastapi import Request
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.user import User


def _client_ip(request: Request | None) -> str | None:
    if request is None or request.client is None:
        return None
    return request.client.host


def log(
    db: Session,
    *,
    actor: User | None,
    action: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    outcome: str = "success",
    detail: dict | None = None,
    actor_username: str | None = None,
    request: Request | None = None,
) -> AuditLog:
    """Record one audit entry. Never pass secrets (passwords, raw tokens) in
    `detail` -- it is stored and later readable by any ADMIN.

    `actor` is the authenticated user when there is one; `actor_username` lets
    a caller record a *claimed* identity for events where authentication
    itself failed (e.g. a login attempt for a username that has no matching
    session yet).
    """
    entry = AuditLog(
        actor_user_id=actor.id if actor else None,
        actor_username=actor.username if actor else actor_username,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        outcome=outcome,
        detail=detail,
        ip_address=_client_ip(request),
    )
    db.add(entry)
    db.commit()
    return entry


def count_recent_login_failures(db: Session, username: str, window_minutes: int) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    return db.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(
            and_(
                AuditLog.action == "auth.login",
                AuditLog.outcome == "failure",
                AuditLog.actor_username == username,
                AuditLog.created_at >= cutoff,
            )
        )
    ) or 0


def list_audit_logs(
    db: Session,
    page: int,
    page_size: int,
    actor_username: str | None = None,
    action: str | None = None,
    entity_type: str | None = None,
) -> tuple[list[AuditLog], int]:
    conditions = []
    if actor_username is not None:
        conditions.append(AuditLog.actor_username == actor_username)
    if action is not None:
        conditions.append(AuditLog.action == action)
    if entity_type is not None:
        conditions.append(AuditLog.entity_type == entity_type)

    where_clause = and_(*conditions) if conditions else True

    total = db.scalar(select(func.count()).select_from(AuditLog).where(where_clause)) or 0
    items = (
        db.query(AuditLog)
        .where(where_clause)
        .order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total
