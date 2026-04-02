#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
export JARVIS_CONFIG="${JARVIS_CONFIG:-$ROOT/config/jarvis.json}"
exec python3 "$HERE/jarvis_welcome.py" "$@"
