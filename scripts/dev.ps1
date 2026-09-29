# FALCON development: API with auto-reload (port 8600) and the Vite console
# with hot module replacement (port 5180, proxies /api to the server).
# Usage: powershell -ExecutionPolicy Bypass -File scripts\dev.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root "server\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Server environment missing. Run scripts\setup.ps1 first." }

Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\server'; & '$python' -m falcon serve --reload"
Push-Location (Join-Path $root "console")
try { npm run dev }
finally { Pop-Location }
