#!/usr/bin/env python3
"""Concise read-only diagnostics for a local Jarvis installation."""
from __future__ import annotations

import hashlib
import json
import os
import plistlib
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CheckResult:
    status: str
    message: str
    fix: str | None = None


class DoctorReport:
    def __init__(self) -> None:
        self.sections: list[tuple[str, list[CheckResult]]] = []
        self._current: list[CheckResult] | None = None
        self.failures = 0
        self.warnings = 0

    def section(self, title: str) -> None:
        bucket: list[CheckResult] = []
        self.sections.append((title, bucket))
        self._current = bucket

    def add(self, status: str, message: str, fix: str | None = None) -> None:
        if self._current is None:
            self.section("Checks")
        assert self._current is not None
        self._current.append(CheckResult(status=status, message=message, fix=fix))
        if status == "FAIL":
            self.failures += 1
        elif status == "WARN":
            self.warnings += 1

    def print(self, *, repo_root: Path, cfg_path: Path, runtime_python: Path) -> None:
        print("Jarvis doctor")
        print(f"Repo: {repo_root}")
        print(f"Config target: {cfg_path}")
        print(f"Runtime python: {runtime_python}")
        for title, checks in self.sections:
            print(f"\n{title}")
            for check in checks:
                print(f"  {check.status:<4} {check.message}")
                if check.fix:
                    print(f"       Fix: {check.fix}")
        print(f"\nSummary: {self.failures} fail, {self.warnings} warning(s)")


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _default_cfg_path(repo_root: Path) -> Path:
    env = os.environ.get("JARVIS_CONFIG")
    if env:
        return Path(env).expanduser().resolve()
    return (repo_root / "config" / "jarvis.json").resolve()


def _cfg_path_from_argv(argv: list[str], repo_root: Path) -> Path:
    if len(argv) > 1 and not str(argv[1]).startswith("-"):
        return Path(argv[1]).expanduser().resolve()
    return _default_cfg_path(repo_root)


def _state_dir_from_cfg(cfg: dict | None) -> Path:
    if cfg is None:
        return Path("~/.jarvis").expanduser().resolve()
    return Path(os.path.expanduser(str(cfg.get("state_dir", "~/.jarvis")))).resolve()


def _preferred_runtime_python(repo_root: Path) -> Path:
    venv_python = repo_root / ".venv" / "bin" / "python3"
    if venv_python.is_file() and os.access(venv_python, os.X_OK):
        return venv_python.resolve()
    current = Path(sys.executable).resolve()
    if current.is_file() and os.access(current, os.X_OK):
        return current
    found = shutil.which("python3")
    if found:
        return Path(found).resolve()
    return current


def _paths_equivalent(a: Path | None, b: Path | None) -> bool:
    if a is None or b is None:
        return False
    try:
        return os.path.samefile(a, b)
    except OSError:
        return a.expanduser().resolve() == b.expanduser().resolve()


def _run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, check=False)


def _python_check(python: Path, code: str) -> tuple[bool, str]:
    result = _run_command([str(python), "-c", code])
    output = (result.stderr or result.stdout).strip()
    return result.returncode == 0, output


