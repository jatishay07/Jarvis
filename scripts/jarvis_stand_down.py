#!/usr/bin/env python3
"""Jarvis stand-down: pause Spotify, quit apps, Focus off, restore wallpaper, clear session."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _load_config(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _expand(p: str) -> Path:
    return Path(os.path.expanduser(p)).resolve()


def _state_dir(cfg: dict) -> Path:
    return _expand(cfg.get("state_dir", "~/.jarvis"))


def _run_applescript_quiet(source: str) -> bool:
    r = subprocess.run(["osascript", "-e", source], capture_output=True, text=True)
    return r.returncode == 0


def _spotify_pause() -> None:
    script = """
    tell application "Spotify"
      if player state is playing then pause
    end tell
    """
    subprocess.run(["osascript", "-e", script], capture_output=True, text=True)


def _quit_app(name: str) -> None:
    esc = name.replace("\\", "\\\\").replace('"', '\\"')
    script = f"""
    try
      tell application "{esc}"
        if it is running then
          try
            quit saving yes
          on error
            quit
          end try
        end if
      end tell
    end try
    """
    _run_applescript_quiet(script)


def _say(text: str, voice: str) -> None:
    cmd = ["say"]
    if voice:
        cmd.extend(["-v", voice])
    cmd.append(text)
    subprocess.run(cmd, check=False)


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    cfg_path = Path(os.environ.get("JARVIS_CONFIG", root / "config" / "jarvis.json"))
    if len(sys.argv) > 1:
        cfg_path = Path(sys.argv[1]).expanduser().resolve()
    if not cfg_path.is_file():
        print(f"Missing config: {cfg_path}", file=sys.stderr)
        return 1

    cfg = _load_config(cfg_path)
    state = _state_dir(cfg)
    session_path = state / "lab_session.json"
    restore_path = state / "wallpaper_restore.json"
    util = Path(__file__).resolve().parent / "wallpaper_util.py"

    _spotify_pause()

    for app in cfg.get("stand_down_apps_quit", ["Kiro", "Cursor", "Terminal"]):
        _quit_app(app)

    off_name = cfg.get("shortcut_focus_off", "")
    if off_name:
        subprocess.run(["shortcuts", "run", off_name], capture_output=True, text=True)

    hw = cfg.get("holographic_wallpaper", {})
    ack_msg = cfg.get("stand_down_ack_message", "Very good, sir")
    voice = cfg.get("say_voice", "")
    holo_ack = (
        cfg.get("stand_down_ack_enabled", True)
        and hw.get("enabled", False)
        and hw.get("stand_down_ack", True)
    )
    if holo_ack:
        scripts = Path(__file__).resolve().parent
        if str(scripts) not in sys.path:
            sys.path.insert(0, str(scripts))
        from jarvis_holographic_wallpaper import apply_holographic_wallpaper

        try:
            apply_holographic_wallpaper(cfg, state, ack_msg)
        except Exception as e:
            print(f"Holographic stand-down wallpaper failed: {e}", file=sys.stderr)
        _say(ack_msg, voice)

    if restore_path.is_file():
        try:
            subprocess.run(
                [sys.executable, str(util), "restore", str(restore_path)],
                check=False,
            )
        except OSError:
            pass

    if session_path.is_file():
        session_path.unlink()

    if cfg.get("stand_down_ack_enabled", True) and not holo_ack:
        _say(ack_msg, voice)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
