from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "GhostNet-AI Backend"
    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+psycopg://ghostnet:ghostnet@localhost:5432/ghostnet"

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 12

    refresh_token_expires_days: int = 14
    password_reset_expires_minutes: int = 30

    # Brute-force lockout: N failed logins for the same username within the
    # trailing window blocks further attempts, derived from audit_logs rather
    # than a second tracking table.
    login_failure_limit: int = 5
    login_failure_window_minutes: int = 15

    # General API rate limit (per authenticated user/IP) and the stricter
    # login-specific one, both enforced via slowapi's in-memory store --
    # correct for the single-uvicorn-worker deployment this repo ships
    # (docker-compose.yml has no Redis).
    rate_limit_default: str = "60/minute"
    rate_limit_login: str = "5/minute"

    max_concurrent_jobs_per_user: int = 2

    seed_admin_username: str = "operator"
    seed_admin_password: str = "operator123"

    storage_root: str = "./uploads"
    max_upload_size_mb: int = 200
    allowed_upload_extensions: tuple[str, ...] = (".xtf", ".jsf", ".tif", ".tiff", ".png", ".jpg", ".jpeg", ".json", ".csv")

    # Both spellings of the dev frontend. An origin is matched as a literal
    # string, so a browser opened at 127.0.0.1:3000 is a different origin from
    # one opened at localhost:3000 and would otherwise be refused.
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
