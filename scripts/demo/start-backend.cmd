@echo off
REM Auto-start wrapper for the GhostNet-AI backend (Task Scheduler runs this at boot).
REM Single worker on purpose: processing_service keeps its running-job table in
REM process memory and slowapi's rate limiter is in-memory too, so a second
REM worker silently breaks job cancellation and halves the rate limits.
cd /d "E:\ghostnet-docker-demo\app\backend"
REM Apply database migrations first. Nothing else runs them, and a model that
REM gains a column with its migration unapplied keeps /health and login green
REM while every detection query 500s -- the dashboards just render empty
REM (25 Sep 2026, migration 0005). Re-running an applied migration is a no-op.
REM On failure, stop here: serving on a stale schema is the silent failure.
.venv\Scripts\python.exe -m alembic upgrade head
if errorlevel 1 (
    echo.
    echo   DATABASE MIGRATION FAILED - the backend was NOT started.
    echo   Fix the error above, then run this script again.
    exit /b 1
)
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
