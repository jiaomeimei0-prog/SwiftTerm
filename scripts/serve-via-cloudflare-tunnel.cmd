@echo off
setlocal
cd /d "%USERPROFILE%\Documents\SwiftTerm\Web\cloudflare\site"
if not exist index.html (
  echo Missing site. Clone repo to Documents\SwiftTerm first.
  exit /b 1
)

where cloudflared >nul 2>&1
if errorlevel 1 (
  echo Installing cloudflared...
  winget install --id Cloudflare.cloudflared -e --accept-source-agreements --accept-package-agreements
  echo Close this window, open a NEW cmd, and run this script again.
  pause
  exit /b 1
)

echo.
echo === WINDOW A style: starting python on 127.0.0.1:8765 ===
start "SwiftTerm-local-8765" /min cmd /c "cd /d \"%CD%\" && python -m http.server 8765 --bind 127.0.0.1"
timeout /t 2 >nul

echo.
echo === Cloudflare Tunnel — copy the https://....trycloudflare.com line below ===
echo === Open THAT url on your phone (NOT 127.0.0.1) ===
echo.
cloudflared tunnel --url http://127.0.0.1:8765
echo.
echo Tunnel stopped. Closing local python window if still open...
taskkill /FI "WINDOWTITLE eq SwiftTerm-local-8765*" /F >nul 2>&1
pause
