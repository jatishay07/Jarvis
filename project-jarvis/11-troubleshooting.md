# 11 — Troubleshooting

[← Back to index](README.md)

Organized as **symptom → likely cause → what to do**. Many items are expanded from the root [README.md](../README.md).

**First step for most issues:** run **[`jarvis_doctor.sh`](../scripts/jarvis_doctor.sh)** (implementation: [`jarvis_doctor.py`](../scripts/jarvis_doctor.py)) for a concise read-only report covering config resolution, runtime imports, state files, LaunchAgents, and HUD runtime drift. Full usage and env vars: [09 — Installation and LaunchAgents](09-installation-and-launchd.md#health-check-jarvis_doctor). Glossary entry: [Jarvis doctor](01-overview.md#glossary).

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
| **Dwell mode feels “stuck”** | Default **`reveal_mode`** is **`edge_dwell`**: you must **hold** the cursor in the edge band for **`reveal_dwell_seconds`** (example JSON: **3s**; code default if key omitted: **0.4s**). Switch to **`reveal_mode`: `edge`** for instant reveal, or lower **`reveal_dwell_seconds`**. |
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
| **No active lab session** | AppKit **overlays stay transparent** until **welcome** has finished and written `lab_session.json`. Stand down hides them again. Trigger welcome (HUD, clap, or wake phrase) and wait up to ~0.5s for the overlay poll. |
| **Welcome has not run** | `dictation_text.txt` is written during **welcome**. Without welcome, the file may be missing or stale. |
| **Stand down removed the file** | Expected — stand-down deletes `dictation_text.txt` and ends the lab session, so overlays **fade out**. Run welcome again to repopulate. |
| **Overlays disabled** | Set `hud_overlay.dictation.enabled` / `hud_overlay.enabled` in JSON, or you are on Tk/dialog HUD (no overlay). |

## HUD lab chrome never appears (or vanishes after stand down)

| Cause | What to do |
|-------|------------|
| **Expected after stand down** | Overlays are **tied to lab session** — they hide when `lab_session.json` is cleared. The HUD slider can still work for the next welcome. |
| **Welcome never completed** | Session file is written only **after** welcome finishes. If welcome errors out, overlays may never show. Check Terminal / logs for welcome failures. |
| **`hud_overlay.enabled` false** | Turn on in JSON or copy defaults from `jarvis.example.json`. |
| **Fullscreen app covering desktop** | Overlay layers are **behind normal windows** by design — you only see grid/arc/dictation on **exposed desktop**. Not a bug if a fullscreen window hides them. |

## Privacy reminder

All speech processing in these scripts is **local** (Whisper on CPU in-process). No cloud STT is required by the repo.

## Related chapters

- [09-installation-and-launchd.md](09-installation-and-launchd.md) — **`jarvis_doctor`** runbook
- [04-configuration.md](04-configuration.md) — tuning keys
- [05-listener-and-speech.md](05-listener-and-speech.md) — listener details
- [08-hud.md](08-hud.md) — HUD diagnostics
- [12-backlog.md](12-backlog.md) — future ideas (not commitments)
