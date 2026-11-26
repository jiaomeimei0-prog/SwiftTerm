# Persistent Windows E2E launcher for SwiftTerm Cloudflare WASM demo.
# Opens SEPARATE windows for http.server and cloudflared that stay open.
# Does NOT kill those windows when this launcher exits.
#
# Usage:
#   cd $env:USERPROFILE\Documents\SwiftTerm
#   powershell -ExecutionPolicy Bypass -File .\scripts\windows-persistent-e2e.ps1
#
# Results land in:
#   $env:USERPROFILE\Documents\SwiftTerm\Docs\evidence\windows-persistent-e2e-log.txt

$ErrorActionPreference = "Stop"

$Root = Join-Path $env:USERPROFILE "Documents\SwiftTerm"
$Site = Join-Path $Root "Web\cloudflare\site"
$Index = Join-Path $Site "index.html"
$EvidenceDir = Join-Path $Root "Docs\evidence"
$Log = Join-Path $EvidenceDir "windows-persistent-e2e-log.txt"
$UrlFile = Join-Path $EvidenceDir "windows-trycloudflare-url.txt"

if (-not (Test-Path -LiteralPath $Index)) {
    throw "Missing $Index - clone https://github.com/jiaomeimei0-prog/SwiftTerm.git into Documents\SwiftTerm first."
}
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

function Refresh-Path {
    $machine = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [System.Environment]::GetEnvironmentVariable("Path", "User")
    if ($null -eq $machine) { $machine = "" }
    if ($null -eq $user) { $user = "" }
    $env:Path = $machine + ";" + $user
}

function Ensure-Cloudflared {
    Refresh-Path
    if (Get-Command cloudflared -ErrorAction SilentlyContinue) { return }
    Write-Host "Installing cloudflared (winget)..."
    winget install --id Cloudflare.cloudflared -e --accept-source-agreements --accept-package-agreements
    Refresh-Path
    if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
        throw "cloudflared not on PATH. Close PowerShell, reopen, re-run."
    }
}

function Ensure-Python {
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }
    if (-not $py) { throw "Python not found. Install: winget install Python.Python.3.12" }
    return $py.Source
}

Ensure-Cloudflared
$Python = Ensure-Python

$stamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
@(
    "=== windows-persistent-e2e $stamp ===",
    "root=$Root",
    "site=$Site",
    "python=$Python",
    "NOTE: http.server and cloudflared run in separate windows; leave them open."
) | Set-Content -LiteralPath $Log -Encoding UTF8

# Free 8765 only if needed (optional - comment out if you want to keep an existing server)
$listeners = Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue
if ($listeners) {
    "port 8765 busy - leaving existing listener; not killing (persistent policy)." | Add-Content $Log
} else {
    $serverCmd = @"
`$Host.UI.RawUI.WindowTitle = 'SwiftTerm-HTTP-8765-KEEP-OPEN'
Set-Location -LiteralPath '$Site'
Write-Host 'Serving $Site on http://127.0.0.1:8765 - keep this window open.'
& '$Python' -m http.server 8765 --bind 127.0.0.1
"@
    Start-Process -FilePath "powershell.exe" -ArgumentList @(
        "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $serverCmd
    ) | Out-Null
    "started http.server window" | Add-Content $Log
    Start-Sleep -Seconds 2
}

$tunnelCmd = @"
`$Host.UI.RawUI.WindowTitle = 'SwiftTerm-Cloudflared-KEEP-OPEN'
`$m = [System.Environment]::GetEnvironmentVariable('Path','Machine')
`$u = [System.Environment]::GetEnvironmentVariable('Path','User')
if (`$null -eq `$m) { `$m = '' }
if (`$null -eq `$u) { `$u = '' }
`$env:Path = `$m + ';' + `$u
Write-Host 'Cloudflare Quick Tunnel - copy https://....trycloudflare.com URL below.'
Write-Host 'Keep this window open. Do not close until you finish acceptance.'
& cloudflared tunnel --url http://127.0.0.1:8765
"@
Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $tunnelCmd
) | Out-Null
"started cloudflared window" | Add-Content $Log

Start-Sleep -Seconds 3

# Local probe from launcher (does not close child windows)
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8765/" -UseBasicParsing -TimeoutSec 10
    "local_index status=$($r.StatusCode) len=$($r.RawContentLength)" | Add-Content $Log
} catch {
    "local_index FAIL: $($_.Exception.Message)" | Add-Content $Log
}

Write-Host ""
Write-Host "Launcher finished. Child windows stay open (HTTP + cloudflared)."
Write-Host "Log: $Log"
Write-Host "When cloudflared prints the trycloudflare URL, open it in your browser."
Write-Host "Paste that URL into: $UrlFile"
Write-Host ""
Write-Host "This launcher window can stay open too (press Enter to leave it idle)..."
Read-Host | Out-Null
"launcher_idle_ack" | Add-Content $Log
