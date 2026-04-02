#!/usr/bin/env bash
set -euo pipefail

PLIST_LABEL="com.jarvis.claplistener"
PLIST_DEST="${HOME}/Library/LaunchAgents/${PLIST_LABEL}.plist"

if [[ -f "$PLIST_DEST" ]]; then
  launchctl unload "$PLIST_DEST" 2>/dev/null || true
  rm -f "$PLIST_DEST"
  echo "Removed ${PLIST_DEST} and unloaded ${PLIST_LABEL}."
else
  echo "No plist at ${PLIST_DEST}"
fi
