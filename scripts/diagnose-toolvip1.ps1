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
Write-Host "-- public https (no follow redirects; Access 302 must not look like PASS) --"
try {
    # MaximumRedirection 0: Cloudflare Access login is a 302; following it yields fake 200 login HTML
    $p = Invoke-WebRequest -Uri "https://toolvip1.top/" -UseBasicParsing -TimeoutSec 15 -MaximumRedirection 0
    $snip = $p.Content
    if ($snip.Length -gt 160) { $snip = $snip.Substring(0, 160) }
    Write-Host "https://toolvip1.top/ => $($p.StatusCode)"
    Write-Host "snip: $snip"
    if ($p.StatusCode -ge 300 -and $p.StatusCode -lt 400) {
        $loc = $p.Headers["Location"]
        Write-Host "FAIL redirect Location=$loc (Cloudflare Access or other gate)"
    } elseif ($p.Content -match '(?i)cloudflareaccess\.com|Access|Sign in|login') {
        Write-Host "FAIL body looks like Access/login wall"
    } elseif ($p.Content -match 'SwiftTerm') {
        Write-Host "PASS public SwiftTerm"
    } elseif ($p.Content -match '1033|Tunnel error') {
        Write-Host "FAIL Error 1033 / tunnel down"
    } elseif ($p.Content -match 'Hello World') {
        Write-Host "FAIL Worker Hello World DNS"
    } else {
        Write-Host "WARN unexpected body"
    }
} catch {
    $resp = $_.Exception.Response
    if ($resp -and [int]$resp.StatusCode -ge 300 -and [int]$resp.StatusCode -lt 400) {
        $loc = $null
        try { $loc = $resp.Headers["Location"] } catch { }
        Write-Host "https://toolvip1.top/ => $([int]$resp.StatusCode) redirect Location=$loc"
        Write-Host "FAIL Cloudflare Access (or redirect gate) - delete Access app on apex"
    } else {
        Write-Host "https://toolvip1.top/ FAIL: $($_.Exception.Message)"
    }
}
