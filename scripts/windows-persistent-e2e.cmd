@echo off
REM Persistent launcher - leaves HTTP + cloudflared windows open.
cd /d "%~dp0.."
powershell -ExecutionPolicy Bypass -File "%~dp0windows-persistent-e2e.ps1"
pause
