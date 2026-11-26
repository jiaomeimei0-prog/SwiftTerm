# Named Cloudflare Tunnel → custom domain (Windows, windows stay open).
# Use when Pages is not ready, or you want the local site on your hostname.
#
# Prerequisites:
#   1. Domain exists and is on your Cloudflare account (NS or CNAME).
#   2. cloudflared installed; run once: cloudflared tunnel login
#
# Usage:
#   cd $env:USERPROFILE\Documents\SwiftTerm
#   powershell -ExecutionPolicy Bypass -File .\scripts\serve-named-tunnel-domain.ps1 -Hostname toolvip1.top
#   # or after you register it:
#   powershell -ExecutionPolicy Bypass -File .\scripts\serve-named-tunnel-domain.ps1 -Hostname tooltop1.vip

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
Refresh-Path
if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
    winget install --id Cloudflare.cloudflared -e --accept-source-agreements --accept-package-agreements
    Refresh-Path
}

$py = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }
if (-not $py) { throw "Python required" }

$stamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
"=== named-tunnel $stamp hostname=$Hostname tunnel=$TunnelName ===" | Set-Content $Log

# Create tunnel if missing (idempotent-ish)
$existing = & cloudflared tunnel list 2>$null | Select-String -SimpleMatch $TunnelName
if (-not $existing) {
    & cloudflared tunnel create $TunnelName
    "created tunnel $TunnelName" | Add-Content $Log
} else {
    "tunnel exists $TunnelName" | Add-Content $Log
}

& cloudflared tunnel route dns $TunnelName $Hostname
"routed dns $Hostname -> $TunnelName" | Add-Content $Log

$configDir = Join-Path $env:USERPROFILE ".cloudflared"
$cred = Get-ChildItem -Path $configDir -Filter "*.json" | Where-Object { $_.Name -ne "cert.pem" } | Select-Object -First 1
if (-not $cred) { throw "No tunnel credentials under $configDir — run: cloudflared tunnel login" }

$tunnelId = [System.IO.Path]::GetFileNameWithoutExtension($cred.Name)
$configPath = Join-Path $configDir "swiftterm-web-config.yml"
@"
tunnel: $tunnelId
credentials-file: $($cred.FullName)
ingress:
  - hostname: $Hostname
    service: http://127.0.0.1:$Port
  - service: http_status:404
"@ | Set-Content -LiteralPath $configPath -Encoding UTF8
"wrote $configPath" | Add-Content $Log

$serverCmd = @"
`$Host.UI.RawUI.WindowTitle = 'SwiftTerm-HTTP-$Port-KEEP-OPEN'
Set-Location -LiteralPath '$Site'
Write-Host 'Serving on http://127.0.0.1:$Port — keep open.'
& '$($py.Source)' -m http.server $Port --bind 127.0.0.1
"@
Start-Process powershell.exe -ArgumentList @("-NoExit","-ExecutionPolicy","Bypass","-Command",$serverCmd) | Out-Null

$tunnelCmd = @"
`$Host.UI.RawUI.WindowTitle = 'SwiftTerm-NamedTunnel-KEEP-OPEN'
`$m = [System.Environment]::GetEnvironmentVariable('Path','Machine')
`$u = [System.Environment]::GetEnvironmentVariable('Path','User')
`$env:Path = (`$m + ';' + `$u)
Write-Host 'Named tunnel for https://$Hostname — keep this window open.'
& cloudflared tunnel --config '$configPath' run $TunnelName
"@
Start-Process powershell.exe -ArgumentList @("-NoExit","-ExecutionPolicy","Bypass","-Command",$tunnelCmd) | Out-Null

Write-Host "Started HTTP + named tunnel windows (stay open)."
Write-Host "Open: https://$Hostname/"
Write-Host "If Access login appears, disable Cloudflare Access for $Hostname in Zero Trust."
Write-Host "Log: $Log"
Read-Host "Press Enter to leave launcher idle" | Out-Null
