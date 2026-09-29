# FALCON: install the server and console, then build the console.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
# Needs Python 3.12+ and Node.js 20.19+ (or 22.12+). Nothing is installed outside this folder.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "FALCON setup" -ForegroundColor Cyan

# --- prerequisites -----------------------------------------------------------
function Find-Python {
    foreach ($candidate in @(@("py", "-3"), @("python"), @("python3"))) {
        if (-not (Get-Command $candidate[0] -ErrorAction SilentlyContinue)) { continue }
        $extra = @($candidate | Select-Object -Skip 1)
        # Probing must never stop the script: the Store's "python" alias writes to stderr and exits.
        $previous = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try { $ok = & $candidate[0] @extra -c "import sys; print(1 if sys.version_info >= (3, 12) else 0)" 2>$null }
        catch { $ok = $null }
        finally { $ErrorActionPreference = $previous }
        if ("$ok".Trim() -eq "1") { return , $candidate }
    }
    return $null
}

$pythonCmd = Find-Python
if (-not $pythonCmd) { throw "Python 3.12 or newer is required: https://www.python.org/downloads/" }
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw "Node.js 20.19+ or 22.12+ is required: https://nodejs.org/" }
$nodeMajor = [int]((node --version).TrimStart("v").Split(".")[0])
if ($nodeMajor -lt 20) { throw "Node.js 20.19+ or 22.12+ is required (found $(node --version)): https://nodejs.org/" }

# --- server ------------------------------------------------------------------
Push-Location (Join-Path $root "server")
try {
    if (-not (Test-Path ".venv")) {
        $extra = @($pythonCmd | Select-Object -Skip 1)
        & $pythonCmd[0] @extra -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw "Could not create the Python environment." }
    }
    & .\.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
    & .\.venv\Scripts\python.exe -m pip install -e ".[dev]" --quiet
    if ($LASTEXITCODE -ne 0) { throw "Installing the server dependencies failed." }
    Write-Host "  server dependencies installed" -ForegroundColor Green
}
finally { Pop-Location }

# --- console -----------------------------------------------------------------
Push-Location (Join-Path $root "console")
try {
    if (Test-Path "package-lock.json") { npm ci --no-audit --no-fund } else { npm install --no-audit --no-fund }
    if ($LASTEXITCODE -ne 0) { throw "Installing the console dependencies failed." }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Building the console failed." }
    Write-Host "  console built" -ForegroundColor Green
}
finally { Pop-Location }

Write-Host "Done. Start FALCON with: powershell -ExecutionPolicy Bypass -File scripts\start.ps1" -ForegroundColor Cyan
