@echo off
REM Persistent launcher — leaves HTTP + cloudflared windows open.
cd /d "%USERPROFILE%\Documents\SwiftTerm"
powershell -ExecutionPolicy Bypass -File "%~dp0windows-persistent-e2e.ps1"
pause
