#!/usr/bin/env python3
"""Jarvis welcome routine: TTS, Focus, wallpaper, apps, Spotify stinger, lab session."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path


def _root() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_config(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _expand(p: str) -> Path:
    return Path(os.path.expanduser(p)).resolve()


def _state_dir(cfg: dict) -> Path:
    d = _expand(cfg.get("state_dir", "~/.jarvis"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _run_applescript(source: str) -> None:
    r = subprocess.run(["osascript", "-e", source], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "AppleScript failed")


def _spotify_stinger(uri: str, seconds: float) -> None:
    esc = uri.replace("\\", "\\\\").replace('"', '\\"')
    script = f"""
    tell application "Spotify" to activate
    delay 0.4
    tell application "Spotify" to play track "{esc}"
    delay {seconds}
    tell application "Spotify" to pause
    """
    subprocess.run(["osascript", "-e", script], capture_output=True, text=True)


def _backup_wallpaper(state: Path) -> None:
    util = Path(__file__).resolve().parent / "wallpaper_util.py"
    r = subprocess.run(
        [sys.executable, str(util), "backup"],
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr or "wallpaper backup failed")
    data = json.loads(r.stdout or '{"desktops":[]}')
    (state / "wallpaper_restore.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def _set_lab_wallpaper(cfg: dict, state: Path, message_text: str) -> None:
    util = Path(__file__).resolve().parent / "wallpaper_util.py"
    hw = cfg.get("holographic_wallpaper", {})
    if hw.get("enabled", False):
        scripts = Path(__file__).resolve().parent
        if str(scripts) not in sys.path:
            sys.path.insert(0, str(scripts))
        from jarvis_holographic_wallpaper import apply_holographic_wallpaper

        apply_holographic_wallpaper(cfg, state, message_text)
        return
    lab = _expand(cfg["wallpaper_lab_image"])
    subprocess.run([sys.executable, str(util), "set", str(lab)], check=True)


def _shortcuts_run(name: str) -> None:
    if not name.strip():
        return
    r = subprocess.run(["shortcuts", "run", name], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"Warning: shortcuts run '{name}': {r.stderr.strip()}", file=sys.stderr)


def _say(text: str, voice: str) -> None:
    cmd = ["say"]
    if voice:
        cmd.extend(["-v", voice])
    cmd.append(text)
    subprocess.run(cmd, check=False)


def _open_app(name: str) -> None:
    subprocess.run(["open", "-a", name], check=False)


def _terminal_codex_claude(cfg: dict) -> None:
    if not cfg.get("terminal_open_codex_claude", True):
        return
    term = cfg.get("terminal_app", "Terminal")
    t = term.lower()
    if "iterm" in t:
        esc = term.replace("\\", "\\\\").replace('"', '\\"')
        script = f'''
        tell application "{esc}"
          activate
          create window with default profile
          tell current session of current window to write text "codex"
          tell current window
            create tab with default profile
            tell current session to write text "claude"
          end tell
        end tell
        '''
    else:
        script = f'''
        tell application "{term}"
          activate
          do script "codex"
          delay 0.3
          do script "claude"
        end tell
        '''
    subprocess.run(["osascript", "-e", script], capture_output=True, text=True)


def main() -> int:
    root = _root()
    cfg_path = Path(os.environ.get("JARVIS_CONFIG", root / "config" / "jarvis.json"))
    if len(sys.argv) > 1:
        cfg_path = Path(sys.argv[1]).expanduser().resolve()
    if not cfg_path.is_file():
        print(f"Missing config: {cfg_path}", file=sys.stderr)
        print("Copy config/jarvis.example.json to config/jarvis.json and edit paths.", file=sys.stderr)
        return 1

    cfg = _load_config(cfg_path)
    state = _state_dir(cfg)
    session_path = state / "lab_session.json"

    if session_path.is_file():
        try:
            prev = json.loads(session_path.read_text(encoding="utf-8"))
            if prev.get("active"):
                print("Lab session already active; skip welcome.", file=sys.stderr)
                return 0
        except json.JSONDecodeError:
            pass

    welcome_text = cfg.get("welcome_message", "Welcome Home Sir")
    voice = cfg.get("say_voice", "")
    hw = cfg.get("holographic_wallpaper", {})
    try:
        _backup_wallpaper(state)
        if hw.get("enabled", False):
            scripts = Path(__file__).resolve().parent
            if str(scripts) not in sys.path:
                sys.path.insert(0, str(scripts))
            from jarvis_holographic_wallpaper import play_typing_wallpaper

            play_typing_wallpaper(cfg, state, welcome_text, voice)
        else:
            _set_lab_wallpaper(cfg, state, welcome_text)
            _say(welcome_text, voice)
    except Exception as e:
        print(f"Wallpaper step failed: {e}", file=sys.stderr)
        return 1

    on_name = cfg.get("shortcut_focus_on", "")
    if on_name:
        _shortcuts_run(on_name)

    uri = cfg.get("spotify_track_uri", "")
    sec = float(cfg.get("music_preview_seconds", 10))
    if uri:
        threading.Thread(target=_spotify_stinger, args=(uri, sec), daemon=True).start()

    apps = cfg.get("apps", {})
    _open_app(apps.get("kiro", "Kiro"))
    _open_app(apps.get("cursor", "Cursor"))
    _terminal_codex_claude(cfg)

    session_path.write_text(
        json.dumps({"active": True, "started": time.time()}, indent=2),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
