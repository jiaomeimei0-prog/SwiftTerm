# Install SwiftTerm origin + Cloudflare tunnel as persistent Windows processes
# so Error 1033 does not return when you close a PowerShell window.
#
# Run ONCE in elevated PowerShell (Run as Administrator) if service install is desired:
#   powershell -ExecutionPolicy Bypass -File .\scripts\windows-install-persistent-tunnel.ps1
#
# Non-admin fallback: starts detached processes that survive the launcher window
# (still die on reboot unless Scheduled Task is created).

param(
    [string]$Hostname = "toolvip1.top",
    [string]$TunnelName = "swiftterm-web",
    [string]$TunnelId = "b3fae273-5e2e-428c-aaff-7bfc20e441f5",
    [int]$Port = 8787,
    [switch]$AsService
)

$ErrorActionPreference = "Stop"

function Refresh-Path {
    $m = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $u = [System.Environment]::GetEnvironmentVariable("Path", "User")
    if ($null -eq $m) { $m = "" }
    if ($null -eq $u) { $u = "" }
    $env:Path = $m + ";" + $u
}

function Test-CanBindPort([int]$TestPort) {
    $listener = $null
    try {
        $listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, $TestPort)
        $listener.Start()
        $listener.Stop()
        return $true
    } catch {
        return $false
    } finally {
        if ($listener) { try { $listener.Stop() } catch { } }
    }
}

Refresh-Path
$Root = Join-Path $env:USERPROFILE "Documents\SwiftTerm"
$Site = Join-Path $Root "Web\cloudflare\site"
$CfgDir = Join-Path $env:USERPROFILE ".cloudflared"
$Cred = Join-Path $CfgDir ($TunnelId + ".json")
$Cfg = Join-Path $CfgDir "config.yml"
$LogDir = Join-Path $Root "Docs\evidence"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

if (-not (Test-Path (Join-Path $Site "index.html"))) { throw "Missing site $Site" }
if (-not (Test-Path $Cred)) { throw "Missing $Cred" }
if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) { throw "cloudflared missing" }
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }
if (-not $py) { throw "Python missing" }

if (-not (Test-CanBindPort $Port)) {
    foreach ($p in 8888, 18080, 19000, 28080) {
        if (Test-CanBindPort $p) { $Port = $p; break }
    }
}
Write-Host "Using origin port $Port"

# Standard cloudflared config.yml (used by `cloudflared service`)
$yaml = @(
    "tunnel: $TunnelId"
    "credentials-file: $Cred"
    "ingress:"
    "  - hostname: $Hostname"
    "    service: http://127.0.0.1:$Port"
    "  - service: http_status:404"
) -join "`r`n"
[System.IO.File]::WriteAllText($Cfg, $yaml + "`r`n")
Copy-Item -Force $Cfg (Join-Path $CfgDir "swiftterm-web-config.yml")
Write-Host "Wrote $Cfg"

# Stop leftover python servers on this port if we can identify them
Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }

# Start origin detached (hidden window, survives parent)
$originLog = Join-Path $LogDir "origin-8787.log"
$originArgs = "-NoProfile -WindowStyle Hidden -Command `"Set-Location -LiteralPath '$Site'; & '$($py.Source)' -m http.server $Port --bind 127.0.0.1 *>> '$originLog'`""
Start-Process -FilePath "powershell.exe" -ArgumentList $originArgs -WindowStyle Hidden | Out-Null

Start-Sleep -Seconds 2
$ok = $false
try {
    $r = Invoke-WebRequest "http://127.0.0.1:$Port/" -UseBasicParsing -TimeoutSec 5
    if ($r.StatusCode -eq 200 -and $r.Content -match "SwiftTerm") { $ok = $true }
} catch { }
if (-not $ok) { throw "Origin did not become healthy on :$Port - see $originLog" }
Write-Host "Origin PASS SwiftTerm on :$Port"

if ($AsService) {
    # Requires Administrator
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & cloudflared service uninstall 2>&1 | Out-Null
    & cloudflared service install 2>&1 | Write-Host
    Start-Service cloudflared -ErrorAction SilentlyContinue
    Get-Service cloudflared -ErrorAction SilentlyContinue | Format-List *
    $ErrorActionPreference = $prev
    Write-Host "Attempted cloudflared Windows service install/start."
} else {
    # Detached tunnel process (survives this script; dies on logout/reboot)
    $tunLog = Join-Path $LogDir "tunnel-swiftterm-web.log"
    $tunArgs = "-NoProfile -WindowStyle Hidden -Command `"& cloudflared tunnel --config '$Cfg' run '$TunnelName' *>> '$tunLog'`""
    Start-Process -FilePath "powershell.exe" -ArgumentList $tunArgs -WindowStyle Hidden | Out-Null
    Write-Host "Started detached cloudflared (log $tunLog)"
}

Start-Sleep -Seconds 8
Write-Host "=== PUBLIC CHECK ==="
try {
    $p = Invoke-WebRequest "https://$Hostname/" -UseBasicParsing -TimeoutSec 25
    $snip = $p.Content
    if ($snip.Length -gt 160) { $snip = $snip.Substring(0, 160) }
    Write-Host "http=$($p.StatusCode) snip=$snip"
    if ($p.Content -match "SwiftTerm") { Write-Host "PASS public SwiftTerm" }
    elseif ($p.Content -match "1033|Tunnel error") { Write-Host "FAIL still 1033 - wait or check tunnel log" }
    elseif ($p.Content -match "Hello World") { Write-Host "FAIL Worker DNS still bound" }
    else { Write-Host "WARN unexpected body" }
} catch {
    Write-Host "public error: $($_.Exception.Message)"
}

Write-Host "Done. Processes should keep running after this window closes (until reboot unless -AsService)."
