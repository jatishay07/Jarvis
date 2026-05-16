#!/usr/bin/env bash
# Backward-compatible entry: removes HUD app LaunchAgent + ~/Applications copy (see uninstall_hud_login.sh).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$HERE/uninstall_hud_login.sh" "$@"
