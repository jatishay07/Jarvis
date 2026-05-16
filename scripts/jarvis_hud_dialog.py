#!/usr/bin/env python3
"""
Native macOS HUD (no Tkinter): pick Welcome or Stand down from a system dialog.
Use when jarvis_hud_slider.py fails (missing _tkinter, Tcl version mismatch, etc.).

  python3 scripts/jarvis_hud_dialog.py
  ./scripts/jarvis_hud_dialog.sh
"""
from __future__ import annotations

import subprocess
import sys

from jarvis_hud_lib import lab_active, load_cfg, resolve_cfg_path, spawn_stand_down, spawn_welcome


def _osascript_choose() -> str | None:
    """Returns 'welcome', 'stand_down', or None if cancelled."""
    script = r'''
set picked to choose from list {"Welcome (start lab)", "Stand down (end lab)"} with prompt "Jarvis — same as double-clap / stand-down phrase" with title "Jarvis HUD" default items {"Welcome (start lab)"}
if picked is false then return ""
return item 1 of picked
'''
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    line = (r.stdout or "").strip()
    if not line:
        return None
    if line.startswith("Welcome"):
        return "welcome"
    if line.startswith("Stand down"):
        return "stand_down"
    return None


def _confirm_stand_down() -> bool:
    script = r'''
set r to display dialog "Stand down and quit lab apps?" buttons {"Cancel", "Stand down"} default button "Stand down" cancel button "Cancel"
return button returned of r
'''
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if r.returncode != 0:
        return False
    return "Stand down" in (r.stdout or "")


def main() -> int:
    cfg_path = resolve_cfg_path(sys.argv)
    if not cfg_path.is_file():
        print(f"Missing config: {cfg_path}", file=sys.stderr)
        return 1
    cfg = load_cfg(cfg_path)
    hud = cfg.get("hud_slider") or {}
    confirm_sd = hud.get("confirm_stand_down", True)

    choice = _osascript_choose()
    if choice is None:
        return 0
    if choice == "welcome":
        if lab_active(cfg):
            subprocess.run(
                [
                    "osascript",
                    "-e",
                    'display dialog "Lab session is already active." buttons {"OK"} default button "OK"',
                ],
                capture_output=True,
                text=True,
            )
            return 0
        spawn_welcome(cfg_path)
        return 0
    if choice == "stand_down":
        if confirm_sd and not _confirm_stand_down():
            return 0
        spawn_stand_down(cfg_path)
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
