# FALCON: serve the API and the console from one process on one port.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\start.ps1 [-NoDemo]
#
# The first run installs everything (scripts\setup.ps1) and, unless -NoDemo is
# given, creates a demonstration organisation with an admin account, ten
# systems and scans of the bundled sample estates. The sign-in is printed below.
# With -NoDemo the browser opens the setup assistant instead.
param([switch]$NoDemo)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root "server\.venv\Scripts\python.exe"

if (-not (Test-Path $python) -or -not (Test-Path (Join-Path $root "console\dist\index.html"))) {
    Write-Host "First run: installing FALCON (a few minutes, once)." -ForegroundColor Cyan
    & (Join-Path $PSScriptRoot "setup.ps1")
}

$port = if ($env:FALCON_PORT) { $env:FALCON_PORT } else { "8600" }
Write-Host "FALCON is starting at http://127.0.0.1:$port" -ForegroundColor Cyan
Start-Job -ScriptBlock { param($p) Start-Sleep -Seconds 4; Start-Process "http://127.0.0.1:$p" } -ArgumentList $port | Out-Null

Push-Location (Join-Path $root "server")
try {
    if ($NoDemo) { & $python -m falcon serve }
    else { & $python -m falcon serve --demo }
}
finally { Pop-Location }
