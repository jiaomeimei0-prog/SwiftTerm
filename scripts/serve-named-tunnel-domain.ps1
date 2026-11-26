# Named Cloudflare Tunnel -> custom domain (Windows, windows stay open).
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
$listOut = & cloudflared tunnel list 2>&1 | Out-String
if ($listOut -notmatch [regex]::Escape($TunnelName)) {
    Write-Host "Creating tunnel $TunnelName ..."
    & cloudflared tunnel create $TunnelName
    "created tunnel $TunnelName" | Add-Content -LiteralPath $Log
} else {
    Write-Host "Tunnel exists: $TunnelName"
    "tunnel exists $TunnelName" | Add-Content -LiteralPath $Log
}

Write-Host "Routing DNS $Hostname -> $TunnelName ..."
& cloudflared tunnel route dns $TunnelName $Hostname
"routed dns $Hostname -> $TunnelName" | Add-Content -LiteralPath $Log

# Prefer credentials JSON whose name matches tunnel list UUID for TunnelName
$tunnelId = $null
$listLines = & cloudflared tunnel list 2>&1
foreach ($line in $listLines) {
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
# Build YAML without here-string edge cases on PS 5.1
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

$tunnelCmd = "Refresh-Path; function Refresh-Path { `$m=[System.Environment]::GetEnvironmentVariable('Path','Machine'); `$u=[System.Environment]::GetEnvironmentVariable('Path','User'); if (`$null -eq `$m){`$m=''}; if (`$null -eq `$u){`$u=''}; `$env:Path=`$m+';'+`$u }; Refresh-Path; `$Host.UI.RawUI.WindowTitle = 'SwiftTerm-NamedTunnel-KEEP-OPEN'; Write-Host 'Named tunnel https://$Hostname - keep this window open.'; & cloudflared tunnel --config '$configPath' run '$TunnelName'"
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit","-ExecutionPolicy","Bypass","-Command",$tunnelCmd | Out-Null

Write-Host ""
Write-Host "Started HTTP + named tunnel windows (stay open)."
Write-Host "Open: https://$Hostname/"
Write-Host "If Access login appears, disable Cloudflare Access for $Hostname in Zero Trust."
Write-Host "If phone shows Unable to connect to origin, wait 10s then refresh; keep both windows open."
Write-Host "Log: $Log"
Write-Host ""
Write-Host "cert.pem already exists - that is OK. Do NOT delete it unless you need to re-login."
Read-Host "Press Enter to leave this launcher idle" | Out-Null
