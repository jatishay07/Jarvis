#!/usr/bin/env bash
# Quit any running AppKit/Tk HUD, then start again from this repo (correct paths).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
export JARVIS_CONFIG="${JARVIS_CONFIG:-$ROOT/config/jarvis.json}"

pkill -f "jarvis_hud_appkit.py" 2>/dev/null || true
pkill -f "jarvis_hud_slider.py" 2>/dev/null || true
sleep 0.45

if [[ ! -f "$JARVIS_CONFIG" ]]; then
  echo "Missing config: $JARVIS_CONFIG" >&2
  exit 1
fi

if [[ "$(uname -s)" == "Darwin" ]]; then
  export JARVIS_HUD_BACKEND="${JARVIS_HUD_BACKEND:-tk}"
  if [[ "${JARVIS_HUD_BACKEND}" == "tk" && -z "${PYTHON_JARVIS_HUD:-}" && -x /usr/bin/python3 ]]; then
    export PYTHON_JARVIS_HUD="/usr/bin/python3"
  fi
fi

echo "Starting Jarvis HUD (config: $JARVIS_CONFIG backend=${JARVIS_HUD_BACKEND:-auto} python=${PYTHON_JARVIS_HUD:-auto})"
exec "$HERE/jarvis_hud_slider.sh" "$@"
