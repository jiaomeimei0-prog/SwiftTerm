# One-shot bring-up for https://toolvip1.top -> local SwiftTerm WASM.
# Fixes the failures already seen on this PC:
#   - WinError 10013 on 8765  -> auto pick bindable port (default try 8787)
#   - Wrong tunnel (toolvip1-ssh / Hello World) -> force tunnel name swiftterm-web
#   - Error 1033 (tunnel down) -> start cloudflared and keep window open
#   - Access login -> cannot delete Access from here; prints reminder
#   - Worker DNS Hello World -> cannot edit Cloudflare DNS API without token in shell;
#       prints exact DNS check
#
# Usage (PowerShell on the Windows PC, keep windows open):
#   cd $env:USERPROFILE\Documents\SwiftTerm
#   git pull origin cursor/fix-named-tunnel-ps1-45fd
#   powershell -ExecutionPolicy Bypass -File .\scripts\windows-bringup-toolvip1.ps1

param(
    [string]$Hostname = "toolvip1.top",
    [string]$TunnelName = "swiftterm-web",
    [string]$TunnelId = "b3fae273-5e2e-428c-aaff-7bfc20e441f5",
    [int]$Port = 0
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
    throw "No bindable port. Run: netsh interface ipv4 show excludedportrange protocol=tcp"
}

function Invoke-Cloudflared {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$CfArgs)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $out = & cloudflared @CfArgs 2>&1
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prev
    }
    return @{
        ExitCode = $code
        Text = (($out | ForEach-Object { "$_" }) -join "`n")
        Lines = @($out | ForEach-Object { "$_" })
    }
}

Refresh-Path
$Root = Join-Path $env:USERPROFILE "Documents\SwiftTerm"
$Site = Join-Path $Root "Web\cloudflare\site"
$CfgDir = Join-Path $env:USERPROFILE ".cloudflared"
$Cfg = Join-Path $CfgDir "swiftterm-web-config.yml"
$Log = Join-Path $Root "Docs\evidence\windows-bringup-toolvip1-log.txt"
New-Item -ItemType Directory -Force -Path (Split-Path $Log) | Out-Null

if (-not (Test-Path (Join-Path $Site "index.html"))) {
    throw "Missing $Site\index.html - clone/pull SwiftTerm first"
}
if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
    throw "cloudflared not on PATH"
}
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }
if (-not $py) { throw "Python required" }

$cred = Join-Path $CfgDir ($TunnelId + ".json")
if (-not (Test-Path -LiteralPath $cred)) {
    throw "Missing $cred - run: cloudflared tunnel create $TunnelName"
}

$Port = Select-ListenPort $Port
Write-Host "Origin port=$Port tunnel=$TunnelName id=$TunnelId host=$Hostname"

$yaml = @(
    "tunnel: $TunnelId"
    "credentials-file: $cred"
    "ingress:"
    "  - hostname: $Hostname"
    "    service: http://127.0.0.1:$Port"
    "  - service: http_status:404"
) -join "`r`n"
[System.IO.File]::WriteAllText($Cfg, $yaml + "`r`n")
Write-Host "Wrote $Cfg"

# Start HTTP origin window
$pyPath = $py.Source
$httpCmd = "Set-Location -LiteralPath '$Site'; `$Host.UI.RawUI.WindowTitle='SwiftTerm-HTTP-$Port-KEEP-OPEN'; Write-Host 'ORIGIN http://127.0.0.1:$Port - keep open'; & '$pyPath' -m http.server $Port --bind 127.0.0.1"
Start-Process powershell.exe -ArgumentList "-NoExit","-ExecutionPolicy","Bypass","-Command",$httpCmd | Out-Null

Write-Host "Waiting for local origin..."
$ready = $false
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Milliseconds 400
    try {
        $r = Invoke-WebRequest "http://127.0.0.1:$Port/" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200 -and $r.Content -match "SwiftTerm") { $ready = $true; break }
    } catch { }
}
if (-not $ready) { throw "Local origin not SwiftTerm on :$Port" }
Write-Host "Local origin PASS (SwiftTerm on :$Port)"

# Best-effort DNS route (fails if Worker still owns hostname - user must delete Worker in DNS)
Write-Host "Attempting tunnel route dns $TunnelName $Hostname ..."
$route = Invoke-Cloudflared @("tunnel", "route", "dns", $TunnelName, $Hostname)
$route.Text | Out-File -FilePath $Log -Append -Encoding ascii
Write-Host $route.Text
if ($route.Text -match "(?i)already|success|added|cname") {
    Write-Host "DNS route command reported OK/already"
} else {
    Write-Host "DNS route may have failed. In Cloudflare DNS: DELETE Worker record for $Hostname, then Add CNAME @ -> $TunnelId.cfargotunnel.com (Proxied)."
}

# Start tunnel window (inline PATH refresh BEFORE use; do not call undefined Refresh-Path first)
$tunCmd = "`$m=[System.Environment]::GetEnvironmentVariable('Path','Machine'); `$u=[System.Environment]::GetEnvironmentVariable('Path','User'); if(`$null -eq `$m){`$m=''}; if(`$null -eq `$u){`$u=''}; `$env:Path=`$m+';'+`$u; `$Host.UI.RawUI.WindowTitle='SwiftTerm-NamedTunnel-KEEP-OPEN'; Write-Host 'TUNNEL $Hostname -> 127.0.0.1:$Port - keep open (Error 1033 if you close this)'; & cloudflared tunnel --config '$Cfg' run '$TunnelName'"
Start-Process powershell.exe -ArgumentList "-NoExit","-ExecutionPolicy","Bypass","-Command",$tunCmd | Out-Null

Write-Host "Waiting 8s for tunnel register..."
Start-Sleep -Seconds 8

Write-Host ""
Write-Host "=== LOCAL CHECK ==="
try {
    $l = Invoke-WebRequest "http://127.0.0.1:$Port/" -UseBasicParsing -TimeoutSec 5
    Write-Host "local http=$($l.StatusCode) swiftterm=$($l.Content -match 'SwiftTerm')"
} catch { Write-Host "local FAIL $_" }

Write-Host "=== PUBLIC CHECK ==="
try {
    $p = Invoke-WebRequest "https://$Hostname/" -UseBasicParsing -TimeoutSec 20
    $snip = $p.Content
    if ($snip.Length -gt 180) { $snip = $snip.Substring(0, 180) }
    Write-Host "public http=$($p.StatusCode)"
    Write-Host "public body snip: $snip"
    if ($p.Content -match "SwiftTerm") {
        Write-Host "PASS: public SwiftTerm"
    } elseif ($p.Content -match "Hello World") {
        Write-Host "FAIL: still Worker Hello World - delete Worker DNS for $Hostname"
    } elseif ($p.Content -match "Sign in") {
        Write-Host "FAIL: Access still on - delete Access app $Hostname"
    } elseif ($p.Content -match "1033|Tunnel error") {
        Write-Host "FAIL: Error 1033 - NamedTunnel window not registered"
    } else {
        Write-Host "WARN: unexpected body - paste this snip back to the agent"
    }
} catch {
    Write-Host "public FAIL: $($_.Exception.Message)"
    Write-Host "If Error 1033 in browser: wait for Registered tunnel connection in NamedTunnel window."
}

Write-Host ""
Write-Host "Leave HTTP + NamedTunnel windows OPEN."
Write-Host "Log: $Log"
Read-Host "Press Enter to leave launcher idle" | Out-Null
