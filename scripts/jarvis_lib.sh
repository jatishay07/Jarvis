#!/usr/bin/env bash
# Shared helpers for Jarvis shell scripts.
set -euo pipefail

jarvis_root() {
  local here
  here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  (cd "$here/.." && pwd)
}

jarvis_config_path() {
  local root
  root="$(jarvis_root)"
  echo "${JARVIS_CONFIG:-$root/config/jarvis.json}"
}

# Usage: jarvis_json_get <keypath>  e.g. apps.kiro
jarvis_json_get() {
  local cfg keypath
  cfg="$(jarvis_config_path)"
  keypath="$1"
  python3 - "$cfg" "$keypath" <<'PY'
import json, sys
cfg, path = sys.argv[1], sys.argv[2]
with open(cfg, encoding="utf-8") as f:
    data = json.load(f)
cur = data
for part in path.split("."):
    if part == "":
        continue
    if isinstance(cur, dict) and part in cur:
        cur = cur[part]
    else:
        print("", end="")
        sys.exit(0)
if isinstance(cur, (dict, list)):
    print(json.dumps(cur))
else:
    print(cur)
PY
}
