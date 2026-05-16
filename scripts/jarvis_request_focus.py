#!/usr/bin/env python3
"""Bring the right macOS app to the front when an AI agent needs the user's attention.

Usage:
  jarvis_request_focus.py [config_path] <source>
  jarvis_request_focus.py [config_path] --watch

Sources: kiro, cursor, codex, terminal — or any slug defined in lab_focus.sources.
--watch: poll state_dir/focus_request.json and activate on each new write.
"""
from __future__ import annotations

import json
import os
import signal
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent


def _load_config(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _resolve_cfg_path(args: list[str]) -> tuple[Path, list[str]]:
    """Return (config_path, remaining_args). Config path from args[0] if it looks like a file."""
    env_cfg = os.environ.get("JARVIS_CONFIG", "")
    default = Path(env_cfg).expanduser().resolve() if env_cfg else _ROOT / "config" / "jarvis.json"
    if args and not args[0].startswith("-") and Path(args[0]).suffix in (".json",):
        return Path(args[0]).expanduser().resolve(), args[1:]
    return default, args


def _watch_loop(cfg: dict, cfg_path: Path) -> None:
    sys.path.insert(0, str(_HERE))
    from jarvis_focus_lib import _state_dir, request_focus  # type: ignore[import-not-found]

    lab_focus = cfg.get("lab_focus", {})
    if not lab_focus.get("watch_file_enabled", True):
        print("jarvis_focus: watch_file_enabled is false — exiting", flush=True)
        return

    watch_path = _state_dir(cfg) / str(lab_focus.get("watch_file", "focus_request.json"))
    poll_secs = float(lab_focus.get("watch_file_poll_seconds", 0.5))
    default_source = str(lab_focus.get("default_source", "terminal"))
    last_mtime: float = 0.0

    print(f"jarvis_focus: watching {watch_path} (poll={poll_secs}s)", flush=True)

    def _handle_sigterm(signum, frame):  # noqa: ANN001
        print("jarvis_focus: watch loop exiting", flush=True)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _handle_sigterm)

    while True:
        try:
            # Re-read config each iteration so live edits take effect
            try:
                cfg = _load_config(cfg_path)
                lab_focus = cfg.get("lab_focus", {})
            except Exception:
                pass

            try:
                mtime = watch_path.stat().st_mtime
            except FileNotFoundError:
                last_mtime = 0.0
                time.sleep(poll_secs)
                continue

            if mtime != last_mtime:
                last_mtime = mtime
                try:
                    data = json.loads(watch_path.read_text(encoding="utf-8"))
                    slug = str(data.get("source", default_source)).lower().strip()
                except (json.JSONDecodeError, OSError):
                    slug = default_source
                try:
                    watch_path.unlink(missing_ok=True)
                except OSError:
                    pass
                last_mtime = 0.0  # reset so re-create fires again
                request_focus(slug, cfg)

        except KeyboardInterrupt:
            print("jarvis_focus: watch loop exiting", flush=True)
            break
        time.sleep(poll_secs)


def main() -> int:
    args = sys.argv[1:]
    cfg_path, args = _resolve_cfg_path(args)

    if not cfg_path.is_file():
        print(f"jarvis_focus: config not found: {cfg_path}", file=sys.stderr)
        return 1

    cfg = _load_config(cfg_path)

    sys.path.insert(0, str(_HERE))
    from jarvis_focus_lib import request_focus  # type: ignore[import-not-found]

    if not args:
        print(__doc__, file=sys.stderr)
        return 1

    if args[0] == "--watch":
        _watch_loop(cfg, cfg_path)
        return 0

    slug = args[0].lower().strip()
    return 0 if request_focus(slug, cfg) or True else 1  # always exit 0 (non-fatal)


if __name__ == "__main__":
    raise SystemExit(main())
