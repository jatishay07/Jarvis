# Jarvis

macOS “Iron Man” routine: **double-clap** → welcome (voice, Focus, lab wallpaper, Kiro, Cursor, Terminal with `codex` / `claude`, Spotify **~10 s** stinger). While a **lab session** is active, say a configured phrase (e.g. “stand down jarvis”) to **stand down**—save/quit apps, restore wallpaper and Focus, pause Spotify.

## Requirements

- macOS with **Microphone** permission for the Python you use
- **Python 3.10+** recommended
- **Spotify** desktop app (for the stinger)
- **Shortcuts** app (for Focus on/off)
- Optional: **Kiro**, **Cursor**, `codex` and `claude` on your `PATH` in Terminal

## Setup

### 1. Config

```bash
cp config/jarvis.example.json config/jarvis.json
```

Edit `config/jarvis.json`:

- **`holographic_wallpaper`**: when `"enabled": true`, **welcome** and **stand-down** lines are shown as a **typewriter-style** holographic wallpaper in sync with **Samantha** (duration measured with `say` + `afinfo`), then the text is replaced by a **plain black** desktop for the rest of the lab session (welcome) or until your normal wallpaper is **restored** (stand-down). Options: `typing_show_cursor`, `typing_cursor_char`, `pause_after_typing_seconds`. Set `"enabled": false` to use a static `wallpaper_lab_image` and plain `say` instead.
- **`stand_down_quit_spotify`**: when `true` (default), **Spotify** is **quit** on stand-down (after pause), along with `stand_down_apps_quit`.
- **`wallpaper_lab_image`**: required only when holographic mode is **disabled**—absolute path to your lab image
- **`holographic_wallpaper.font_scale` / `glow_blur`**: tweak size and glow strength; `width` / `height` default to your main screen size (`null` = auto)
- **`welcome_message`** / **`stand_down_ack_message`**: these strings are what you **hear** and what is **drawn** on the holographic wallpaper
- **`shortcut_focus_on` / `shortcut_focus_off`**: names of two Shortcuts (see below)
- **`clap.*`**: tune `peak_threshold` / gaps if claps are missed or false-trigger
- **`stand_down_phrases`**: lowercase-ish phrases; ASR is fuzzy (e.g. `stand down jarvis`, `house party protocol`)

### 2. Shortcuts (Focus)

Create two shortcuts in the **Shortcuts** app:

1. **Jarvis Lab On** — add action **Set Focus** → your Work / custom “Lab” focus (and allowed people/apps as you like).
2. **Jarvis Lab Off** — **Set Focus** → Off or **Personal**.

Names must match `shortcut_focus_on` and `shortcut_focus_off` in JSON.

Test from Terminal:

```bash
shortcuts run "Jarvis Lab On"
shortcuts run "Jarvis Lab Off"
```

### 3. Python dependencies

From the repo root (virtualenv recommended):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The first lab session will download the **Whisper** model (`tiny.en` by default); keep the machine online once for that.

### 4. Permissions

- **System Settings → Privacy & Security → Microphone**: enable for **Terminal** (or **iTerm**) while testing, and for the **Python** binary used in LaunchAgent (often `/usr/bin/python3` or your venv `python`).
- **Accessibility** is **not** required for the default scripts (AppleScript targets standard apps). If you add UI automation later, you may need to allow it.

### 5. Manual test (no LaunchAgent)

```bash
export JARVIS_CONFIG="$PWD/config/jarvis.json"
./scripts/jarvis_welcome.sh    # welcome once
./scripts/jarvis_stand_down.sh # restore
python3 scripts/double_clap_listener.py
```

**Auto-restart while tuning:** if you edit `config/jarvis.json` or any `scripts/*.py`, run the listener with **`--watch`** (or **`-w`**) so it restarts by itself and picks up changes:

```bash
export JARVIS_CONFIG="$PWD/config/jarvis.json"
python3 scripts/double_clap_listener.py --watch
```

`Ctrl+C` stops the watcher and the listener.

Double-clap near the mic → welcome. Speak your stand-down phrase → stand down.

If you use a **venv**, run the listener with that interpreter instead of `/usr/bin/python3`, and point LaunchAgent at the same path.

### 6. Always-on listener (login + background)

So double-clap works **without keeping Terminal open**, install the LaunchAgent once from the repo root:

