@echo off
REM Auto-start wrapper for the GhostNet-AI frontend (Task Scheduler runs this at boot).
REM Production build, not `next dev` -- dev wedged under concurrent .next writes
REM and served pages in seconds rather than milliseconds.
cd /d "E:\ghostnet-docker-demo\app\frontend"
npm run start
