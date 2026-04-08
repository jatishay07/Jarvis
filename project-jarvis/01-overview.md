# 1 — Overview

[← Back to index](README.md)

## What is Jarvis?

**Jarvis** is a macOS automation project that mimics a playful “Iron Man lab” routine:

- **Welcome** — Transition into a focused “lab session”: spoken lines, desktop wallpaper (static image or animated holographic typing), Shortcuts-driven **Focus** mode, optional launches of apps like Kiro and Cursor, and optionally a short **Spotify** preview.
- **Stand down** — Clean exit: acknowledgment line, restore your previous wallpapers, turn Focus off, quit configured applications, pause Spotify.

**In practice:** you double-clap (or say a wake phrase, or use the HUD) to start; you speak a configured phrase to end, or run stand-down manually, or use the HUD again.

## Privacy and trust

- **Microphone audio is processed on your Mac.** Clap detection uses energy and spectral shape; phrases use **faster-whisper** (local model). There is **no cloud speech API** in this repository’s scripts.
- Shortcuts, AppleScript, and `osascript` drive system and app integration; you control which Shortcuts names appear in config.

## What you need

| Requirement | Notes |
|-------------|--------|
| **macOS** | Tested patterns assume Apple’s desktop APIs (AppleScript, Shortcuts). |
| **Python 3.10+** | Recommended; use a venv inside the repo. |
| **Microphone permission** | For the Python binary running the listener (often `.venv/bin/python3`). |
| **`config/jarvis.json`** | Copy from `config/jarvis.example.json` and edit. |
| **Shortcuts app** | Two shortcuts for Focus on/off (names must match config). |
| **Optional** | Spotify desktop app (for stinger), Kiro, Cursor, Terminal + `codex`/`claude` on `PATH` if you enable terminal launch. |

## Glossary

| Term | Meaning |
|------|---------|
| **Lab session** | Logical “session active” state stored in `lab_session.json`. While active, the listener expects **stand-down speech**, not double-claps for welcome. |
| **Welcome** | Script-driven routine that prepares desktop, wallpaper, voice, Focus, apps, Spotify, then writes the lab session file. |
| **Stand down** | Routine that ends the lab, restores wallpaper, clears session state, quits apps, turns Focus off. |
| **HUD** | Manual UI when clapping or speaking is impractical: native **AppKit** slider (preferred), **Tk** fallback, or **AppleScript dialog**. |
| **HUD overlay** | Optional full-screen-style chrome in **`hud_overlay`** (AppKit only): animated background grid, center “arc reactor” graphic, and a **dictation** line that types out text from **`dictation_text.txt`** in `state_dir`. |
| **Holographic wallpaper** | Pillow-generated frames: subtitle-style typing (and optional erase) synced with `say`, instead of a single static lab image. |
| **Wake phrase** | Optional voice trigger that runs **welcome** while not in a lab session (alternative to double-clap). |
| **Stand-down phrase** | Spoken phrase matched fuzzily after Whisper transcription (e.g. “stand down jarvis”). |

## Related chapters

- [02-architecture.md](02-architecture.md) — how pieces connect
- [04-configuration.md](04-configuration.md) — all the knobs in one place
