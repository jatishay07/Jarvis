#!/usr/bin/env bash
# Unload HUD LaunchAgent, remove plist, optionally remove Jarvis HUD.app from ~/Applications.
set -euo pipefail

PLIST_LABEL="com.jarvis.hud"
PLIST_DEST="${HOME}/Library/LaunchAgents/${PLIST_LABEL}.plist"
DEST_APP="${HOME}/Applications/Jarvis HUD.app"

if [[ -f "$PLIST_DEST" ]]; then
  launchctl unload "$PLIST_DEST" 2>/dev/null || true
  rm -f "$PLIST_DEST"
  echo "Removed LaunchAgent ${PLIST_LABEL}."
else
  echo "No plist at ${PLIST_DEST}"
fi

if [[ -d "$DEST_APP" ]]; then
  rm -rf "$DEST_APP"
  echo "Removed ${DEST_APP}"
else
  echo "No app at ${DEST_APP}"
fi

echo "Optional: rm ~/.jarvis/repository_path if you no longer use the HUD app."
