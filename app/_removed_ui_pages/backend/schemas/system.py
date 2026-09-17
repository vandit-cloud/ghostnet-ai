from pydantic import BaseModel


class ComponentStatus(BaseModel):
    name: str
    state: str  # ONLINE | ACTIVE | LIVE | CONNECTING | OFFLINE | STALE | ERROR
    detail: str | None = None


class SystemStatus(BaseModel):
    components: list[ComponentStatus]
    checked_at: str


class SystemConfig(BaseModel):
    app_name: str
    max_upload_size_mb: int
    allowed_upload_extensions: list[str]
