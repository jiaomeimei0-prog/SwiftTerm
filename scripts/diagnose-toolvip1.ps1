# Quick local diagnostics for toolvip1.top named tunnel on Windows.
# Run while HTTP + tunnel should already be running:
#   powershell -ExecutionPolicy Bypass -File .\scripts\diagnose-toolvip1.ps1

$ErrorActionPreference = "Continue"
$config = Join-Path $env:USERPROFILE ".cloudflared\swiftterm-web-config.yml"
if (-not (Test-Path -LiteralPath $config)) {
    $config = Join-Path $env:USERPROFILE ".cloudflared\config.yml"
}

# Prefer port from config ingress (auto-selected 8787+), not hard-coded 8765
$Port = 8787
if (Test-Path -LiteralPath $config) {
    $cfgText = Get-Content -LiteralPath $config -Raw
    if ($cfgText -match 'http://127\.0\.0\.1:(\d+)') {
        $Port = [int]$Matches[1]
    }
}

Write-Host "=== diagnose toolvip1.top $(Get-Date -Format o) ==="
Write-Host "probed_port=$Port config=$config"
Write-Host ""

Write-Host "-- local origin --"
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/" -UseBasicParsing -TimeoutSec 5
    Write-Host "http://127.0.0.1:$Port/ => $($r.StatusCode) len=$($r.RawContentLength)"
    if ($r.Content -match 'SwiftTerm') { Write-Host "body contains SwiftTerm: YES" } else { Write-Host "body contains SwiftTerm: NO" }
} catch {
    Write-Host "FAIL local origin: $($_.Exception.Message)"
    Write-Host "=> Start origin on the port in config (often 8787). Run windows-install-persistent-tunnel.ps1"
}

Write-Host ""
Write-Host "-- config --"
if (Test-Path -LiteralPath $config) {
    Get-Content -LiteralPath $config
} else {
    Write-Host "Missing config under .cloudflared"
}

Write-Host ""
Write-Host "-- cloudflared processes --"
Get-Process cloudflared -ErrorAction SilentlyContinue | Format-Table Id,ProcessName,StartTime -AutoSize
if (-not (Get-Process cloudflared -ErrorAction SilentlyContinue)) {
    Write-Host "No cloudflared process. Tunnel is down => Error 1033 publicly."
}

Write-Host ""
Write-Host "-- public https --"
try {
    $p = Invoke-WebRequest -Uri "https://toolvip1.top/" -UseBasicParsing -TimeoutSec 15
    $snip = $p.Content
    if ($snip.Length -gt 160) { $snip = $snip.Substring(0, 160) }
    Write-Host "https://toolvip1.top/ => $($p.StatusCode)"
    Write-Host "snip: $snip"
} catch {
    Write-Host "https://toolvip1.top/ FAIL: $($_.Exception.Message)"
}
