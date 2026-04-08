# 10 — Scripts inventory

[← Back to index](README.md)

Every file under [`scripts/`](../scripts/) in this repository, with a short role. Paths are relative to `scripts/`.

| Script | Role |
|--------|------|
| **`double_clap_listener.py`** | Long-running mic listener: claps, wake phrases, stand-down Whisper; invokes welcome/stand-down wrappers. |
| **`jarvis_welcome.py`** | Welcome routine: wallpaper, voice, Focus, apps, Spotify, session file. |
| **`jarvis_welcome.sh`** | Runs `jarvis_welcome.py` with venv Python when `.venv` exists. |
| **`jarvis_stand_down.py`** | Stand-down routine: interrupt welcome, restore wallpaper, quit apps, Focus off. |
| **`jarvis_stand_down.sh`** | Runs `jarvis_stand_down.py` with venv Python when `.venv` exists. |
| **`jarvis_holographic_wallpaper.py`** | Holographic frames, `say` timing, typing animation. |
| **`wallpaper_util.py`** | AppleScript backup / set / restore desktop pictures. |
| **`jarvis_phrase.py`** | Fuzzy phrase matching for Whisper output (stand-down + wake). |
| **`phrase_listener.py`** | Re-exports `phrase_matches` for tests/imports. |
| **`jarvis_hud_lib.py`** | Repo resolution, HUD singleton lock, spawn welcome/stand-down. |
| **`jarvis_hud_appkit.py`** | Native macOS HUD (hover slider). |
| **`jarvis_hud_slider.py`** | Tk HUD slider fallback. |
| **`jarvis_hud_dialog.py`** | AppleScript list dialog HUD. |
| **`jarvis_hud_slider.sh`** | Picks Python + backend: AppKit → Tk → dialog. |
| **`jarvis_hud_dialog.sh`** | Launches dialog HUD. |
| **`jarvis_hud_restart.sh`** | Kill HUD processes and restart via `jarvis_hud_slider.sh`. |
| **`list_audio_devices.py`** | Lists input devices for `clap.input_device` tuning. |
| **`jarvis_lib.sh`** | Optional shell helpers (`jarvis_root`, `jarvis_config_path`, `jarvis_json_get`); not sourced by other repo scripts but safe to use from custom wrappers. |
| **`install_launch_agent.sh`** | Install `com.jarvis.claplistener` LaunchAgent. |
| **`uninstall_launch_agent.sh`** | Remove clap listener LaunchAgent. |
| **`install_hud_login.sh`** | Install `Jarvis HUD.app`, HUD runtime copies, `com.jarvis.hud` agent. |
| **`install_hud_launch_agent.sh`** | Wrapper that execs `install_hud_login.sh`. |
| **`uninstall_hud_login.sh`** | Remove HUD app + HUD LaunchAgent. |
| **`uninstall_hud_launch_agent.sh`** | Wrapper: `exec`s `uninstall_hud_login.sh` (same removal path). |

## Related chapters

- [06-welcome-and-stand-down.md](06-welcome-and-stand-down.md) — welcome/stand-down flow
- [08-hud.md](08-hud.md) — HUD stack
