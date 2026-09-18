@echo off
REM ===========================================================================
REM  GhostNet-AI - double-click to bring the whole stack up.
REM
REM  Checks the install, starts PostgreSQL, the API and the web console in the
REM  right order, rebuilds the frontend only if sources changed since the last
REM  build, waits for each to actually answer, then opens the browser.
REM
REM  The real logic is scripts\launch\launch.ps1 -- this wrapper exists only so
REM  the thing is double-clickable, since .ps1 files open in an editor by
REM  default rather than running.
REM ===========================================================================
title GhostNet-AI launcher
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\launch\launch.ps1"
if errorlevel 1 pause
