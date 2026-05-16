"""Shared helpers for HUD scripts (Tk slider + native dialog)."""
from __future__ import annotations

import fcntl
import json
import os
import shlex
import subprocess
from pathlib import Path


_HUD_LOCK_FILE = None


def repo_root() -> Path:
    env_root = os.environ.get("JARVIS_REPO_ROOT")
    if env_root:
        p = Path(env_root).expanduser().resolve()
        if p.is_dir():
            return p

    here = Path(__file__).resolve().parent.parent
    if (here / "scripts").is_dir() and (here / "config").is_dir():
        return here

    repo_file = Path.home() / ".jarvis" / "repository_path"
    try:
        raw = repo_file.read_text(encoding="utf-8").strip()
    except OSError:
        raw = ""
    if raw:
        p = Path(os.path.expanduser(raw)).resolve()
        if p.is_dir():
            return p

    return here


def scripts_dir() -> Path:
    here = Path(__file__).resolve().parent
    if (here / "jarvis_welcome.sh").is_file():
        return here
    return repo_root() / "scripts"


def resolve_cfg_path(argv: list[str]) -> Path:
    root = repo_root()
    p = Path(os.environ.get("JARVIS_CONFIG", str(root / "config" / "jarvis.json"))).expanduser().resolve()
    if len(argv) > 1 and not str(argv[1]).startswith("-"):
        p = Path(argv[1]).expanduser().resolve()
    return p


def load_cfg(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def state_dir(cfg: dict) -> Path:
    return Path(os.path.expanduser(cfg.get("state_dir", "~/.jarvis"))).resolve()


def acquire_hud_singleton(cfg: dict) -> bool:
    """Allow only one HUD process at a time across AppKit/Tk runtimes."""
    global _HUD_LOCK_FILE
    state = state_dir(cfg)
    state.mkdir(parents=True, exist_ok=True)
    lock_path = state / "hud.instance.lock"
    fh = lock_path.open("w")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return False
    fh.seek(0)
    fh.truncate()
    fh.write(f"{os.getpid()}\n")
    fh.flush()
    _HUD_LOCK_FILE = fh
    return True


def lab_active(cfg: dict) -> bool:
    sp = state_dir(cfg) / "lab_session.json"
    if not sp.is_file():
        return False
    try:
        return bool(json.loads(sp.read_text(encoding="utf-8")).get("active"))
    except (json.JSONDecodeError, OSError):
        return False


def hud_env(cfg_path: Path) -> dict:
    return {**os.environ, "JARVIS_CONFIG": str(cfg_path)}


def _terminal_app_from_cfg(cfg_path: Path) -> str:
    try:
        cfg = load_cfg(cfg_path)
    except Exception:
        return "Terminal"
    app = str(cfg.get("terminal_app", "Terminal")).strip()
    return app or "Terminal"


def _applescript_quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _spawn_via_terminal(script_name: str, cfg_path: Path) -> None:
    root = repo_root()
    script_path = root / "scripts" / script_name
    cfg_text = str(cfg_path)
    shell_cmd = (
        f"cd {shlex.quote(str(root))} && "
        f"JARVIS_CONFIG={shlex.quote(cfg_text)} "
        f"{shlex.quote(str(script_path))}"
    )
    app = _terminal_app_from_cfg(cfg_path)
    if "iterm" in app.lower():
        osa = f"""
        tell application "{app}"
          activate
          create window with default profile
          tell current session of current window to write text {_applescript_quote(shell_cmd)}
        end tell
        """
    else:
        osa = f'''
        tell application "Terminal"
          do script {_applescript_quote(shell_cmd)}
          activate
        end tell
        '''
    subprocess.run(["osascript", "-e", osa], capture_output=True, text=True, check=False)


def _spawn_script(script_name: str, cfg_path: Path) -> None:
    root = repo_root()
    sd = scripts_dir()
    script_path = sd / script_name
    try:
        subprocess.Popen(
            [str(script_path)],
            cwd=str(root),
            env=hud_env(cfg_path),
        )
        return
    except OSError:
        pass
    _spawn_via_terminal(script_name, cfg_path)


def spawn_welcome(cfg_path: Path) -> None:
    _spawn_script("jarvis_welcome.sh", cfg_path)


def spawn_stand_down(cfg_path: Path) -> None:
    _spawn_script("jarvis_stand_down.sh", cfg_path)
