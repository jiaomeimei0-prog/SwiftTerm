# Shared helpers for Windows toolvip1.top tunnel scripts.
# Dot-source from caller:
#   . (Join-Path $PSScriptRoot 'windows-tunnel-common.ps1')

function Get-SwiftTermRoot([string]$ScriptDir) {
    # Repo root = parent of scripts\ ; SWIFTTERM_ROOT overrides it for unusual layouts.
    if ($env:SWIFTTERM_ROOT) { return $env:SWIFTTERM_ROOT }
    if (-not $ScriptDir) { throw "Cannot locate the repo: run the script from a file or set SWIFTTERM_ROOT." }
    return (Split-Path -Parent $ScriptDir)
}

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

function Write-SwiftTermIngressConfig {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$TunnelId,
        [Parameter(Mandatory = $true)][string]$CredentialsFile,
        [Parameter(Mandatory = $true)][string]$Hostname,
        [Parameter(Mandatory = $true)][int]$Port
    )
    $yaml = @(
        "tunnel: $TunnelId"
        "credentials-file: $CredentialsFile"
        "ingress:"
        "  - hostname: $Hostname"
        "    service: http://127.0.0.1:$Port"
        "  - service: http_status:404"
    ) -join "`r`n"
    [System.IO.File]::WriteAllText($Path, $yaml + "`r`n")
}

function Test-PublicSwiftTermHost {
    param(
        [Parameter(Mandatory = $true)][string]$Hostname,
        [int]$TimeoutSec = 20
    )
    # MaximumRedirection 0: Access 302 must not look like PASS 200
    try {
        $p = Invoke-WebRequest "https://$Hostname/" -UseBasicParsing -TimeoutSec $TimeoutSec -MaximumRedirection 0
        $snip = $p.Content
        if ($snip.Length -gt 160) { $snip = $snip.Substring(0, 160) }
        Write-Host "https://$Hostname/ => $($p.StatusCode) snip=$snip"
        if ($p.StatusCode -ge 300 -and $p.StatusCode -lt 400) {
            Write-Host "FAIL redirect Location=$($p.Headers['Location']) (Access/gate)"
            return $false
        }
        if ($p.Content -match "SwiftTerm") {
            Write-Host "PASS public SwiftTerm"
            return $true
        }
        if ($p.Content -match "1033|Tunnel error") {
            Write-Host "FAIL Error 1033 / tunnel down"
            return $false
        }
        if ($p.Content -match "Hello World") {
            Write-Host "FAIL Worker Hello World DNS"
            return $false
        }
        if ($p.Content -match "(?i)cloudflareaccess\.com|Sign in|Access") {
            Write-Host "FAIL Access login wall"
            return $false
        }
        Write-Host "WARN unexpected body"
        return $false
    } catch {
        $resp = $_.Exception.Response
        if ($resp -and [int]$resp.StatusCode -ge 300 -and [int]$resp.StatusCode -lt 400) {
            $loc = $null
            try { $loc = $resp.Headers["Location"] } catch { }
            Write-Host "FAIL HTTP $([int]$resp.StatusCode) redirect Location=$loc (Access gate)"
            return $false
        }
        Write-Host "public FAIL: $($_.Exception.Message)"
        return $false
    }
}
