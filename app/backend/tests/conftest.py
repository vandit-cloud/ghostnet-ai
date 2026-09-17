import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://ghostnet:ghostnet@localhost:5432/ghostnet_test"),
)

from app.core import db as db_module  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.limiter import limiter  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User  # noqa: E402

settings = get_settings()


@pytest.fixture(scope="session", autouse=True)
def _setup_database():
    """Tests run against a real Postgres+PostGIS instance (see docker-compose
    'db' service / README) since detections use a PostGIS geometry column
    that has no sqlite equivalent."""
    with db_module.engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        conn.commit()
    db_module.Base.metadata.create_all(db_module.engine)
    yield
    db_module.Base.metadata.drop_all(db_module.engine)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """The rate limiter's in-memory storage is a module-level singleton that
    otherwise persists for the whole pytest process, so one test's login
    attempts would count against the next test's quota."""
    limiter.reset()
    yield


@pytest.fixture()
def db_session():
    session = db_module.SessionLocal()
    yield session
    session.close()


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def auth_identity():
    """The authenticated test user, headers plus the username behind them.

    Tests that assert on server-recorded identity (audit trails) need to know
    who the token belongs to; `auth_headers` alone hides it.
    """
    session = db_module.SessionLocal()
    username = f"test-{uuid.uuid4().hex[:8]}"
    user = User(username=username, password_hash=hash_password("password123"), display_name="Test User")
    session.add(user)
    session.commit()
    session.close()
    token = create_access_token(username)
    return {"username": username, "headers": {"Authorization": f"Bearer {token}"}}


@pytest.fixture()
def auth_headers(auth_identity):
    return auth_identity["headers"]
