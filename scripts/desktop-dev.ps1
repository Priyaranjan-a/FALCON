# FALCON desktop in development: the native shell runs the engine straight from
# the server's virtual environment (no PyInstaller build), with the built console.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\desktop-dev.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $root "server\.venv\Scripts\python.exe"))) { throw "Server environment missing. Run scripts\setup.ps1 first." }

Push-Location (Join-Path $root "console")
try { npm run build } finally { Pop-Location }

Push-Location (Join-Path $root "desktop")
try {
    npm install --no-audit --no-fund
    npx tauri dev --config src-tauri\tauri.dev.conf.json
}
finally { Pop-Location }
