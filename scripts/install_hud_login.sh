#!/usr/bin/env bash
# Install Jarvis HUD.app to ~/Applications, write ~/.jarvis/repository_path, load LaunchAgent (login + KeepAlive).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
APP_SRC="${REPO}/macos/Jarvis HUD.app"
DEST_APP="${HOME}/Applications/Jarvis HUD.app"
CONFIG="${REPO}/config/jarvis.json"
HUD_CONFIG="${HOME}/.jarvis/hud_config.json"
HUD_RUNTIME_DIR="${HOME}/.jarvis/hud_runtime"
HUD_PYTHON_PATH_FILE="${HOME}/.jarvis/hud_python_path"
PLIST_LABEL="com.jarvis.hud"
PLIST_DEST="${HOME}/Library/LaunchAgents/${PLIST_LABEL}.plist"
LOG_OUT="${HOME}/.jarvis/hud.app.log"
LOG_ERR="${HOME}/.jarvis/hud.app.err.log"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This script is for macOS only." >&2
  exit 1
fi
if [[ ! -d "$APP_SRC" ]]; then
  echo "Missing bundle: $APP_SRC" >&2
  exit 1
fi
if [[ ! -f "$CONFIG" ]]; then
  echo "Missing $CONFIG — copy config/jarvis.example.json first." >&2
  exit 1
fi

mkdir -p "${HOME}/.jarvis" "${HOME}/Applications" "${HUD_RUNTIME_DIR}"
printf '%s\n' "$REPO" > "${HOME}/.jarvis/repository_path"
cp "$CONFIG" "$HUD_CONFIG"
cp "${REPO}/scripts/jarvis_hud_slider.py" "${HUD_RUNTIME_DIR}/jarvis_hud_slider.py"
cp "${REPO}/scripts/jarvis_hud_lib.py" "${HUD_RUNTIME_DIR}/jarvis_hud_lib.py"
cp "${REPO}/scripts/jarvis_hud_appkit.py" "${HUD_RUNTIME_DIR}/jarvis_hud_appkit.py"

HUD_PYTHON="/usr/bin/python3"
PY="${REPO}/.venv/bin/python3"
if [[ -x "$PY" ]] && "$PY" -c "import objc; from Cocoa import NSApplication" 2>/dev/null; then
  HUD_PYTHON="$PY"
fi
printf '%s\n' "$HUD_PYTHON" > "$HUD_PYTHON_PATH_FILE"

rm -rf "$DEST_APP"
cp -R "$APP_SRC" "$DEST_APP"
chmod +x "${DEST_APP}/Contents/MacOS/jarvis-hud-launcher"

LAUNCHER="${DEST_APP}/Contents/MacOS/jarvis-hud-launcher"
if [[ ! -x "$LAUNCHER" ]]; then
  echo "Launcher not executable: $LAUNCHER" >&2
  exit 1
fi

PY="${REPO}/.venv/bin/python3"
if [[ -x "$PY" ]] && ! "$PY" -c "import objc; from Cocoa import NSApplication" 2>/dev/null; then
  echo ""
  echo "Warning: PyObjC not importable in .venv. Install with:"
  echo "  cd \"$REPO\" && .venv/bin/pip install pyobjc-framework-Cocoa"
  echo ""
fi

xml_escape() {
  printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'
}

E_LAUNCHER="$(xml_escape "$LAUNCHER")"
E_LOG_OUT="$(xml_escape "$LOG_OUT")"
E_LOG_ERR="$(xml_escape "$LOG_ERR")"

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

cat >"$TMP" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>Label</key>
	<string>${PLIST_LABEL}</string>
	<key>ProgramArguments</key>
	<array>
		<string>${E_LAUNCHER}</string>
	</array>
	<key>RunAtLoad</key>
	<true/>
	<key>KeepAlive</key>
	<true/>
	<key>StandardOutPath</key>
	<string>${E_LOG_OUT}</string>
	<key>StandardErrorPath</key>
	<string>${E_LOG_ERR}</string>
</dict>
</plist>
EOF

mkdir -p "${HOME}/Library/LaunchAgents"
if [[ -f "$PLIST_DEST" ]]; then
  echo "Unloading existing ${PLIST_LABEL}…"
  launchctl unload "$PLIST_DEST" 2>/dev/null || true
fi
cp "$TMP" "$PLIST_DEST"
launchctl load -w "$PLIST_DEST"

echo ""
echo "Installed:"
echo "  App:  $DEST_APP"
echo "  Repo: $REPO  (also in ~/.jarvis/repository_path)"
echo "  HUD runtime: $HUD_RUNTIME_DIR"
echo "  HUD config: $HUD_CONFIG"
echo "  HUD python: $HUD_PYTHON"
echo "  Agent: $PLIST_LABEL (RunAtLoad + KeepAlive)"
echo "  Logs: $LOG_OUT / $LOG_ERR"
echo ""
echo "The HUD should start now. Log out and back in to confirm login startup."
echo "Remove: ${REPO}/scripts/uninstall_hud_login.sh"
