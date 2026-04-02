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

- **`holographic_wallpaper`**: when `"enabled": true` (default in the example), the “lab” wallpaper is **generated**: black background + blue/cyan **holographic-style text** that matches **`welcome_message`** right before `say`, and (if `stand_down_ack` is true) **`stand_down_ack_message`** before that line is spoken on stand-down. You do not need a custom image for that mode. Set `"enabled": false` to use a static file instead.
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

### 6. LaunchAgent (login + keep-alive)

1. Copy and edit [launchd/com.jarvis.claplistener.plist.example](launchd/com.jarvis.claplistener.plist.example): replace `REPLACE_WITH_*` with your repo path, home directory, and (recommended) venv `python3` path.
2. Install:

```bash
cp com.jarvis.claplistener.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.jarvis.claplistener.plist
```

Logs: `~/.jarvis/listener.log` and `listener.err.log` (after you create `~/.jarvis` or let the welcome script create it).

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
- **Claps not detected**: set `"clap.debug": true` in `jarvis.json` and watch `peak=` lines while clapping — then set `peak_threshold` **just below** the peaks you see when you clap (typical range **0.08–0.2** on laptop mics). Increase `max_clap_gap_ms` if your second clap is slow (up to **1200**). Allow a brief quiet moment between the two claps.
- **False claps**: raise `peak_threshold` or shorten `max_clap_gap_ms`.
- **Phrase never fires**: speak clearly after the welcome; check `listener.err.log`; try `tiny.en` vs `base.en` in `phrase.whisper_model` (slower, heavier).
- **Wallpaper**: multi-Space behavior varies by macOS version; we set **every desktop** exposed to AppleScript. If one screen does not restore, re-save `wallpaper_restore.json` by running welcome once with a known-good wallpaper.

## Privacy

Audio is processed **locally** (clap energy + Whisper). No cloud STT is used by this repo’s scripts.
