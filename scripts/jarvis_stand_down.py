#!/usr/bin/env python3
"""Jarvis stand-down: goodbye typing+voice, quit Spotify/apps, Focus off, restore wallpaper."""
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


def _stand_down_apps_to_quit(cfg: dict) -> list[str]:
    """Merge config list with terminal and Spotify (deduped, order preserved)."""
    raw = list(cfg.get("stand_down_apps_quit", ["Kiro", "Cursor"]))
    out: list[str] = []
    seen: set[str] = set()
    for a in raw:
        k = a.casefold()
        if k not in seen:
            seen.add(k)
            out.append(a)
    if cfg.get("stand_down_quit_terminal", False):
        ta = cfg.get("terminal_app", "Terminal")
        k = ta.casefold()
        if k not in seen:
            seen.add(k)
            out.append(ta)
    if cfg.get("stand_down_quit_spotify", True) and "spotify" not in seen:
        out.append("Spotify")
        seen.add("spotify")
    return out


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


def _say(text: str, voice: str, cfg: dict) -> None:
    scripts = Path(__file__).resolve().parent
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from jarvis_holographic_wallpaper import run_cli_say

    run_cli_say(text, voice, cfg)


def _afplay(path: str) -> None:
    p = Path(os.path.expanduser(path)).expanduser().resolve()
    if p.is_file():
        subprocess.run(["afplay", str(p)], capture_output=True, text=True)


def _restore_wallpaper(restore_path: Path, util: Path) -> None:
    if not restore_path.is_file():
        return
    r = subprocess.run(
        [sys.executable, str(util), "restore", str(restore_path)],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print(
            f"Warning: wallpaper restore failed: {r.stderr.strip() or r.stdout.strip()}",
            file=sys.stderr,
        )


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

    hw = cfg.get("holographic_wallpaper", {})
    ack_msg = cfg.get("stand_down_ack_message", "Very good, sir")
    voice = cfg.get("say_voice", "")
    sd_sound = str(cfg.get("stand_down_sound", "")).strip()
    if sd_sound:
        _afplay(sd_sound)

    holo_ack = (
        cfg.get("stand_down_ack_enabled", True)
        and hw.get("enabled", False)
        and hw.get("stand_down_ack", True)
    )

    # Goodbye: subtitle typing + erase + black (same pipeline as welcome), then restore wallpaper
    if holo_ack:
        scripts = Path(__file__).resolve().parent
        if str(scripts) not in sys.path:
            sys.path.insert(0, str(scripts))
        from jarvis_holographic_wallpaper import play_typing_wallpaper

        try:
            play_typing_wallpaper(cfg, state, ack_msg, voice, end_with_black=True)
        except Exception as e:
            print(f"Stand-down typing wallpaper failed: {e}", file=sys.stderr)
            if cfg.get("stand_down_ack_enabled", True):
                _say(ack_msg, voice, cfg)
        # Lab session used a black desktop; bring back the user's wallpaper for quit/Focus
        _restore_wallpaper(restore_path, util)
    else:
        # No holo goodbye: still on black lab wallpaper — restore before pausing/quitting
        _restore_wallpaper(restore_path, util)

    _spotify_pause()

    apps = _stand_down_apps_to_quit(cfg)
    for app in apps:
        _quit_app(app)

    off_name = cfg.get("shortcut_focus_off", "")
    if off_name:
        subprocess.run(["shortcuts", "run", off_name], capture_output=True, text=True)

    # Second pass if the first restore failed, or Focus/quit altered desktop state
    _restore_wallpaper(restore_path, util)

    if session_path.is_file():
        session_path.unlink()

    if cfg.get("stand_down_ack_enabled", True) and not holo_ack:
        _say(ack_msg, voice, cfg)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
