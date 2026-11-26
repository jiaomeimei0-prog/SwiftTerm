# Install SwiftTerm origin + Cloudflare tunnel as detached Windows processes
# so Error 1033 does not return when you close the launcher window.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\windows-install-persistent-tunnel.ps1
#
# Notes on -AsService:
#   cloudflared Windows service runs as Local System and reads
#   C:\Windows\System32\config\systemprofile\.cloudflared\config.yml
#   This script copies config+credentials there when -AsService is set (Admin required).
#   Origin (python http.server) is still a user-session process unless you also
#   create a Scheduled Task; reboot will drop origin unless you re-run or add a task.
#   Do NOT claim full reboot survival for origin with -AsService alone.

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

function Select-ListenPort([int]$Preferred) {
    $candidates = @()
    if ($Preferred -gt 0) { $candidates += $Preferred }
    $candidates += 8787, 8888, 18080, 19000, 28080, 3000, 8080
    $seen = @{}
    foreach ($p in $candidates) {
        if ($seen.ContainsKey($p)) { continue }
        $seen[$p] = $true
        if (Test-CanBindPort $p) { return $p }
        Write-Host "Port $p blocked - next..."
    }
    throw "No bindable local port. Check: netsh interface ipv4 show excludedportrange protocol=tcp"
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

$Port = Select-ListenPort $Port
Write-Host "Using origin port $Port"

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

Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }

$originLog = Join-Path $LogDir ("origin-" + $Port + ".log")
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
    $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $isAdmin) {
        throw "-AsService requires Administrator PowerShell (Local System profile copy)."
    }
    $sysHome = "C:\Windows\System32\config\systemprofile\.cloudflared"
    New-Item -ItemType Directory -Force -Path $sysHome | Out-Null
    # Service reads credentials-file path INSIDE its config; rewrite path for System profile
    $sysCred = Join-Path $sysHome ($TunnelId + ".json")
    Copy-Item -Force $Cred $sysCred
    $sysYaml = @(
        "tunnel: $TunnelId"
        "credentials-file: $sysCred"
        "ingress:"
        "  - hostname: $Hostname"
        "    service: http://127.0.0.1:$Port"
        "  - service: http_status:404"
    ) -join "`r`n"
    [System.IO.File]::WriteAllText((Join-Path $sysHome "config.yml"), $sysYaml + "`r`n")
    Write-Host "Copied tunnel config+cred to $sysHome for Local System service"

    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $un = & cloudflared service uninstall 2>&1 | Out-String
    $ins = & cloudflared service install 2>&1 | Out-String
    Write-Host $un
    Write-Host $ins
    if ($ins -match '(?i)error|fail|access is denied') {
        $ErrorActionPreference = $prev
        throw "cloudflared service install failed:`n$ins"
    }
    Start-Service cloudflared -ErrorAction Stop
    Get-Service cloudflared | Format-List Name,Status,StartType
    $ErrorActionPreference = $prev
    Write-Host "cloudflared service started. Origin is still a USER process - re-run this script after reboot to restore http.server (or add a Scheduled Task)."
} else {
    $tunLog = Join-Path $LogDir "tunnel-swiftterm-web.log"
    $tunArgs = "-NoProfile -WindowStyle Hidden -Command `"& cloudflared tunnel --config '$Cfg' run '$TunnelName' *>> '$tunLog'`""
    Start-Process -FilePath "powershell.exe" -ArgumentList $tunArgs -WindowStyle Hidden | Out-Null
    Write-Host "Started detached cloudflared (log $tunLog). Survives this window; dies on logout/reboot."
}

Start-Sleep -Seconds 8
Write-Host "=== PUBLIC CHECK (no redirect follow) ==="
try {
    $p = Invoke-WebRequest "https://$Hostname/" -UseBasicParsing -TimeoutSec 25 -MaximumRedirection 0
    $snip = $p.Content
    if ($snip.Length -gt 160) { $snip = $snip.Substring(0, 160) }
    Write-Host "http=$($p.StatusCode) snip=$snip"
    if ($p.StatusCode -ge 300 -and $p.StatusCode -lt 400) {
        Write-Host "FAIL redirect Location=$($p.Headers['Location']) (Access/gate)"
    }
    elseif ($p.Content -match "SwiftTerm") { Write-Host "PASS public SwiftTerm" }
    elseif ($p.Content -match "1033|Tunnel error") { Write-Host "FAIL still 1033 - wait or check tunnel log" }
    elseif ($p.Content -match "Hello World") { Write-Host "FAIL Worker DNS still bound" }
    elseif ($p.Content -match "(?i)cloudflareaccess\.com|Sign in|Access") { Write-Host "FAIL Access login wall" }
    else { Write-Host "WARN unexpected body" }
} catch {
    $resp = $_.Exception.Response
    if ($resp -and [int]$resp.StatusCode -ge 300 -and [int]$resp.StatusCode -lt 400) {
        $loc = $null
        try { $loc = $resp.Headers["Location"] } catch { }
        Write-Host "public FAIL: HTTP $([int]$resp.StatusCode) redirect Location=$loc (Access gate)"
    } else {
        Write-Host "public error: $($_.Exception.Message)"
    }
}

Write-Host "Done."
