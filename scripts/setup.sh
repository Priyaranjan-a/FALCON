#!/usr/bin/env sh
# FALCON: install the server and console, then build the console.
# Needs Python 3.12+ and Node.js 20.19+ (or 22.12+). Nothing is installed outside this folder.
set -eu
root="$(cd "$(dirname "$0")/.." && pwd)"

echo "FALCON setup"
py=""
for candidate in python3.14 python3.13 python3.12 python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' 2>/dev/null; then
    py="$candidate"; break
  fi
done
[ -n "$py" ] || { echo "Python 3.12 or newer is required: https://www.python.org/downloads/" >&2; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Node.js 20.19+ or 22.12+ is required: https://nodejs.org/" >&2; exit 1; }
node_major="$(node --version | sed 's/^v//' | cut -d. -f1)"
[ "$node_major" -ge 20 ] || { echo "Node.js 20.19+ or 22.12+ is required (found $(node --version))" >&2; exit 1; }

cd "$root/server"
[ -d .venv ] || "$py" -m venv .venv
.venv/bin/python -m pip install --upgrade pip --quiet
.venv/bin/python -m pip install -e ".[dev]" --quiet
echo "  server dependencies installed"

cd "$root/console"
if [ -f package-lock.json ]; then npm ci --no-audit --no-fund; else npm install --no-audit --no-fund; fi
npm run build
echo "  console built"
echo "Done. Start FALCON with: sh scripts/start.sh"
