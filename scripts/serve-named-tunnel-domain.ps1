-# Named Cloudflare Tunnel -> custom domain (Windows, windows stay open).
# ASCII-only for Windows PowerShell 5.1 encoding safety.
#
# Prerequisites:
#   1. Domain exists and is on your Cloudflare account (NS or CNAME).
#   2. cloudflared installed. cert.pem already present is OK (skip tunnel login).
#
# Usage:
#   cd $env:USERPROFILE\Documents\SwiftTerm
#   powershell -ExecutionPolicy Bypass -File .\scripts\serve-named-tunnel-domain.ps1 -Hostname toolvip1.top

param(
    [Parameter(Mandatory = $true)]
    [string]$Hostname,
    [string]$TunnelName = "swiftterm-web",
    [int]$Port = 8765
)

$ErrorActionPreference = "Stop"
$Root = Join-Path $env:USERPROFILE "Documents\SwiftTerm"
$Site = Join-Path $Root "Web\cloudflare\site"
$EvidenceDir = Join-Path $Root "Docs\evidence"
$Log = Join-Path $EvidenceDir "windows-named-tunnel-log.txt"
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

if (-not (Test-Path -LiteralPath (Join-Path $Site "index.html"))) {
    throw "Missing site at $Site"
}

function Refresh-Path {
    $machine = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [System.Environment]::GetEnvironmentVariable("Path", "User")
    if ($null -eq $machine) { $machine = "" }
    if ($null -eq $user) { $user = "" }
    $env:Path = $machine + ";" + $user
}

# cloudflared writes WRN/INF to stderr; with $ErrorActionPreference=Stop + 2>&1 that becomes a terminating error on PS 5.1.
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
    $text = ($out | ForEach-Object { "$_" }) -join "`n"
    return @{ ExitCode = $code; Text = $text; Lines = @($out | ForEach-Object { "$_" }) }
}

Refresh-Path
if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
    Write-Host "Installing cloudflared (winget)..."
    winget install --id Cloudflare.cloudflared -e --accept-source-agreements --accept-package-agreements
    Refresh-Path
}

$py = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }
if (-not $py) { throw "Python required. Install: winget install Python.Python.3.12" }

$stamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
"=== named-tunnel $stamp hostname=$Hostname tunnel=$TunnelName ===" | Set-Content -LiteralPath $Log -Encoding ASCII

$configDir = Join-Path $env:USERPROFILE ".cloudflared"
if (-not (Test-Path -LiteralPath (Join-Path $configDir "cert.pem"))) {
    throw "Missing $configDir\cert.pem - run: cloudflared tunnel login"
}

# Create tunnel if missing
$list = Invoke-Cloudflared @("tunnel", "list")
$list.Text | Add-Content -LiteralPath $Log
if ($list.Text -notmatch [regex]::Escape($TunnelName)) {
    Write-Host "Creating tunnel $TunnelName ..."
    $created = Invoke-Cloudflared @("tunnel", "create", $TunnelName)
    $created.Text | Add-Content -LiteralPath $Log
    if ($created.ExitCode -ne 0 -and $created.ExitCode -ne $null) {
        # exit code may be null on some hosts; only fail on clear error text
        if ($created.Text -match '(?i)\berror\b|\bfatal\b|\bfailed\b') {
            throw "cloudflared tunnel create failed:`n$($created.Text)"
        }
    }
    "created tunnel $TunnelName" | Add-Content -LiteralPath $Log
} else {
    Write-Host "Tunnel exists: $TunnelName"
    "tunnel exists $TunnelName" | Add-Content -LiteralPath $Log
}

Write-Host "Routing DNS $Hostname -> $TunnelName ..."
$route = Invoke-Cloudflared @("tunnel", "route", "dns", $TunnelName, $Hostname)
$route.Text | Add-Content -LiteralPath $Log
# route dns is often idempotent; ignore "already exists" style messages
if ($route.Text -match '(?i)\bfatal\b' -and $route.Text -notmatch '(?i)already exists') {
    throw "cloudflared tunnel route dns failed:`n$($route.Text)"
}
"routed dns $Hostname -> $TunnelName" | Add-Content -LiteralPath $Log

