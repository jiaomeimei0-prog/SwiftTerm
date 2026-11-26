# Quick local diagnostics for toolvip1.top named tunnel on Windows.
# Run while HTTP + NamedTunnel windows should already be open:
#   powershell -ExecutionPolicy Bypass -File .\scripts\diagnose-toolvip1.ps1

$ErrorActionPreference = "Continue"
$Port = 8765
$config = Join-Path $env:USERPROFILE ".cloudflared\swiftterm-web-config.yml"

Write-Host "=== diagnose toolvip1.top $(Get-Date -Format o) ==="
Write-Host ""

Write-Host "-- local origin --"
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/" -UseBasicParsing -TimeoutSec 5
    Write-Host "http://127.0.0.1:$Port/ => $($r.StatusCode) len=$($r.RawContentLength)"
    if ($r.Content -match 'SwiftTerm') { Write-Host "body contains SwiftTerm: YES" } else { Write-Host "body contains SwiftTerm: NO" }
} catch {
    Write-Host "FAIL local origin: $($_.Exception.Message)"
    Write-Host "=> Start/fix the SwiftTerm-HTTP-$Port-KEEP-OPEN window."
}

Write-Host ""
Write-Host "-- config --"
if (Test-Path -LiteralPath $config) {
    Get-Content -LiteralPath $config
} else {
    Write-Host "Missing $config"
}

Write-Host ""
Write-Host "-- cloudflared processes --"
Get-Process cloudflared -ErrorAction SilentlyContinue | Format-Table Id,ProcessName,StartTime -AutoSize
if (-not (Get-Process cloudflared -ErrorAction SilentlyContinue)) {
    Write-Host "No cloudflared process. NamedTunnel window is not running."
}

Write-Host ""
Write-Host "-- public https (may show Access or origin error) --"
try {
    $p = Invoke-WebRequest -Uri "https://toolvip1.top/" -UseBasicParsing -TimeoutSec 15 -MaximumRedirection 0
    Write-Host "https://toolvip1.top/ => $($p.StatusCode)"
} catch {
    $resp = $_.Exception.Response
    if ($resp) {
        Write-Host "https://toolvip1.top/ => $([int]$resp.StatusCode) $($resp.StatusCode)"
        Write-Host "If 302 to cloudflareaccess.com => DELETE Access application in Zero Trust."
    } else {
        Write-Host "https://toolvip1.top/ FAIL: $($_.Exception.Message)"
    }
}

Write-Host ""
Write-Host "Same WiFi = Access login  => turn OFF Access."
Write-Host "Other WiFi = Unable to connect to origin => fix NamedTunnel + local HTTP windows."
