# Tests for scripts\windows-tunnel-common.ps1 and for the rules every scripts\*.ps1 must keep.
# Windows PowerShell 5.1:
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\tests\windows-tunnel-common.tests.ps1
# Exit code = number of failed checks (0 = everything passed).

$ErrorActionPreference = "Stop"
$ScriptsDir = Split-Path -Parent $PSScriptRoot
. (Join-Path $ScriptsDir "windows-tunnel-common.ps1")

$script:Failures = 0

function Check([string]$Name, [bool]$Condition, [string]$Detail = "") {
    if ($Condition) {
        Write-Host "PASS $Name"
    } else {
        Write-Host "FAIL $Name $Detail"
        $script:Failures++
    }
}

# --- Rules for every Windows script: UTF-8 BOM, ASCII only, parses, no machine-specific root ---
foreach ($file in Get-ChildItem -Path $ScriptsDir -Filter "*.ps1" -Recurse) {
    $bytes = [System.IO.File]::ReadAllBytes($file.FullName)
    $hasBom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
    Check "bom $($file.Name)" $hasBom

    $nonAscii = @($bytes | Select-Object -Skip 3 | Where-Object { $_ -gt 127 }).Count
    Check "ascii-only $($file.Name)" ($nonAscii -eq 0) "non-ascii bytes=$nonAscii"

    $tokens = $null
    $errors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($file.FullName, [ref]$tokens, [ref]$errors)
    $messages = ($errors | ForEach-Object { $_.Message }) -join "; "
    Check "parse $($file.Name)" ($errors.Count -eq 0) $messages

    # [S] keeps this file from matching its own pattern (same trick as [g]rep).
    $text = [System.IO.File]::ReadAllText($file.FullName)
    Check "no Documents-based repo root in $($file.Name)" ($text -notmatch "Documents\\[S]wiftTerm")
}

# --- Get-SwiftTermRoot ---
$savedRoot = $env:SWIFTTERM_ROOT
$env:SWIFTTERM_ROOT = $null
Check "root = parent of scripts dir" ((Get-SwiftTermRoot "C:\Users\Admin\SwiftTerm\scripts") -ceq "C:\Users\Admin\SwiftTerm")
Check "root does not depend on Documents" ((Get-SwiftTermRoot "C:\work\st\scripts") -ceq "C:\work\st")
$threw = $false
try { [void](Get-SwiftTermRoot "") } catch { $threw = $true }
Check "root without script dir throws" $threw
$env:SWIFTTERM_ROOT = "E:\override"
Check "SWIFTTERM_ROOT overrides the script dir" ((Get-SwiftTermRoot "C:\Users\Admin\SwiftTerm\scripts") -ceq "E:\override")
$env:SWIFTTERM_ROOT = $savedRoot

# --- Refresh-Path ---
$env:Path = ""
Refresh-Path
Check "Refresh-Path rebuilds PATH from machine and user scope" ($env:Path -match "(?i)windows\\system32")

# --- Test-CanBindPort / Select-ListenPort ---
$holder = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, 0)
$holder.Start()
$busyPort = ([System.Net.IPEndPoint]$holder.LocalEndpoint).Port
Check "Test-CanBindPort is false for a busy port" ((Test-CanBindPort $busyPort) -eq $false)
Check "Select-ListenPort skips a busy preferred port" ((Select-ListenPort $busyPort) -ne $busyPort)
$holder.Stop()
Check "Test-CanBindPort is true once the port is released" ((Test-CanBindPort $busyPort) -eq $true)

# --- Write-SwiftTermIngressConfig ---
$config = Join-Path ([System.IO.Path]::GetTempPath()) ("ingress-" + [guid]::NewGuid().ToString("N") + ".yml")
Write-SwiftTermIngressConfig -Path $config -TunnelId "00000000-0000-0000-0000-000000000000" -CredentialsFile "C:\Users\Admin\.cloudflared\x.json" -Hostname "toolvip1.top" -Port 8787
$raw = [System.IO.File]::ReadAllBytes($config)
$expected = "tunnel: 00000000-0000-0000-0000-000000000000`r`ncredentials-file: C:\Users\Admin\.cloudflared\x.json`r`ningress:`r`n  - hostname: toolvip1.top`r`n    service: http://127.0.0.1:8787`r`n  - service: http_status:404`r`n"
Check "ingress yaml content" ([System.Text.Encoding]::UTF8.GetString($raw) -ceq $expected)
Check "ingress yaml has no BOM (cloudflared would reject it)" (-not ($raw.Length -ge 3 -and $raw[0] -eq 0xEF))
Remove-Item -LiteralPath $config

# --- Test-PublicSwiftTermHost: classification of what the public hostname returns ---
function Invoke-WebRequest {
    param($Uri, [switch]$UseBasicParsing, $TimeoutSec, $MaximumRedirection)
    if ($script:FakeError) { throw $script:FakeError }
    return $script:FakeResponse
}

function Set-FakeResponse([int]$Status, [string]$Body) {
    $script:FakeError = $null
    $script:FakeResponse = [pscustomobject]@{
        StatusCode = $Status
        Content    = $Body
        Headers    = @{ Location = "https://team.cloudflareaccess.com/" }
    }
}

Set-FakeResponse 200 "<title>SwiftTerm Web</title>"
Check "public host: SwiftTerm page passes" ((Test-PublicSwiftTermHost -Hostname "toolvip1.top") -eq $true)
Set-FakeResponse 200 "Error 1033 Tunnel error"
Check "public host: tunnel error fails" ((Test-PublicSwiftTermHost -Hostname "toolvip1.top") -eq $false)
Set-FakeResponse 200 "Hello World"
Check "public host: Worker Hello World fails" ((Test-PublicSwiftTermHost -Hostname "toolvip1.top") -eq $false)
Set-FakeResponse 200 "Sign in to continue"
Check "public host: Access login wall fails" ((Test-PublicSwiftTermHost -Hostname "toolvip1.top") -eq $false)
Set-FakeResponse 302 ""
Check "public host: redirect fails" ((Test-PublicSwiftTermHost -Hostname "toolvip1.top") -eq $false)
$script:FakeError = "connection refused"
Check "public host: network error fails" ((Test-PublicSwiftTermHost -Hostname "toolvip1.top") -eq $false)

Write-Host ""
if ($script:Failures -eq 0) { Write-Host "ALL PASSED" } else { Write-Host "$($script:Failures) FAILED" }
exit $script:Failures
