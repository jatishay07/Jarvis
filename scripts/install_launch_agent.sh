#!/usr/bin/env bash
# Install LaunchAgent so the clap listener runs at login and stays running (KeepAlive).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
PLIST_LABEL="com.jarvis.claplistener"
PLIST_DEST="${HOME}/Library/LaunchAgents/${PLIST_LABEL}.plist"
CONFIG="${REPO}/config/jarvis.json"
LISTENER="${REPO}/scripts/double_clap_listener.py"

if [[ ! -f "$CONFIG" ]]; then
  echo "Missing $CONFIG — copy config/jarvis.example.json to config/jarvis.json first." >&2
  exit 1
fi
if [[ ! -f "$LISTENER" ]]; then
  echo "Missing $LISTENER" >&2
  exit 1
fi

PYTHON="${REPO}/.venv/bin/python3"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3 || true)"
fi
if [[ -z "$PYTHON" || ! -x "$PYTHON" ]]; then
  echo "No Python found. Create a venv: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

mkdir -p "${HOME}/.jarvis"
LOG_OUT="${HOME}/.jarvis/listener.log"
LOG_ERR="${HOME}/.jarvis/listener.err.log"

# XML-escape & < > in paths (rare in home paths)
xml_escape() {
  printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'
}

E_PYTHON="$(xml_escape "$PYTHON")"
E_LISTENER="$(xml_escape "$LISTENER")"
E_CONFIG="$(xml_escape "$CONFIG")"
E_REPO="$(xml_escape "$REPO")"
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
		<string>${E_PYTHON}</string>
		<string>${E_LISTENER}</string>
		<string>${E_CONFIG}</string>
	</array>
	<key>WorkingDirectory</key>
	<string>${E_REPO}</string>
	<key>EnvironmentVariables</key>
	<dict>
		<key>JARVIS_CONFIG</key>
		<string>${E_CONFIG}</string>
	</dict>
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
  launchctl unload "${PLIST_DEST}" 2>/dev/null || true
fi
cp "$TMP" "$PLIST_DEST"
echo "Wrote ${PLIST_DEST}"
echo "Using Python: ${PYTHON}"

launchctl load -w "$PLIST_DEST"
echo "Loaded ${PLIST_LABEL} — listener starts now and at every login."
echo ""
echo "IMPORTANT: System Settings → Privacy & Security → Microphone"
echo "  Allow the app: ${PYTHON}"
echo "  (or 'Python' if macOS groups it that way)"
echo ""
echo "Logs: ${LOG_OUT} and ${LOG_ERR}"
echo "Stop: ${REPO}/scripts/uninstall_launch_agent.sh"
