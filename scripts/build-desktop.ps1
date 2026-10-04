# FALCON desktop: build the Windows installer.
#   1. console bundle   (console/dist)
#   2. engine           (server/dist/falcon-engine, PyInstaller one-folder build)
#   3. native app       (Tauri) and its NSIS installer
# Needs: the server environment from scripts\setup.ps1, Node.js 20+, Rust (MSVC toolchain)
# and Microsoft Edge WebView2 (preinstalled on Windows 10/11).
# Usage: powershell -ExecutionPolicy Bypass -File scripts\build-desktop.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root "server\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Server environment missing. Run scripts\setup.ps1 first." }
if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) { throw "Rust is required: install it from https://rustup.rs" }

Write-Host "FALCON desktop build" -ForegroundColor Cyan

Push-Location (Join-Path $root "console")
try {
    npm install --no-audit --no-fund
    npm run build
    Write-Host "  console built" -ForegroundColor Green
}
finally { Pop-Location }

Push-Location (Join-Path $root "server")
try {
    & $python -m pip install -e ".[desktop]" --quiet
    & $python -m PyInstaller ..\desktop\engine\falcon-engine.spec --distpath dist --workpath build\pyinstaller --noconfirm --log-level WARN
    if ($LASTEXITCODE -ne 0) { throw "The engine build failed." }
    Write-Host "  engine built (server\dist\falcon-engine)" -ForegroundColor Green
}
finally { Pop-Location }

Push-Location (Join-Path $root "desktop")
try {
    npm install --no-audit --no-fund
    npx tauri build --bundles nsis,msi
    if ($LASTEXITCODE -ne 0) { throw "The desktop build failed." }
}
finally { Pop-Location }

$installer = Get-ChildItem (Join-Path $root "desktop\src-tauri\target\release\bundle\nsis\*.exe") | Sort-Object LastWriteTime | Select-Object -Last 1
Write-Host "Done. Installer: $($installer.FullName)" -ForegroundColor Cyan
