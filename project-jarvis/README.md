# Project Jarvis — documentation for humans

This folder is a **book-style guide** to the [Jarvis](../README.md) macOS automation project. It is written for people who want to understand how everything fits together, not as a dump of keywords for language models.

## Sixty-second mental model

1. **Welcome** puts you in a “lab session”: voice + wallpaper, optional Focus mode, your dev apps, maybe a Spotify sting.
2. **Stand down** ends the session: goodbye line, restore wallpaper and Focus, quit configured apps.
3. You can trigger welcome with a **double clap**, a **wake phrase** (optional), or the **HUD** (slider or dialog) when the mic is awkward.
4. While a lab session is active, the background listener listens for **stand-down phrases** (local speech recognition), not new claps.
5. Everything is driven by **`config/jarvis.json`** and optional state files under **`~/.jarvis/`**.
6. With the **AppKit HUD** open, optional **`hud_overlay`** layers (grid background, arc reactor, dictation strip) can sit above the desktop; the dictation view reads **`dictation_text.txt`** in your state directory, which **welcome** updates when it runs.

## Table of contents

| # | Document | What you will learn |
|---|----------|---------------------|
| 1 | [01-overview.md](01-overview.md) | What Jarvis is, privacy, prerequisites, glossary |
| 2 | [02-architecture.md](02-architecture.md) | Components, state on disk, diagrams |
| 3 | [03-user-journeys.md](03-user-journeys.md) | Setup, daily use, HUD-only, debugging paths |
| 4 | [04-configuration.md](04-configuration.md) | Config file layout, env vars, grouped key reference |
| 5 | [05-listener-and-speech.md](05-listener-and-speech.md) | Double-clap listener, Whisper, wake phrases |
| 6 | [06-welcome-and-stand-down.md](06-welcome-and-stand-down.md) | Welcome and stand-down scripts, apps, Spotify |
| 7 | [07-wallpaper-and-holographic.md](07-wallpaper-and-holographic.md) | Static vs holographic wallpaper, backup/restore |
| 8 | [08-hud.md](08-hud.md) | AppKit slider, `hud_overlay` chrome, Tk, dialog, login app |
| 9 | [09-installation-and-launchd.md](09-installation-and-launchd.md) | venv, LaunchAgents, logs, HUD install |
| 10 | [10-scripts-inventory.md](10-scripts-inventory.md) | Every script and what it is for |
| 11 | [11-troubleshooting.md](11-troubleshooting.md) | Symptom → cause → fix |

## Where things live in the repo

| Path | Role |
|------|------|
| [`config/jarvis.example.json`](../config/jarvis.example.json) | Template; copy to `config/jarvis.json` |
| [`scripts/`](../scripts/) | Python and shell entry points |
| [`docs/HUD.md`](../docs/HUD.md) | Shorter HUD-focused notes (this pack expands on them) |
| [`launchd/com.jarvis.claplistener.plist.example`](../launchd/com.jarvis.claplistener.plist.example) | Example plist for manual launchd setup |
| [`macos/Jarvis HUD.app/`](../macos/Jarvis%20HUD.app/) | Bundle copied to `~/Applications` by the HUD login installer |

## Further reading (in-repo)

- Root [README.md](../README.md) — quick start and exhaustive config bullet list
- [requirements.txt](../requirements.txt) — Python dependencies

---

*Jarvis — local audio, configurable “lab” routine, optional Iron Man vibes.*
