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


def _spotify_stinger(uri: str, seconds: float, cfg: dict) -> None:
    """Play preview without activating Spotify so the desktop wallpaper stays visible."""
    esc = uri.replace("\\", "\\\\").replace('"', '\\"')
    subprocess.run(
        ["open", "-g", "-j", "-a", "Spotify"],
        capture_output=True,
        text=True,
    )
    for _ in range(60):
        chk = subprocess.run(
            ["osascript", "-e", 'tell application "System Events" to return (name of processes) contains "Spotify"'],
            capture_output=True,
            text=True,
        )
        if chk.returncode == 0 and "true" in chk.stdout.lower():
            break
        time.sleep(0.15)
    time.sleep(0.35)
    play_script = f"""
    tell application "Spotify"
      play track "{esc}"
    end tell
    """
    subprocess.run(["osascript", "-e", play_script], capture_output=True, text=True)
    if cfg.get("welcome_dock_lab_after_apps", True):
        _dock_lab_behind_desktop(cfg)
    time.sleep(seconds)
    pause_script = """
    tell application "Spotify"
      pause
    end tell
    """
    subprocess.run(["osascript", "-e", pause_script], capture_output=True, text=True)


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


def _prepare_desktop_for_wallpaper(hide_other_apps: bool) -> None:
    """Bring Finder forward so the desktop picture is visible; optionally Hide Others."""
    esc_hide = "true" if hide_other_apps else "false"
    script = f"""
    tell application "Finder" to activate
    delay 0.25
    if {esc_hide} then
      tell application "System Events"
        keystroke "h" using {{command down, option down}}
      end tell
    end if
    """
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if r.returncode != 0:
        print(
            f"Warning: welcome_prepare_desktop (Finder / Hide Others) failed: {r.stderr.strip() or r.stdout.strip()}",
            file=sys.stderr,
        )


def _terminal_process_name(terminal_app: str) -> str:
    tl = terminal_app.lower()
    if "iterm" in tl:
        return "iTerm2"
    return terminal_app


def _open_app(
    name: str,
    *,
    background: bool = False,
    hidden: bool = False,
) -> None:
    if background:
        cmd = (
            ["open", "-g", "-j", "-a", name]
            if hidden
            else ["open", "-g", "-a", name]
        )
        subprocess.run(cmd, check=False)
    else:
        subprocess.run(["open", "-a", name], check=False)


def _hide_processes(names: list[str]) -> None:
    """Send app windows behind the desktop (Finder stays usable)."""
    if not names:
        return
    blocks: list[str] = []
    for raw in names:
        n = raw.strip()
        if not n:
            continue
        esc = n.replace("\\", "\\\\").replace('"', '\\"')
        blocks.append(
            f'        try\n          set visible of process "{esc}" to false\n        end try\n'
        )
    if not blocks:
        return
    script = 'tell application "System Events"\n' + "".join(blocks) + "end tell\n"
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if r.returncode != 0:
        print(
            f"Warning: could not hide processes (Automation for System Events?): {r.stderr.strip() or r.stdout.strip()}",
            file=sys.stderr,
        )


def _lab_process_names(cfg: dict) -> list[str]:
    apps = cfg.get("apps", {})
    names = [
        apps.get("kiro", "Kiro"),
        apps.get("cursor", "Cursor"),
    ]
    if cfg.get("terminal_open_codex_claude", True):
        names.append(_terminal_process_name(cfg.get("terminal_app", "Terminal")))
    if str(cfg.get("spotify_track_uri", "")).strip():
        names.append("Spotify")
    return names


def _dock_lab_behind_desktop(cfg: dict) -> None:
    _hide_processes(_lab_process_names(cfg))
    subprocess.run(
        ["osascript", "-e", 'tell application "Finder" to activate'],
        capture_output=True,
        text=True,
    )


def _terminal_codex_claude(
    cfg: dict,
    *,
    activate: bool = False,
    hidden_launch: bool = True,
) -> None:
    if not cfg.get("terminal_open_codex_claude", True):
        return
    term = cfg.get("terminal_app", "Terminal")
    if hidden_launch:
        subprocess.run(
            ["open", "-g", "-j", "-a", term],
            capture_output=True,
            text=True,
        )
    else:
        subprocess.run(["open", "-g", "-a", term], capture_output=True, text=True)
    time.sleep(0.35)
    t = term.lower()
    if "iterm" in t:
        esc = term.replace("\\", "\\\\").replace('"', '\\"')
        if activate:
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
            tell application "{esc}"
              create window with default profile
              tell current session of current window to write text "codex"
              tell current window
                create tab with default profile
                tell current session to write text "claude"
              end tell
            end tell
            '''
    elif activate:
        script = f'''
        tell application "{term}"
          activate
          do script "codex"
          delay 0.3
          do script "claude"
        end tell
        '''
    else:
        script = f'''
        tell application "{term}"
          do script "codex"
          delay 0.3
          do script "claude"
        end tell
        '''
    subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if cfg.get("welcome_dock_lab_after_apps", True):
        _dock_lab_behind_desktop(cfg)


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
    prepare = cfg.get("welcome_prepare_desktop", True)
    hide_others = cfg.get("welcome_hide_other_apps", True)
    apps_bg = cfg.get("welcome_open_apps_background", True)
    apps_hidden = cfg.get("welcome_launch_apps_hidden", True)
    dock_after = cfg.get("welcome_dock_lab_after_apps", True)
    term_delay = float(cfg.get("welcome_delay_terminal_seconds", 6.0))
    term_activate = cfg.get("welcome_terminal_activate_after_delay", False)
    term_hidden = cfg.get("welcome_terminal_hidden_launch", True)
    try:
        _backup_wallpaper(state)
        if prepare:
            _prepare_desktop_for_wallpaper(hide_others)
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
    spotify_th: threading.Thread | None = None
    if uri:
        spotify_th = threading.Thread(
            target=_spotify_stinger,
            args=(uri, sec, cfg),
            daemon=False,
            name="jarvis-spotify-stinger",
        )
        spotify_th.start()

    apps = cfg.get("apps", {})
    _open_app(
        apps.get("kiro", "Kiro"),
        background=apps_bg,
        hidden=apps_hidden and apps_bg,
    )
    _open_app(
        apps.get("cursor", "Cursor"),
        background=apps_bg,
        hidden=apps_hidden and apps_bg,
    )
    if dock_after and apps_bg:
        time.sleep(0.45)
        _dock_lab_behind_desktop(cfg)

    def _run_terminal() -> None:
        _terminal_codex_claude(
            cfg,
            activate=term_activate,
            hidden_launch=term_hidden,
        )

    term_timer: threading.Timer | None = None
    if term_delay > 0:
        term_timer = threading.Timer(term_delay, _run_terminal)
        term_timer.start()
    else:
        _run_terminal()

    session_path.write_text(
        json.dumps({"active": True, "started": time.time()}, indent=2),
        encoding="utf-8",
    )

    if term_timer is not None:
        term_timer.join()
    if spotify_th is not None:
        spotify_th.join(timeout=max(sec, term_delay) + 30.0)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
