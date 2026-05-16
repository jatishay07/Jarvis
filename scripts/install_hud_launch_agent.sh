#!/usr/bin/env bash
# Backward-compatible entry: installs Jarvis HUD.app + login agent (see install_hud_login.sh).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$HERE/install_hud_login.sh" "$@"
