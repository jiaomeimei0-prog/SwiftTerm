# One-shot on the USER Windows PC:
# 1) Start Cursor My Machines worker (agent must stay running - keep window open)
# 2) Install detached HTTP origin + named tunnel for toolvip1.top
#
# Run:
#   cd $env:USERPROFILE\Documents\SwiftTerm
#   git fetch origin
#   git checkout cursor/fix-named-tunnel-ps1-45fd
#   git pull
#   powershell -ExecutionPolicy Bypass -File .\scripts\windows-start-my-machine-and-tunnel.ps1
#
# Without a live "agent worker start" process, cloud agents still cannot drive this PC.

param(
    [string]$Hostname = "toolvip1.top",
    [string]$WorkerName = "windows-pc",
    [switch]$AsService,
    [switch]$SkipWorker
)

$ErrorActionPreference = "Stop"
$Root = Join-Path $env:USERPROFILE "Documents\SwiftTerm"
if (-not (Test-Path -LiteralPath $Root)) { throw "Repo missing: $Root - clone SwiftTerm there first" }
Set-Location -LiteralPath $Root

function Refresh-Path {
    $m = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $u = [System.Environment]::GetEnvironmentVariable("Path", "User")
    if ($null -eq $m) { $m = "" }
    if ($null -eq $u) { $u = "" }
    $env:Path = $m + ";" + $u
}
Refresh-Path

Write-Host "=== 1/2 My Machines worker ==="
if ($SkipWorker) {
    Write-Host "SkipWorker set - not starting agent worker"
} else {
    $agent = Get-Command agent -ErrorAction SilentlyContinue
    if (-not $agent) {
        Write-Host "Cursor agent CLI not on PATH."
        Write-Host "Install then re-run this script:"
        Write-Host "  irm 'https://cursor.com/install?win32=true' | iex"
        Write-Host "  agent login"
        throw "agent CLI missing"
    }
    $workerCmd = "`$Host.UI.RawUI.WindowTitle='Cursor-MyMachines-KEEP-OPEN'; Set-Location -LiteralPath '$Root'; Write-Host 'My Machines worker $WorkerName - KEEP THIS WINDOW OPEN'; Write-Host 'Cloud agent can only control this PC while this process runs.'; & agent worker --computer-use --name '$WorkerName' --worker-dir '$Root' start"
    Start-Process powershell.exe -ArgumentList "-NoExit","-ExecutionPolicy","Bypass","-Command",$workerCmd | Out-Null
    Write-Host "Started worker window: $WorkerName (must stay open)"
}

Write-Host "=== 2/2 persistent tunnel for $Hostname ==="
$install = Join-Path $Root "scripts\windows-install-persistent-tunnel.ps1"
if (-not (Test-Path -LiteralPath $install)) { throw "Missing $install - git pull this branch" }
$args = @("-ExecutionPolicy","Bypass","-File",$install,"-Hostname",$Hostname)
if ($AsService) { $args += "-AsService" }
& powershell.exe @args
if ($LASTEXITCODE -ne 0) { throw "persistent tunnel install failed exit=$LASTEXITCODE" }

Write-Host ""
Write-Host "DONE local steps."
Write-Host "- Keep My Machines window open until agent confirms workers is not empty."
Write-Host "- Tunnel is detached; diagnose: powershell -File .\scripts\diagnose-toolvip1.ps1"
Write-Host "- Public check: https://$Hostname/"