def _file_hash(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_fingerprint(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    normalized = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _pid_state(pid_path: Path) -> tuple[str, int | None]:
    if not pid_path.is_file():
        return "missing", None
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return "invalid", None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return "stale", pid
    except PermissionError:
        return "alive", pid
    return "alive", pid


def _load_plist(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        with path.open("rb") as fh:
            data = plistlib.load(fh)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _launchctl_loaded(label: str) -> tuple[bool | None, str | None]:
    launchctl = shutil.which("launchctl")
    if not launchctl:
        return None, "launchctl not found"
    target = f"gui/{os.getuid()}/{label}"
    result = _run_command([launchctl, "print", target])
    output = (result.stderr or result.stdout).strip()
    if result.returncode == 0:
        return True, None
    lowered = output.lower()
    if "could not find service" in lowered or "service is disabled" in lowered:
        return False, None
    return False, output or "launchctl print failed"


def _fmt_rel(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root))
    except ValueError:
        return str(path)


def main() -> int:
    repo_root = _repo_root()
    cfg_path = _cfg_path_from_argv(sys.argv, repo_root)
    runtime_python = _preferred_runtime_python(repo_root)
    report = DoctorReport()

    cfg: dict | None = None
    state_dir = Path("~/.jarvis").expanduser().resolve()

    report.section("Config")
    if cfg_path.is_file():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            report.add("OK", f"config loaded: {cfg_path}")
        except json.JSONDecodeError as exc:
            report.add(
                "FAIL",
                f"config is not valid JSON: {cfg_path} ({exc})",
                "Fix the JSON syntax or restore from config/jarvis.example.json.",
            )
        except OSError as exc:
            report.add(
                "FAIL",
                f"config is unreadable: {cfg_path} ({exc})",
                "Check file permissions and the JARVIS_CONFIG path.",
            )
    else:
        report.add(
            "FAIL",
            f"config missing: {cfg_path}",
            "Copy config/jarvis.example.json to config/jarvis.json or point JARVIS_CONFIG at a valid file.",
        )

    if cfg is not None:
        state_dir = _state_dir_from_cfg(cfg)
        if state_dir.exists():
            report.add("OK", f"state_dir resolves: {state_dir}")
        else:
            report.add("OK", f"state_dir configured but not created yet: {state_dir}")

    report.section("Runtime")
    current_python = Path(sys.executable).resolve()
    report.add("OK", f"current interpreter: {current_python}")
    report.add("OK", f"preferred repo runtime: {runtime_python}")
    if current_python != runtime_python:
        report.add(
            "WARN",
            "doctor is not running under the repo-preferred Python runtime",
            f"Use ./scripts/jarvis_doctor.sh to run with {runtime_python}.",
        )

    venv_python = repo_root / ".venv" / "bin" / "python3"
    if venv_python.is_file() and os.access(venv_python, os.X_OK):
        if _paths_equivalent(venv_python, runtime_python):
            report.add("OK", f"repo venv selected: {venv_python}")
        else:
            report.add(
                "WARN",
                f"repo venv exists but is not the selected runtime: {venv_python}",
                f"Use ./scripts/jarvis_doctor.sh or reinstall the relevant LaunchAgent to prefer {venv_python}.",
            )
    else:
        report.add(
            "WARN",
            "repo venv missing; Jarvis will fall back to the active python3 on PATH",
            f"Create one with: cd {repo_root} && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt",
        )

    import_checks = [
        ("numpy", "import numpy"),
        ("sounddevice", "import sounddevice"),
        ("faster_whisper", "import faster_whisper"),
    ]
    for label, code in import_checks:
        ok, output = _python_check(runtime_python, code)
        if ok:
            report.add("OK", f"{label} import works in runtime python")
        else:
            pip_hint = f"{runtime_python} -m pip install -r {repo_root / 'requirements.txt'}"
            report.add(
                "FAIL",
                f"{label} import failed in runtime python",
                f"Run {pip_hint}. Details: {output or 'no stderr'}",
            )

    if sys.platform == "darwin":
        ok, output = _python_check(runtime_python, "import objc; from Cocoa import NSApplication")
        if ok:
            report.add("OK", "PyObjC/AppKit import works in runtime python")
        else:
            report.add(
                "WARN",
                "PyObjC/AppKit import failed in runtime python",
                f"AppKit HUD needs PyObjC. Install with: {runtime_python} -m pip install pyobjc-framework-Cocoa. Details: {output or 'no stderr'}",
            )

    report.section("State")
    session_path = state_dir / "lab_session.json"
    restore_path = state_dir / "wallpaper_restore.json"
    dictation_path = state_dir / "dictation_text.txt"
    welcome_pid_path = state_dir / "welcome.pid"

    active_session = False
    if session_path.is_file():
        try:
            session = json.loads(session_path.read_text(encoding="utf-8"))
            active_session = bool(session.get("active"))
            started = session.get("started")
            if active_session:
                started_text = f", started={started}" if started is not None else ""
                report.add(
                    "WARN",
                    f"lab session marked active: {session_path}{started_text}",
                    f"If stale, run {repo_root / 'scripts' / 'jarvis_stand_down.sh'} or remove {session_path}.",
                )
            else:
                report.add("OK", f"lab_session.json present but inactive: {session_path}")
        except (OSError, json.JSONDecodeError) as exc:
            report.add(
                "WARN",
                f"lab_session.json is unreadable: {session_path} ({exc})",
                f"If stale, remove {session_path}.",
            )
    else:
        report.add("OK", f"lab session file absent: {session_path}")

    if restore_path.is_file():
        report.add("OK", f"wallpaper restore snapshot present: {restore_path}")
    elif active_session:
        report.add(
            "WARN",
            f"active lab session but wallpaper_restore.json is missing: {restore_path}",
            "Stand down may not restore the previous wallpaper correctly.",
        )
    else:
        report.add("OK", f"wallpaper restore snapshot absent: {restore_path}")

    pid_state, pid = _pid_state(welcome_pid_path)
    if pid_state == "missing":
        report.add("OK", f"welcome.pid absent: {welcome_pid_path}")
    elif pid_state == "alive":
        report.add("OK", f"welcome.pid refers to a running process: pid={pid}")
    elif pid_state == "stale":
        report.add(
            "WARN",
            f"stale welcome.pid: pid={pid}",
            f"If no welcome routine is actually running, remove {welcome_pid_path}.",
        )
    else:
        report.add(
            "WARN",
            f"welcome.pid is invalid: {welcome_pid_path}",
            f"If stale, remove {welcome_pid_path}.",
        )

    if dictation_path.is_file():
        if active_session:
            report.add("OK", f"dictation text present during active lab session: {dictation_path}")
        else:
            report.add(
                "WARN",
                f"dictation text is present while no active lab session is recorded: {dictation_path}",
                f"If stale, remove {dictation_path} or rerun stand down.",
            )
    else:
        report.add("OK", f"dictation text absent: {dictation_path}")

    report.section("LaunchAgents")
    listener_label = "com.jarvis.claplistener"
    hud_label = "com.jarvis.hud"
    listener_plist = Path.home() / "Library" / "LaunchAgents" / f"{listener_label}.plist"
    hud_plist = Path.home() / "Library" / "LaunchAgents" / f"{hud_label}.plist"

    listener_loaded, listener_detail = _launchctl_loaded(listener_label)
    listener_plist_data = _load_plist(listener_plist)
    if listener_plist_data is None:
        report.add("OK", f"listener LaunchAgent not installed: {listener_plist}")
    else:
        report.add("OK", f"listener LaunchAgent plist present: {listener_plist}")
        if listener_loaded is True:
            report.add("OK", f"listener LaunchAgent loaded: {listener_label}")
        elif listener_loaded is False:
            report.add(
                "WARN",
                f"listener LaunchAgent not loaded: {listener_label}",
                f"Reinstall with {repo_root / 'scripts' / 'install_launch_agent.sh'}.",
            )
        else:
            report.add("WARN", "listener LaunchAgent status unavailable", listener_detail)

        prog = list(listener_plist_data.get("ProgramArguments") or [])
        env = dict(listener_plist_data.get("EnvironmentVariables") or {})
        wd = listener_plist_data.get("WorkingDirectory")
        expected_listener = (repo_root / "scripts" / "double_clap_listener.py").resolve()
        expected_cfg = (repo_root / "config" / "jarvis.json").resolve()
        if len(prog) >= 2:
            actual_listener = Path(str(prog[1])).expanduser().resolve()
            if _paths_equivalent(actual_listener, expected_listener):
                report.add("OK", "listener agent points at this repo listener script")
            else:
                report.add(
                    "WARN",
                    f"listener agent points at a different script: {actual_listener}",
                    f"Reinstall with {repo_root / 'scripts' / 'install_launch_agent.sh'}.",
                )
        if len(prog) >= 3:
            actual_cfg = Path(str(prog[2])).expanduser().resolve()
        elif env.get("JARVIS_CONFIG"):
            actual_cfg = Path(str(env["JARVIS_CONFIG"])).expanduser().resolve()
        else:
            actual_cfg = None
        if actual_cfg is not None:
            if _paths_equivalent(actual_cfg, expected_cfg):
                report.add("OK", "listener agent config path matches this repo")
            else:
                report.add(
                    "WARN",
                    f"listener agent config differs from this repo default: {actual_cfg}",
                    f"Reinstall with {repo_root / 'scripts' / 'install_launch_agent.sh'} if this is unintended.",
                )
        if wd:
            actual_wd = Path(str(wd)).expanduser().resolve()
            if not _paths_equivalent(actual_wd, repo_root):
                report.add(
                    "WARN",
                    f"listener agent working directory differs from this repo: {actual_wd}",
                    f"Reinstall with {repo_root / 'scripts' / 'install_launch_agent.sh'}.",
                )

    hud_loaded, hud_detail = _launchctl_loaded(hud_label)
    hud_plist_data = _load_plist(hud_plist)
    hud_app = Path.home() / "Applications" / "Jarvis HUD.app"
    launcher = hud_app / "Contents" / "MacOS" / "jarvis-hud-launcher"
    if hud_plist_data is None and not hud_app.exists():
        report.add("OK", f"HUD login app not installed: {hud_app}")
    else:
        if hud_app.exists():
            report.add("OK", f"HUD app present: {hud_app}")
        else:
            report.add(
                "WARN",
                f"HUD LaunchAgent artifacts exist but app is missing: {hud_app}",
                f"Reinstall with {repo_root / 'scripts' / 'install_hud_login.sh'}.",
            )
        if hud_plist_data is None:
            report.add(
                "WARN",
                f"HUD LaunchAgent plist missing: {hud_plist}",
                f"Reinstall with {repo_root / 'scripts' / 'install_hud_login.sh'}.",
            )
        else:
            report.add("OK", f"HUD LaunchAgent plist present: {hud_plist}")
            if hud_loaded is True:
                report.add("OK", f"HUD LaunchAgent loaded: {hud_label}")
            elif hud_loaded is False:
                report.add(
                    "WARN",
                    f"HUD LaunchAgent not loaded: {hud_label}",
                    f"Reinstall with {repo_root / 'scripts' / 'install_hud_login.sh'}.",
                )
            else:
                report.add("WARN", "HUD LaunchAgent status unavailable", hud_detail)
            prog = list(hud_plist_data.get("ProgramArguments") or [])
            if prog:
                actual_launcher = Path(str(prog[0])).expanduser().resolve()
                if _paths_equivalent(actual_launcher, launcher):
                    report.add("OK", "HUD LaunchAgent points at the expected launcher")
                else:
                    report.add(
                        "WARN",
                        f"HUD LaunchAgent points at a different launcher: {actual_launcher}",
                        f"Reinstall with {repo_root / 'scripts' / 'install_hud_login.sh'}.",
                    )

    report.section("HUD Runtime")
    hud_state_dir = Path.home() / ".jarvis"
    repo_path_file = hud_state_dir / "repository_path"
    hud_config_file = hud_state_dir / "hud_config.json"
    hud_runtime_dir = hud_state_dir / "hud_runtime"
    hud_python_file = hud_state_dir / "hud_python_path"

    hud_install_markers = any(
        path.exists()
        for path in (repo_path_file, hud_config_file, hud_runtime_dir, hud_python_file, hud_app, hud_plist)
    )
    if not hud_install_markers:
        report.add("OK", "HUD runtime snapshot not installed (expected if you only launch HUD manually)")
    else:
        if repo_path_file.is_file():
            try:
                recorded_repo = Path(repo_path_file.read_text(encoding="utf-8").strip()).expanduser().resolve()
                if _paths_equivalent(recorded_repo, repo_root):
                    report.add("OK", f"HUD repository_path matches this repo: {recorded_repo}")
                else:
                    report.add(
                        "WARN",
                        f"HUD repository_path points elsewhere: {recorded_repo}",
                        f"Refresh with {repo_root / 'scripts' / 'install_hud_login.sh'}.",
                    )
            except OSError as exc:
                report.add(
                    "WARN",
                    f"HUD repository_path unreadable: {repo_path_file} ({exc})",
                    f"Refresh with {repo_root / 'scripts' / 'install_hud_login.sh'}.",
                )
        else:
            report.add(
                "WARN",
                f"HUD repository_path missing: {repo_path_file}",
                f"Refresh with {repo_root / 'scripts' / 'install_hud_login.sh'}.",
            )

        repo_cfg_fingerprint = _json_fingerprint(cfg_path)
        hud_cfg_fingerprint = _json_fingerprint(hud_config_file)
        if hud_config_file.is_file():
            if repo_cfg_fingerprint is not None and hud_cfg_fingerprint is not None:
                if repo_cfg_fingerprint == hud_cfg_fingerprint:
                    report.add("OK", "HUD config snapshot matches the active Jarvis config")
                else:
                    report.add(
                        "WARN",
                        f"HUD config snapshot differs from active config: {hud_config_file}",
                        f"Refresh with {repo_root / 'scripts' / 'install_hud_login.sh'}.",
                    )
            else:
                report.add(
                    "WARN",
                    f"HUD config snapshot exists but could not be compared safely: {hud_config_file}",
                    f"Refresh with {repo_root / 'scripts' / 'install_hud_login.sh'} if you suspect drift.",
                )
        else:
            report.add(
                "WARN",
                f"HUD config snapshot missing: {hud_config_file}",
                f"Refresh with {repo_root / 'scripts' / 'install_hud_login.sh'}.",
            )

        expected_runtime_files = [
            repo_root / "scripts" / "jarvis_hud_appkit.py",
            repo_root / "scripts" / "jarvis_hud_slider.py",
            repo_root / "scripts" / "jarvis_hud_lib.py",
        ]
        drifted: list[str] = []
        missing: list[str] = []
        for src in expected_runtime_files:
            dst = hud_runtime_dir / src.name
            src_hash = _file_hash(src)
            dst_hash = _file_hash(dst)
            if dst_hash is None:
                missing.append(src.name)
            elif src_hash != dst_hash:
                drifted.append(src.name)
        if not hud_runtime_dir.exists():
            report.add(
                "WARN",
                f"HUD runtime directory missing: {hud_runtime_dir}",
                f"Refresh with {repo_root / 'scripts' / 'install_hud_login.sh'}.",
            )
        elif missing:
            report.add(
                "WARN",
                f"HUD runtime is missing copied files: {', '.join(sorted(missing))}",
                f"Refresh with {repo_root / 'scripts' / 'install_hud_login.sh'}.",
            )
        elif drifted:
            report.add(
                "WARN",
                f"HUD runtime files differ from the repo copies: {', '.join(sorted(drifted))}",
                f"Refresh with {repo_root / 'scripts' / 'install_hud_login.sh'}.",
            )
        else:
            report.add("OK", f"HUD runtime copies match this repo: {_fmt_rel(hud_runtime_dir, repo_root)}")

        if hud_python_file.is_file():
            try:
                hud_python = Path(hud_python_file.read_text(encoding="utf-8").strip()).expanduser().resolve()
            except OSError as exc:
                report.add(
                    "WARN",
                    f"HUD python path unreadable: {hud_python_file} ({exc})",
                    f"Refresh with {repo_root / 'scripts' / 'install_hud_login.sh'}.",
                )
            else:
                if hud_python.is_file() and os.access(hud_python, os.X_OK):
                    report.add("OK", f"HUD python path recorded: {hud_python}")
                else:
                    report.add(
                        "WARN",
                        f"HUD python path is not executable: {hud_python}",
                        f"Refresh with {repo_root / 'scripts' / 'install_hud_login.sh'}.",
                    )
        else:
            report.add(
                "WARN",
                f"HUD python path file missing: {hud_python_file}",
                f"Refresh with {repo_root / 'scripts' / 'install_hud_login.sh'}.",
            )

    report.print(repo_root=repo_root, cfg_path=cfg_path, runtime_python=runtime_python)
    return 1 if report.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