```bash
cd /path/to/Jarvis
./scripts/install_launch_agent.sh
```

This uses **`.venv/bin/python3`** if it exists (recommended); otherwise your `python3` from `PATH`. It sets **RunAtLoad** and **KeepAlive** so the listener starts at login and restarts if it crashes.

**Before installing:** quit any **manual** `double_clap_listener.py` you have running in Terminal (only one process should use the mic).

**Microphone (required):** **System Settings → Privacy & Security → Microphone** → enable for the Python shown at the end of the install script (often `.venv/bin/python3` inside your Jarvis folder). If macOS only lists “Python”, allow it and retry.

**Logs:** `~/.jarvis/listener.log` and `~/.jarvis/listener.err.log`

**Remove:**

```bash
./scripts/uninstall_launch_agent.sh
```

Manual plist editing is still possible via [launchd/com.jarvis.claplistener.plist.example](launchd/com.jarvis.claplistener.plist.example) if you prefer.

## Kiro + Codex + Claude

There is **no stable public API** assumed for driving Kiro’s internal terminal from shell. Default behavior:

- Opens **Kiro** and **Cursor** via `open -a`.
- Opens **Terminal** (name from `terminal_app`) and runs **`codex`** then **`claude`** in separate tabs.

To try Kiro’s terminal only: set `"terminal_open_codex_claude": false` and use Kiro’s own automation or run the CLIs manually once.

## State files

Stored under `~/.jarvis/` (or `state_dir` in config):

- `lab_session.json` — lab session active flag and start time
- `wallpaper_restore.json` — previous desktop picture paths for restore

## Troubleshooting

- **Double-clap does nothing**: If a **lab session** is still active from last time, the listener only listens for the **stand-down phrase**, not claps. Run `./scripts/jarvis_stand_down.sh` or delete `~/.jarvis/lab_session.json`. The listener prints a warning on startup if this is the case.
- **Background listener (LaunchAgent) never starts Jarvis**: The listener now runs **welcome** with the **same Python** as itself (your `.venv`), so Pillow/Shortcuts still work. If it used to fail silently, reinstall: `./scripts/install_launch_agent.sh` then `tail -f ~/.jarvis/listener.err.log` while clapping — you should see `Double-clap detected` or a **Welcome script failed** line with the real error.
- **Calibration**: On startup the listener measures **~1.2s** of background noise (`calibrate_seconds` in JSON; set to **0** to skip). Stay quiet during that window. Then clap sharply twice with a short pause between.
- **`macOS 15 (1507) or later required` / Welcome script failed**: Was usually **tkinter** (removed) plus **Pillow 12+** on slightly older macOS builds. Run `pip install 'Pillow>=10,<12'` in `.venv`, pull latest Jarvis scripts, reinstall the LaunchAgent.
- **Silent mic / AirPods**: Background listeners often get **zeros** from Bluetooth. In **System Settings → Sound → Input** choose **MacBook Microphone**, then run `python3 scripts/list_audio_devices.py`, put that device’s **index** (or a unique **name substring**) in **`clap.input_device`** in `jarvis.json`, and restart the listener.
- **Claps not detected**: set `"clap.debug": true` in `jarvis.json` and watch `peak=` lines while clapping — then set `peak_threshold` **just below** the peaks you see when you clap (typical range **0.08–0.2** on laptop mics). Increase `max_clap_gap_ms` if your second clap is slow (up to **1200**). Allow a brief quiet moment between the two claps.
- **False claps**: raise `peak_threshold` or shorten `max_clap_gap_ms`.
- **Phrase / stand-down never fires**: After welcome, logs should show `Heard: '…'` as you speak. Set `"phrase.debug": true` to see skipped chunks. Defaults now use **`vad_filter: false`** (VAD often dropped speech), **longer chunks + overlap** so phrases are not split, **lower `min_rms`**, and **fuzzy** matching for small Whisper mistakes. Tune `phrase.fuzzy_ratio` (lower = more lenient). If stand-down runs but nothing happens, check **`Stand-down script failed`** in `listener.err.log`.
- **Wallpaper**: multi-Space behavior varies by macOS version; we set **every desktop** exposed to AppleScript. If one screen does not restore, re-save `wallpaper_restore.json` by running welcome once with a known-good wallpaper.

## Privacy

Audio is processed **locally** (clap energy + Whisper). No cloud STT is used by this repo’s scripts.
