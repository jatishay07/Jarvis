#!/usr/bin/env bash
# HUD: On macOS prefer AppKit (stable); Tk often crashes Homebrew Python ("Python quit unexpectedly").
# Then Tk → AppleScript dialog.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
export JARVIS_CONFIG="${JARVIS_CONFIG:-$ROOT/config/jarvis.json}"

python_supports_appkit_hud() {
  local py="$1"
  "$py" - "$HERE" <<'PY' >/dev/null 2>&1
import sys
scripts_dir = sys.argv[1]
sys.path.insert(0, scripts_dir)
import jarvis_hud_appkit as hud
raise SystemExit(0 if getattr(hud, "_HAVE_COCOA", False) else 1)
PY
}

if [[ -n "${PYTHON_JARVIS_HUD:-}" ]]; then
  if python_supports_appkit_hud "$PYTHON_JARVIS_HUD"; then
    exec "$PYTHON_JARVIS_HUD" -B "$HERE/jarvis_hud_appkit.py" "$@"
  fi
  exec "$PYTHON_JARVIS_HUD" "$HERE/jarvis_hud_slider.py" "$@"
fi

pick_tk_python() {
  local v="$ROOT/.venv/bin/python3"
  if [[ -x "$v" ]] && "$v" -c "import tkinter" 2>/dev/null; then
    printf '%s' "$v"
    return 0
  fi
  if [[ -x /usr/bin/python3 ]] && /usr/bin/python3 -c "import tkinter" 2>/dev/null; then
    printf '%s' "/usr/bin/python3"
    return 0
  fi
  if command -v python3 >/dev/null && python3 -c "import tkinter" 2>/dev/null; then
    printf '%s' "$(command -v python3)"
    return 0
  fi
  return 1
}

pick_appkit_python() {
  local py
  for py in "$ROOT/.venv/bin/python3" /usr/bin/python3 "$(command -v python3 2>/dev/null)"; do
    [[ -n "$py" && -x "$py" ]] || continue
    if python_supports_appkit_hud "$py"; then
      printf '%s' "$py"
      return 0
    fi
  done
  return 1
}

# Force order: 1=appkit 2=tk  (default on Darwin: appkit first)
HUD_BACKEND="${JARVIS_HUD_BACKEND:-}"
if [[ "$HUD_BACKEND" == "tk" ]]; then
  if PYTHON="$(pick_tk_python)"; then
    exec "$PYTHON" "$HERE/jarvis_hud_slider.py" "$@"
  fi
  if PYTHON="$(pick_appkit_python)"; then
    exec "$PYTHON" -B "$HERE/jarvis_hud_appkit.py" "$@"
  fi
elif [[ "$(uname -s)" == "Darwin" ]]; then
  if PYTHON="$(pick_appkit_python)"; then
    exec "$PYTHON" -B "$HERE/jarvis_hud_appkit.py" "$@"
  fi
  if PYTHON="$(pick_tk_python)"; then
    exec "$PYTHON" "$HERE/jarvis_hud_slider.py" "$@"
  fi
else
  if PYTHON="$(pick_tk_python)"; then
    exec "$PYTHON" "$HERE/jarvis_hud_slider.py" "$@"
  fi
  if PYTHON="$(pick_appkit_python)"; then
    exec "$PYTHON" -B "$HERE/jarvis_hud_appkit.py" "$@"
  fi
fi

echo "Jarvis HUD: PyObjC and Tk unavailable." >&2
echo "  pip install pyobjc-framework-Cocoa   # native slider" >&2
echo "Opening the dialog HUD instead…" >&2
exec python3 "$HERE/jarvis_hud_dialog.py" "$@"
