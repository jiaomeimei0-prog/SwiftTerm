# Serve SwiftTerm WASM locally and expose it through Cloudflare Quick Tunnel.
# Phone can open the https://*.trycloudflare.com URL (works off LAN / 4G).
#
# Usage (Windows PowerShell 5.1+):
#   cd $env:USERPROFILE\Documents\SwiftTerm
#   powershell -ExecutionPolicy Bypass -File .\scripts\serve-via-cloudflare-tunnel.ps1

$ErrorActionPreference = "Stop"

$Site = Join-Path $env:USERPROFILE "Documents\SwiftTerm\Web\cloudflare\site"
$Index = Join-Path $Site "index.html"
if (-not (Test-Path -LiteralPath $Index)) {
    throw "Missing site at $Site - clone https://github.com/jiaomeimei0-prog/SwiftTerm.git into Documents first."
}

function Refresh-Path {
    $machine = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [System.Environment]::GetEnvironmentVariable("Path", "User")
    if ($null -eq $machine) { $machine = "" }
    if ($null -eq $user) { $user = "" }
    $env:Path = $machine + ";" + $user
}

function Ensure-Cloudflared {
    Refresh-Path
    if (Get-Command cloudflared -ErrorAction SilentlyContinue) {
        return
    }
    Write-Host "Installing cloudflared (winget)..."
    winget install --id Cloudflare.cloudflared -e --accept-source-agreements --accept-package-agreements
    Refresh-Path
    if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
        throw "cloudflared not on PATH. Close PowerShell, reopen, and re-run this script."
    }
}

Ensure-Cloudflared

# Free port 8765 if a previous server is stuck
$listeners = Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue
if ($listeners) {
    $listeners | ForEach-Object {
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}

$pyCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pyCmd) {
    $pyCmd = Get-Command py -ErrorAction SilentlyContinue
}
if (-not $pyCmd) {
    throw "Python not found. Install: winget install Python.Python.3.12"
}

Write-Host "Starting local server on 127.0.0.1:8765 ..."
$server = Start-Process -FilePath $pyCmd.Source `
    -ArgumentList "-m","http.server","8765","--bind","127.0.0.1" `
    -WorkingDirectory $Site `
    -PassThru `
    -WindowStyle Minimized

Start-Sleep -Seconds 1
try {
    Write-Host ""
    Write-Host "Cloudflare Quick Tunnel - copy the https://....trycloudflare.com URL below onto your phone."
    Write-Host "Keep this window open. Ctrl+C stops the tunnel."
    Write-Host ""
    & cloudflared tunnel --url "http://127.0.0.1:8765"
}
finally {
    if ($null -ne $server -and -not $server.HasExited) {
        Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
    }
}
