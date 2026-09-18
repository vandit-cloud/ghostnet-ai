@echo off
REM Stop the GhostNet-AI API and web console (leaves PostgreSQL running, since
REM it is a shared Windows service other things may be using).
title GhostNet-AI shutdown
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\launch\stop.ps1"
pause
