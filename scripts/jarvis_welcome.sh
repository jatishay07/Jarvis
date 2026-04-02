#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
export JARVIS_CONFIG="${JARVIS_CONFIG:-$ROOT/config/jarvis.json}"
if [[ -x "$ROOT/.venv/bin/python3" ]]; then
  exec "$ROOT/.venv/bin/python3" "$HERE/jarvis_welcome.py" "$@"
fi
exec python3 "$HERE/jarvis_welcome.py" "$@"
