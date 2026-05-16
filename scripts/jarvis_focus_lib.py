"""Shared helpers for jarvis_request_focus: slug resolution, cooldown, activation."""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path


def _state_dir(cfg: dict) -> Path:
    d = Path(os.path.expanduser(cfg.get("state_dir", "~/.jarvis"))).resolve()
    d.mkdir(parents=True, exist_ok=True)
    return d


def lab_active(cfg: dict) -> bool:
    sp = _state_dir(cfg) / "lab_session.json"
    if not sp.is_file():
        return False
    try:
        return bool(json.loads(sp.read_text(encoding="utf-8")).get("active"))
    except (json.JSONDecodeError, OSError):
        return False


def resolve_app(slug: str, cfg: dict) -> str | None:
    """Return the macOS display name for slug, or None if unresolvable.

    Resolution order:
    1. lab_focus.sources[slug]
    2. apps[slug]  (for kiro/cursor convenience)
    3. None (unknown)

    A null/empty value at any step resolves to cfg['terminal_app'].
    """
    lab_focus = cfg.get("lab_focus", {})
    sources = lab_focus.get("sources", {})
    slug = slug.lower().strip()

    if slug in sources:
        val = sources[slug]
    elif slug in cfg.get("apps", {}):
        val = cfg["apps"][slug]
    else:
        return None

    if not val:
        val = cfg.get("terminal_app", "Terminal")
    return str(val)


def _cooldown_path(cfg: dict) -> Path:
    return _state_dir(cfg) / "lab_focus_last.json"


def within_cooldown(slug: str, cfg: dict) -> bool:
    """Return True if this slug is still within its per-source cooldown window."""
    secs = float(cfg.get("lab_focus", {}).get("cooldown_seconds", 3))
    try:
        data = json.loads(_cooldown_path(cfg).read_text(encoding="utf-8"))
        last = float(data.get(slug, 0))
        return (time.time() - last) < secs
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return False


def record_fire(slug: str, cfg: dict) -> None:
    """Persist cooldown timestamp for slug."""
    path = _cooldown_path(cfg)
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, json.JSONDecodeError):
        data = {}
    data[slug] = time.time()
    data["_last_source"] = slug
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def activate_app(app_name: str) -> None:
    """Bring app to front via AppleScript."""
    esc = app_name.replace("\\", "\\\\").replace('"', '\\"')
    subprocess.run(
        ["osascript", "-e", f'tell application "{esc}" to activate'],
        capture_output=True,
        text=True,
        check=False,
    )


def request_focus(slug: str, cfg: dict) -> bool:
    """Full pipeline: check lab, resolve, cooldown, activate. Returns True on success."""
    lab_focus = cfg.get("lab_focus", {})
    if not lab_focus.get("enabled", True):
        print(f"jarvis_focus: feature disabled; ignoring request for '{slug}'", flush=True)
        return False

    if not lab_active(cfg):
        print(f"jarvis_focus: lab not active — skipping focus request for '{slug}'", flush=True)
        return False

    app_name = resolve_app(slug, cfg)
    if app_name is None:
        default = str(lab_focus.get("default_source", "terminal"))
        print(
            f"jarvis_focus: unknown source '{slug}', falling back to default_source '{default}'",
            flush=True,
        )
        app_name = resolve_app(default, cfg)
        if app_name is None:
            print(
                f"jarvis_focus: default_source '{default}' also unresolvable — aborting",
                flush=True,
            )
            return False
        slug = default

    if within_cooldown(slug, cfg):
        print(f"jarvis_focus: cooldown active for '{slug}' — skipping", flush=True)
        return False

    activate_app(app_name)
    record_fire(slug, cfg)
    print(f"jarvis_focus: activated '{app_name}' for source '{slug}'", flush=True)
    return True
