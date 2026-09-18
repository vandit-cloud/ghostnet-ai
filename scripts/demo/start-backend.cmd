@echo off
REM Auto-start wrapper for the GhostNet-AI backend (Task Scheduler runs this at boot).
REM Single worker on purpose: processing_service keeps its running-job table in
REM process memory and slowapi's rate limiter is in-memory too, so a second
REM worker silently breaks job cancellation and halves the rate limits.
cd /d "E:\ghostnet-docker-demo\app\backend"
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
