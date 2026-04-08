# 9 — Installation and LaunchAgents

[← Back to index](README.md)

## Python environment

```bash
cd /path/to/Jarvis
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The first **Whisper** model download happens when phrase or wake detection runs — stay online once.

**Pin note:** `Pillow` is capped (`>=10,<12`) in [`requirements.txt`](../requirements.txt) for compatibility on some macOS versions (see root README).

**macOS GUI stack:** [`requirements.txt`](../requirements.txt) also installs **`pyobjc-framework-Cocoa`** and **`pyobjc-framework-Quartz`** when `sys_platform == 'darwin'`, which the AppKit HUD and overlay views need. Linux/other platforms skip those lines.

## Config file

```bash
cp config/jarvis.example.json config/jarvis.json
# edit paths, Shortcut names, phrases
```

## Microphone and Automation

- **Microphone:** System Settings → Privacy & Security → Microphone → allow the **exact Python** you use (e.g. `.venv/bin/python3`).
- **Automation:** May prompt when AppleScript drives Terminal or System Events (Hide Others, hiding app windows).

## Clap listener LaunchAgent

**Install:** [`scripts/install_launch_agent.sh`](../scripts/install_launch_agent.sh)

- Writes `~/Library/LaunchAgents/com.jarvis.claplistener.plist`.
- Uses **`REPO/.venv/bin/python3`** if present, else `python3` from `PATH`.
- Passes **absolute** paths to `double_clap_listener.py` and `config/jarvis.json`.
- Sets **`WorkingDirectory`** to the repo, **`RunAtLoad`**, **`KeepAlive`**, stdout/stderr to `~/.jarvis/listener.log` and `listener.err.log`.

**Remove:** [`scripts/uninstall_launch_agent.sh`](../scripts/uninstall_launch_agent.sh)

**Manual plist:** [`launchd/com.jarvis.claplistener.plist.example`](../launchd/com.jarvis.claplistener.plist.example) for reference if you edit launchd by hand.

**Before installing:** quit any manual `double_clap_listener.py` so only one process captures the mic.

## HUD login (standalone app)

**Install:** [`scripts/install_hud_login.sh`](../scripts/install_hud_login.sh)  
(Backward-compatible wrapper: [`install_hud_launch_agent.sh`](../scripts/install_hud_launch_agent.sh) calls the same script.)

- Copies [`macos/Jarvis HUD.app`](../macos/Jarvis%20HUD.app/) → **`~/Applications/Jarvis HUD.app`**
- Writes **`~/.jarvis/repository_path`** (absolute path to clone)
- Copies **`config/jarvis.json`** → **`~/.jarvis/hud_config.json`**
- Copies HUD Python files to **`~/.jarvis/hud_runtime/`**
- Writes **`~/.jarvis/hud_python_path`** (venv Python if PyObjC works)
- Loads **`com.jarvis.hud`** with **RunAtLoad** + **KeepAlive**
- Logs: **`~/.jarvis/hud.app.log`**, **`~/.jarvis/hud.app.err.log`**

**Remove:** [`scripts/uninstall_hud_login.sh`](../scripts/uninstall_hud_login.sh) — unloads plist, removes app from `~/Applications`. Optional: delete `~/.jarvis/repository_path` if unused.

**Equivalent uninstall:** [`uninstall_hud_launch_agent.sh`](../scripts/uninstall_hud_launch_agent.sh) is a thin wrapper that runs **`uninstall_hud_login.sh`**.

## HUD development restart

[`scripts/jarvis_hud_restart.sh`](../scripts/jarvis_hud_restart.sh) kills running HUD processes and re-runs `jarvis_hud_slider.sh` (defaults to forcing **Tk** backend on Darwin when unset, for developer workflow — read the script if behavior surprises you).

## Log file quick reference

| Log | Source |
|-----|--------|
| `~/.jarvis/listener.log` | Clap listener stdout |
| `~/.jarvis/listener.err.log` | Clap listener stderr |
| `~/.jarvis/hud.app.log` | HUD LaunchAgent stdout |
| `~/.jarvis/hud.app.err.log` | HUD LaunchAgent stderr |

## Related chapters

- [05-listener-and-speech.md](05-listener-and-speech.md) — listener behavior
- [08-hud.md](08-hud.md) — HUD details
