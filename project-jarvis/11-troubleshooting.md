# 11 — Troubleshooting

[← Back to index](README.md)

Organized as **symptom → likely cause → what to do**. Many items are expanded from the root [README.md](../README.md).

## Double-clap does nothing

| Cause | What to do |
|-------|------------|
| **Lab session still active** | Listener ignores claps when `lab_session.json` says active. Run `./scripts/jarvis_stand_down.sh` or remove the stale file. Logs: `Double-clap ignored — lab session already ACTIVE` (about every 25s max). |
| **Listener not running** | Check LaunchAgent: `launchctl list \| grep jarvis`. Re-run `install_launch_agent.sh`; tail `~/.jarvis/listener.err.log`. |
| **Threshold / room noise** | Set `"clap.debug": true`, watch `peak=` lines while clapping; set `peak_threshold` just below your clap peaks (often ~0.08–0.2). |
| **Bluetooth / silent input** | Background listeners may get zeros from AirPods. System Settings → Sound → Input → built-in mic; set `clap.input_device` from `list_audio_devices.py`. |

## Welcome or stand-down script fails from LaunchAgent

| Cause | What to do |
|-------|------------|
| **Wrong Python** | Install script prefers `.venv/bin/python3` so Pillow/Shortcuts match manual runs. Reinstall LaunchAgent after fixing venv. |
| **Missing module** | `pip install -r requirements.txt` inside the venv used by the plist. |

## Stand-down phrase never recognized

| Cause | What to do |
|-------|------------|
| **Whisper chunks** | Enable `"phrase.debug": true`; defaults favor longer chunks + overlap and `vad_filter: false`. |
| **Too strict matching** | Lower `phrase.fuzzy_ratio` slightly. |
| **Low audio energy** | Lower `phrase.min_rms` if speech is quiet. |

## HUD does not appear

| Cause | What to do |
|-------|------------|
| **Borderless window / focus** | `JARVIS_HUD_DEBUG_VISIBILITY_MODE=always_visible ./scripts/jarvis_hud_slider.sh` then `titled_debug`. See [08-hud.md](08-hud.md). |
| **No PyObjC** | `pip install pyobjc-framework-Cocoa` in `.venv`. |
| **Tk crash on Homebrew Python** | Prefer AppKit; or use `./scripts/jarvis_hud_dialog.sh` (no Tk). |
| **Wrong interpreter** | Set `PYTHON_JARVIS_HUD=/path/to/python3` or ensure `.venv` has Cocoa. |

## Tk / “Python quit unexpectedly”

| Cause | What to do |
|-------|------------|
| **Homebrew Python + bad Tcl/Tk** | Launcher prefers AppKit on macOS; install PyObjC. Force dialog HUD if needed. |

## HUD at login broken after moving repo

| Cause | What to do |
|-------|------------|
| **Stale `repository_path` or runtime** | Re-run `install_hud_login.sh` from the new clone path. |

## `macOS 15 (1507) or later` / Pillow errors

| Cause | What to do |
|-------|------------|
| **Pillow 12+ on older OS build** | `pip install 'Pillow>=10,<12'` in `.venv`; pull latest scripts (per README). |

## Wallpaper restore incomplete on one screen

| Cause | What to do |
|-------|------------|
| **Multi-Space / multi-display quirks** | AppleScript sets every desktop it can see; run welcome once with a known-good wallpaper to refresh `wallpaper_restore.json`. |

## HUD dictation strip stays empty

| Cause | What to do |
|-------|------------|
| **Welcome has not run** | `dictation_text.txt` is written during **welcome**. Open the HUD first, then trigger welcome (or run welcome before relying on the strip). |
| **Stand down removed the file** | Expected — stand-down deletes `dictation_text.txt`. Run welcome again to repopulate. |
| **Overlays disabled** | Set `hud_overlay.dictation.enabled` / `hud_overlay.enabled` in JSON, or you are on Tk/dialog HUD (no overlay). |

## Privacy reminder

All speech processing in these scripts is **local** (Whisper on CPU in-process). No cloud STT is required by the repo.

## Related chapters

- [04-configuration.md](04-configuration.md) — tuning keys
- [05-listener-and-speech.md](05-listener-and-speech.md) — listener details
- [08-hud.md](08-hud.md) — HUD diagnostics
