#!/usr/bin/env python3
"""Jarvis Projects: GitHub starred repo fetch, voice project selection, editor open."""
from __future__ import annotations

import difflib
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


# ── Helpers ───────────────────────────────────────────────────────────────────

def _state_dir(cfg: dict) -> Path:
    d = Path(os.path.expanduser(cfg.get("state_dir", "~/.jarvis"))).resolve()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _pcfg(cfg: dict) -> dict:
    return cfg.get("projects", {})


def _say(text: str, cfg: dict) -> None:
    voice = cfg.get("say_voice", "")
    cmd = ["say"]
    if voice:
        cmd += ["-v", voice]
    cmd.append(text)
    subprocess.run(cmd, check=False)


# ── GitHub fetch ──────────────────────────────────────────────────────────────

def fetch_starred_repos(cfg: dict) -> list[dict]:
    """Return GitHub starred repos, using a local cache if fresh."""
    pc = _pcfg(cfg)
    state = _state_dir(cfg)
    cache_file = state / "projects_cache.json"
    cache_ttl = float(pc.get("cache_ttl_hours", 6)) * 3600

    # Return cached if still fresh
    if cache_file.is_file():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            if time.time() - float(cached.get("timestamp", 0)) < cache_ttl:
                return cached["repos"]
        except Exception:
            pass

    token_env = pc.get("github_token_env", "GITHUB_TOKEN")
    token = os.environ.get(token_env, "")
    if not token:
        print(f"[jarvis_projects] No token in ${token_env}", file=sys.stderr)
        return []

    all_repos: list[dict] = []
    page = 1
    while True:
        url = f"https://api.github.com/user/starred?per_page=100&page={page}"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "Jarvis/1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
        except Exception as e:
            print(f"[jarvis_projects] GitHub API error: {e}", file=sys.stderr)
            break

        if not isinstance(data, list) or not data:
            break

        for r in data:
            all_repos.append({
                "name": r["name"],
                "full_name": r["full_name"],
                "html_url": r["html_url"],
            })

        if len(data) < 100:
            break
        page += 1

    # Persist cache
    try:
        cache_file.write_text(
            json.dumps({"timestamp": time.time(), "repos": all_repos}, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass

    return all_repos


# ── Voice listener ────────────────────────────────────────────────────────────

def listen_for_project(repos: list[dict], cfg: dict) -> dict | None:
    """Record audio for `listen_seconds`, transcribe, fuzzy-match to a repo."""
    pc = _pcfg(cfg)
    listen_secs = float(pc.get("listen_seconds", 6))
    threshold = float(pc.get("fuzzy_threshold", 0.55))

    try:
        import numpy as np  # noqa: F401 (ensures numpy is importable)
        import sounddevice as sd
        from faster_whisper import WhisperModel
    except ImportError as e:
        print(f"[jarvis_projects] Missing dependency: {e}", file=sys.stderr)
        return None

    phrase_cfg = cfg.get("phrase", {})
    model_name = phrase_cfg.get("whisper_model", "tiny.en")
    compute_type = phrase_cfg.get("compute_type", "int8")
    sample_rate = 16_000

    print(f"[jarvis_projects] Listening for {listen_secs}s …", file=sys.stderr)
    try:
        recording = sd.rec(
            int(listen_secs * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
        )
        sd.wait()
        audio = recording.flatten()
    except Exception as e:
        print(f"[jarvis_projects] Recording error: {e}", file=sys.stderr)
        return None

    try:
        model = WhisperModel(model_name, compute_type=compute_type)
        segments, _ = model.transcribe(audio, beam_size=5, language="en")
        transcript = " ".join(s.text for s in segments).strip().lower()
    except Exception as e:
        print(f"[jarvis_projects] Transcription error: {e}", file=sys.stderr)
        return None

    print(f"[jarvis_projects] Heard: {transcript!r}", file=sys.stderr)
    if not transcript:
        return None

    best_repo: dict | None = None
    best_score = 0.0

    for repo in repos:
        # Normalise repo name: hyphens/underscores → spaces, lowercase
        name_norm = repo["name"].replace("-", " ").replace("_", " ").lower()

        # Full-transcript vs name
        score = difflib.SequenceMatcher(None, transcript, name_norm).ratio()

        # Also compare each spoken word vs name (handles "open jarvis" → "jarvis")
        for word in transcript.split():
            word_score = difflib.SequenceMatcher(None, word, name_norm).ratio()
            score = max(score, word_score)

        if score > best_score:
            best_score = score
            best_repo = repo

    if best_score >= threshold and best_repo is not None:
        print(f"[jarvis_projects] Matched: {best_repo['name']} (score={best_score:.2f})", file=sys.stderr)
        return best_repo

    print(f"[jarvis_projects] No match (best={best_score:.2f})", file=sys.stderr)
    return None


# ── Editor open ───────────────────────────────────────────────────────────────

def open_project(repo: dict, cfg: dict) -> None:
    """Open a project in Cursor (or Kiro), falling back to the GitHub URL."""
    pc = _pcfg(cfg)
    local_paths: dict[str, str] = pc.get("local_paths", {})
    local_path: str | None = local_paths.get(repo["name"])
    editor = pc.get("default_editor", "cursor").lower()
    app = "Cursor" if editor == "cursor" else "Kiro"

    if local_path:
        expanded = os.path.expanduser(local_path)
        print(f"[jarvis_projects] Opening {repo['name']} in {app} at {expanded}", file=sys.stderr)
        subprocess.run(["open", "-a", app, expanded], capture_output=True)
    else:
        print(f"[jarvis_projects] No local path for {repo['name']} — opening GitHub URL", file=sys.stderr)
        subprocess.run(["open", repo["html_url"]], capture_output=True)


# ── Main entry point ──────────────────────────────────────────────────────────

def prompt_for_project(cfg: dict) -> None:
    """Ask the user which project to work on, listen, match, and open it."""
    state = _state_dir(cfg)
    prompt_file = state / "projects_prompt.json"
    active_file = state / "active_project.json"

    # Signal the HUD to show the projects panel
    try:
        prompt_file.write_text(json.dumps({"ts": time.time()}), encoding="utf-8")
    except OSError:
        pass

    # Pre-fetch repos (may be cached — fast path)
    repos = fetch_starred_repos(cfg)

    _say("What would you like to work on today, sir?", cfg)

    if not repos:
        _say("I'm unable to fetch your projects right now, sir.", cfg)
        try:
            prompt_file.unlink(missing_ok=True)
        except OSError:
            pass
        return

    matched = listen_for_project(repos, cfg)

    if matched:
        _say(f"Opening {matched['name']}, sir.", cfg)
        open_project(matched, cfg)
        try:
            active_file.write_text(
                json.dumps({"name": matched["name"], "ts": time.time()}),
                encoding="utf-8",
            )
        except OSError:
            pass
    else:
        _say("I didn't catch that, sir. I'll leave the panel up for you.", cfg)

    # Remove prompt signal; panel stays up as long as active_file exists
    try:
        prompt_file.unlink(missing_ok=True)
    except OSError:
        pass


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _cfg_path = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else Path(os.environ.get("JARVIS_CONFIG", "config/jarvis.json"))
    )
    try:
        _cfg = json.loads(_cfg_path.read_text(encoding="utf-8"))
    except Exception as _e:
        print(f"Cannot load config {_cfg_path}: {_e}", file=sys.stderr)
        sys.exit(1)
    prompt_for_project(_cfg)
