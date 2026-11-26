# Serve SwiftTerm WASM locally and expose it through Cloudflare Quick Tunnel.
# Phone can open the https://*.trycloudflare.com URL (works off LAN / 4G).
#
# Usage (PowerShell, from anywhere):
#   powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\Documents\SwiftTerm\scripts\serve-via-cloudflare-tunnel.ps1"
#
# Requires: Python 3, and cloudflared (installed automatically via winget if missing).

$ErrorActionPreference = "Stop"
$Site = Join-Path $env:USERPROFILE "Documents\SwiftTerm\Web\cloudflare\site"
if (-not (Test-Path (Join-Path $Site "index.html"))) {
  Write-Error "Missing site at $Site — clone https://github.com/jiaomeimei0-prog/SwiftTerm.git into Documents first."
}

function Ensure-Cloudflared {
  if (Get-Command cloudflared -ErrorAction SilentlyContinue) { return }
  Write-Host "Installing cloudflared (winget)..."
  winget install --id Cloudflare.cloudflared -e --accept-source-agreements --accept-package-agreements
  $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
              [System.Environment]::GetEnvironmentVariable("Path", "User")
  if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
    Write-Error "cloudflared not on PATH. Close PowerShell, reopen, and re-run this script."
  }
}

Ensure-Cloudflared

# Free port 8765 if a previous server is stuck
Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }

Write-Host "Starting local server on 127.0.0.1:8765 ..."
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }
if (-not $py) { Write-Error "Python not found. Install: winget install Python.Python.3.12" }

$server = Start-Process -FilePath $py.Source -ArgumentList @("-m", "http.server", "8765", "--bind", "127.0.0.1") `
  -WorkingDirectory $Site -PassThru -WindowStyle Minimized

Start-Sleep -Seconds 1
try {
  Write-Host ""
  Write-Host "Cloudflare Quick Tunnel — copy the https://....trycloudflare.com URL below onto your phone."
  Write-Host "Keep this window open. Ctrl+C stops the tunnel (then close the python window if needed)."
  Write-Host ""
  & cloudflared tunnel --url http://127.0.0.1:8765
}
finally {
  if ($server -and -not $server.HasExited) { Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue }
}
