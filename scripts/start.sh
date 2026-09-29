#!/usr/bin/env sh
# FALCON: serve the API and the console from one process on one port.
# Usage: sh scripts/start.sh [--no-demo]
#
# The first run installs everything (scripts/setup.sh) and, unless --no-demo is
# given, creates a demonstration organisation with an admin account, ten
# systems and scans of the bundled sample estates. The sign-in is printed below.
set -eu
root="$(cd "$(dirname "$0")/.." && pwd)"
if [ ! -x "$root/server/.venv/bin/python" ] || [ ! -f "$root/console/dist/index.html" ]; then
  echo "First run: installing FALCON (a few minutes, once)."
  sh "$root/scripts/setup.sh"
fi
echo "FALCON is starting at http://${FALCON_HOST:-127.0.0.1}:${FALCON_PORT:-8600}"
cd "$root/server"
if [ "${1:-}" = "--no-demo" ]; then
  exec .venv/bin/python -m falcon serve
fi
exec .venv/bin/python -m falcon serve --demo
