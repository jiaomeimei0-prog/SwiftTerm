# One-shot bring-up for https://toolvip1.top -> local SwiftTerm WASM.
# Fixes seen on PC: WinError 10013, wrong tunnel Hello World, Error 1033, Access/Worker DNS.
#
# Usage (PowerShell on Windows PC, keep windows open):
#   cd <path-to-your-SwiftTerm-clone>
#   git pull origin cursor/fix-named-tunnel-ps1-45fd
#   powershell -ExecutionPolicy Bypass -File .\scripts\windows-bringup-toolvip1.ps1

param(
    [string]$Hostname = "toolvip1.top",
    [string]$TunnelName = "swiftterm-web",
    [string]$TunnelId = "b3fae273-5e2e-428c-aaff-7bfc20e441f5",
    [int]$Port = 0
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "windows-tunnel-common.ps1")
Refresh-Path

$Root = Get-SwiftTermRoot $PSScriptRoot
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

Write-SwiftTermIngressConfig -Path $Cfg -TunnelId $TunnelId -CredentialsFile $cred -Hostname $Hostname -Port $Port
Write-Host "Wrote $Cfg"

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

Write-Host "Attempting tunnel route dns $TunnelName $Hostname ..."
$route = Invoke-Cloudflared @("tunnel", "route", "dns", $TunnelName, $Hostname)
$route.Text | Out-File -FilePath $Log -Append -Encoding ascii
Write-Host $route.Text
if ($route.Text -match "(?i)already|success|added|cname") {
    Write-Host "DNS route command reported OK/already"
} else {
    Write-Host "DNS route may have failed. In Cloudflare DNS: DELETE Worker record for $Hostname, then Add CNAME @ -> $TunnelId.cfargotunnel.com (Proxied)."
}

# Inline PATH in child (do not call undefined Refresh-Path first)
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
[void](Test-PublicSwiftTermHost -Hostname $Hostname -TimeoutSec 20)

Write-Host ""
Write-Host "Leave HTTP + NamedTunnel windows OPEN."
Write-Host "Log: $Log"
Read-Host "Press Enter to leave launcher idle" | Out-Null
