#!/usr/bin/env python3
"""Backup and restore macOS desktop pictures via AppleScript."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run_osascript(source: str) -> str:
    r = subprocess.run(
        ["osascript", "-e", source],
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or r.stdout.strip() or "osascript failed")
    return r.stdout.strip()


def backup() -> list[str]:
    script = """
    tell application "System Events"
      set out to {}
      repeat with d in desktops
        try
          set end of out to (POSIX path of (picture of d as alias))
        on error
          set end of out to ""
        end try
      end repeat
      set AppleScript's text item delimiters to linefeed
      return out as string
    end tell
    """
    raw = _run_osascript(script)
    if not raw:
        return []
    return [p.strip() for p in raw.splitlines() if p.strip()]


def set_all_lab_image(posix_path: str) -> None:
    path = Path(posix_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Wallpaper not found: {path}")
    escaped = str(path).replace("\\", "\\\\").replace('"', '\\"')
    script = f"""
    tell application "System Events"
      tell every desktop
        set picture to "{escaped}"
      end tell
    end tell
    """
    _run_osascript(script)


def _escape_as_string_literal(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def restore(paths: list[str]) -> None:
    for i, p in enumerate(paths, start=1):
        if not p or not Path(p).expanduser().exists():
            continue
        esc = _escape_as_string_literal(str(Path(p).expanduser().resolve()))
        script = f"""
        tell application "System Events"
          tell desktop {i}
            set picture to "{esc}"
          end tell
        end tell
        """
        _run_osascript(script)


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: wallpaper_util.py backup | set <image_path> | restore <json_path>", file=sys.stderr)
        sys.exit(2)
    cmd = sys.argv[1]
    if cmd == "backup":
        paths = backup()
        print(json.dumps({"desktops": paths}))
        return
    if cmd == "set" and len(sys.argv) == 3:
        set_all_lab_image(sys.argv[2])
        return
    if cmd == "restore" and len(sys.argv) == 3:
        data = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
        restore(list(data.get("desktops", [])))
        return
    print("unknown command", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