# Prefer credentials JSON whose name matches tunnel list UUID for TunnelName
$tunnelId = $null
$list2 = Invoke-Cloudflared @("tunnel", "list")
foreach ($line in $list2.Lines) {
    if ($line -match $TunnelName) {
        if ($line -match '([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})') {
            $tunnelId = $Matches[1]
            break
        }
    }
}
if (-not $tunnelId) {
    $cred = Get-ChildItem -Path $configDir -Filter "*.json" -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^[0-9a-fA-F-]{36}\.json$' } |
        Select-Object -First 1
    if (-not $cred) {
        throw "No tunnel credentials JSON under $configDir - run: cloudflared tunnel create $TunnelName"
    }
    $tunnelId = [System.IO.Path]::GetFileNameWithoutExtension($cred.Name)
}
$credPath = Join-Path $configDir ($tunnelId + ".json")
if (-not (Test-Path -LiteralPath $credPath)) {
    throw "Missing credentials file $credPath"
}

$configPath = Join-Path $configDir "swiftterm-web-config.yml"
$yaml = @(
    "tunnel: $tunnelId"
    "credentials-file: $credPath"
    "ingress:"
    "  - hostname: $Hostname"
    "    service: http://127.0.0.1:$Port"
    "  - service: http_status:404"
) -join "`r`n"
[System.IO.File]::WriteAllText($configPath, $yaml + "`r`n")
"wrote $configPath tunnelId=$tunnelId" | Add-Content -LiteralPath $Log
Write-Host "Wrote $configPath"

$pyPath = $py.Source
$serverCmd = "Set-Location -LiteralPath '$Site'; `$Host.UI.RawUI.WindowTitle = 'SwiftTerm-HTTP-$Port-KEEP-OPEN'; Write-Host 'Serving http://127.0.0.1:$Port - keep this window open.'; & '$pyPath' -m http.server $Port --bind 127.0.0.1"
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit","-ExecutionPolicy","Bypass","-Command",$serverCmd | Out-Null

Write-Host "Waiting for local origin http://127.0.0.1:$Port/ ..."
$ready = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch { }
}
if (-not $ready) {
    throw "Local origin http://127.0.0.1:$Port/ is not healthy. Check the SwiftTerm-HTTP window (Python missing? site path wrong?)."
}
Write-Host "Local origin OK (HTTP 200)."
"local_origin http=200" | Add-Content -LiteralPath $Log

$tunnelCmd = "`$m=[System.Environment]::GetEnvironmentVariable('Path','Machine'); `$u=[System.Environment]::GetEnvironmentVariable('Path','User'); if (`$null -eq `$m){`$m=''}; if (`$null -eq `$u){`$u=''}; `$env:Path=`$m+';'+`$u; `$Host.UI.RawUI.WindowTitle = 'SwiftTerm-NamedTunnel-KEEP-OPEN'; Write-Host 'Named tunnel https://$Hostname - keep this window open.'; & cloudflared tunnel --config '$configPath' run '$TunnelName'"
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit","-ExecutionPolicy","Bypass","-Command",$tunnelCmd | Out-Null

Write-Host ""
Write-Host "Started HTTP + named tunnel windows (stay open)."
Write-Host "Open: https://$Hostname/"
Write-Host ""
Write-Host "IMPORTANT - two phone symptoms:"
Write-Host "  1) Login / Sign in page  => Cloudflare Access still ON. Zero Trust > Access > Applications > DELETE app for $Hostname"
Write-Host "  2) Unable to connect to origin => NamedTunnel window not connected OR local HTTP died. Keep BOTH windows open."
Write-Host ""
Write-Host "On this PC verify origin:"
Write-Host "  Invoke-WebRequest http://127.0.0.1:$Port/ -UseBasicParsing | Select StatusCode"
Write-Host "Log: $Log"
Write-Host "cloudflared outdated WRN is OK."
Read-Host "Press Enter to leave this launcher idle" | Out-Null
