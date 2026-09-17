import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1 import (
    analytics,
    auth,
    dashboard,
    detections,
    files,
    frames,
    health,
    maps,
    processing,
    reports,
    surveys,
    ws,
)
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.errors import ApiError, api_error_handler, unhandled_exception_handler
from app.core.limiter import limiter
from app.services.auth_service import ensure_seed_admin

logging.basicConfig(level=logging.INFO)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        ensure_seed_admin(db)
    finally:
        db.close()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(health.router, prefix=settings.api_v1_prefix)
app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(surveys.router, prefix=settings.api_v1_prefix)
app.include_router(dashboard.router, prefix=settings.api_v1_prefix)
app.include_router(analytics.router, prefix=settings.api_v1_prefix)
app.include_router(files.router, prefix=settings.api_v1_prefix)
app.include_router(frames.router, prefix=settings.api_v1_prefix)
app.include_router(processing.router, prefix=settings.api_v1_prefix)
app.include_router(detections.router, prefix=settings.api_v1_prefix)
app.include_router(maps.router, prefix=settings.api_v1_prefix)
app.include_router(reports.router, prefix=settings.api_v1_prefix)
app.include_router(ws.router, prefix=settings.api_v1_prefix)
