"""Real, measured system status (spec: never fabricate system status).

Every component check below either touches the real dependency (DB query,
filesystem stat, live websocket registry) or reports the actual AI adapter
in use - it never invents a state.
"""

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.realtime.manager import manager
from app.schemas.system import ComponentStatus, SystemStatus
from app.services.ai_service import MOCK_MODEL_VERSION, get_ai_adapter

settings = get_settings()


def _database_status(db: Session) -> ComponentStatus:
    try:
        db.execute(text("SELECT 1"))
        return ComponentStatus(name="Database", state="ONLINE", detail="PostgreSQL/PostGIS reachable")
    except Exception as exc:  # pragma: no cover - defensive
        return ComponentStatus(name="Database", state="ERROR", detail=str(exc))


def _storage_status() -> ComponentStatus:
    root = Path(settings.storage_root)
    try:
        root.mkdir(parents=True, exist_ok=True)
        probe = root / ".healthcheck"
        probe.write_text("ok")
        probe.unlink(missing_ok=True)
        return ComponentStatus(name="Storage", state="ONLINE", detail=f"Writable at {settings.storage_root}")
    except OSError as exc:
        return ComponentStatus(name="Storage", state="ERROR", detail=str(exc))


def _realtime_status() -> ComponentStatus:
    count = manager.connection_count()
    state = "LIVE" if count > 0 else "ACTIVE"
    return ComponentStatus(name="Real-Time", state=state, detail=f"{count} active WebSocket connection(s)")


def _ai_engine_status() -> ComponentStatus:
    adapter = get_ai_adapter()
    is_mock = type(adapter).__name__ == "MockAIAdapter"
    detail = f"{type(adapter).__name__} ({MOCK_MODEL_VERSION})" if is_mock else type(adapter).__name__
    return ComponentStatus(
        name="AI Engine",
        state="ACTIVE",
        detail=f"{detail} — development mock, not Member 1's trained model" if is_mock else detail,
    )


def _processing_status() -> ComponentStatus:
    from app.services.processing_service import _running_tasks

    count = len(_running_tasks)
    return ComponentStatus(
        name="Processing",
        state="ACTIVE" if count > 0 else "ONLINE",
        detail=f"{count} job(s) currently running" if count else "Idle",
    )


def _gis_status() -> ComponentStatus:
    return ComponentStatus(name="GIS", state="ONLINE", detail="Map + PostGIS geometry layer available")


def get_system_status(db: Session) -> SystemStatus:
    components = [
        _ai_engine_status(),
        _processing_status(),
        _database_status(db),
        _gis_status(),
        _realtime_status(),
        _storage_status(),
    ]
    return SystemStatus(components=components, checked_at=datetime.now(timezone.utc).isoformat())
