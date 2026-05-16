# Jarvis

macOS “Iron Man” routine: **double-clap** → welcome (voice, Focus, lab wallpaper, Kiro, Cursor, optional Spotify **~10 s** stinger). **Terminal with `codex` / `claude` is off by default** (`terminal_open_codex_claude`); turn it on if you want that flow. While a **lab session** is active, say a configured phrase (e.g. “stand down jarvis”) to **stand down**—save/quit apps, restore wallpaper and Focus, pause Spotify. If clapping or speech is impractical, use the optional **HUD** — **dialog** or **slider** (see below).

## Requirements

- macOS with **Microphone** permission for the Python you use
- **Python 3.10+** recommended
- **Spotify** desktop app (for the stinger)
- **Shortcuts** app (for Focus on/off)
- Optional: **Kiro**, **Cursor**; optional **Terminal** + `codex` / `claude` on your `PATH` if you enable `terminal_open_codex_claude`

## Setup

### 1. Config

```bash
cp config/jarvis.example.json config/jarvis.json
```

Edit `config/jarvis.json`:

- **`holographic_wallpaper`**: when `"enabled": true`, **welcome** and **stand-down** use the same **subtitle** pipeline: holographic text at the **bottom** of the screen, **one character at a time** (with `typing_min_seconds_per_char` so letters do not rush), synced to **`say`** (duration measured with the same flags as playback), then a short **hold**, optional **letter-by-letter erase** (`subtitle_erase_animated`, `subtitle_erase_seconds`), then **black** again. Set **`typing_layout`** to `"center"` for the older centered, multi-line wrap style. Other keys: `subtitle_font_scale`, `subtitle_margin_bottom_ratio`, `subtitle_hold_full_seconds`, `typing_show_cursor`, `typing_cursor_char`, `pause_after_typing_seconds`. Set `"enabled": false` for a static `wallpaper_lab_image` and plain `say`.
- **Subtitle = speech (single source):** For each beat, one normalized line drives **both** the on-screen typing animation and **`say`**: newlines are collapsed to spaces. **`welcome_message`** (or each entry in **`welcome_messages`**) and **`stand_down_ack_message`** are the **only** copy for that beat—edit the JSON to change voice and subtitle together.
- **Glow:** `glow_blur` plus optional **`glow_color`** `[r,g,b,a]`, **`glow_alpha_multiplier`**, **`glow_blur_scale`**, **`glow_blur_extra`**, and **`glow_outer_pass_blur`** (second, fainter halo). Defaults in `jarvis.example.json` are slightly stronger than the old fixed glow; tune to taste.
- **`say_words_per_minute`**: optional integer (e.g. `160`–`200` for slower speech). Passed to **`say -r`** for duration probes and all `say` paths (welcome, stand-down, holographic). Omit or `null` for the system default (no `-r`).
- **Welcome desktop first**: **`welcome_prepare_desktop`** / **`welcome_hide_other_apps`**: Finder + Hide Others before the typing line. **`welcome_open_apps_background`** + **`welcome_launch_apps_hidden`**: `open -g -j` for Kiro/Cursor (no foreground, **hidden** launch). **`welcome_dock_lab_after_apps`**: after launches, AppleScript sets **visible of process** to false for Kiro, Cursor, Terminal/iTerm2, Spotify (as configured) and activates Finder again—needs **Automation** for **System Events**. When **`terminal_open_codex_claude`** is `true`, **`welcome_terminal_hidden_launch`**, **`welcome_delay_terminal_seconds`**, and **`welcome_terminal_activate_after_delay`** apply to Terminal before `codex`/`claude`. Spotify uses **`open -g -j`** and docks lab apps after playback starts. **`stand_down_quit_terminal`** (default **`false`**): when `true`, **`terminal_app`** is merged into the stand-down quit list.
- **`stand_down_quit_spotify`** / **`stand_down_quit_terminal`**: when `true`, **Spotify** and/or **`terminal_app`** are merged into the quit list after **`stand_down_apps_quit`** (deduped). Spotify defaults on; Terminal defaults off unless you enable it.
- **`wallpaper_lab_image`**: required only when holographic mode is **disabled**—absolute path to your lab image
- **`holographic_wallpaper.font_scale` / `glow_blur`**: tweak size and glow strength; `width` / `height` default to your main screen size (`null` = auto)
- **`welcome_message`** / **`stand_down_ack_message`**: primary lines for welcome and stand-down ack (voice + holographic subtitle when enabled)
- **`welcome_messages`**: optional non-empty string array—multiple lines run **sequential** holographic beats (mission-brief style); if empty or omitted, **`welcome_message`** is used alone
- **`welcome_sound`** / **`stand_down_sound`**: optional paths to short audio files; **`afplay`** at the start of welcome / stand-down when set
- **`welcome_shortcuts_chain`**: optional list of Shortcut names to run after **`shortcut_focus_on`** (e.g. dim display, extra Focus)
- **`shortcut_focus_on` / `shortcut_focus_off`**: names of two Shortcuts (see below)
- **`clap.*`**: tune `peak_threshold` / gaps if claps are missed or false-trigger. **`clap.input_device`**: `null` uses the system default mic (safest after macOS updates); or set an **index** or **name substring** from `scripts/list_audio_devices.py`. **`clap.adaptive_calibration`**: when `true` (default), the listener **raises** `peak_threshold` from measured noise during calibration — stay **quiet** during that window, or set **`adaptive_calibration`** to **`false`** to use your JSON `peak_threshold` exactly.
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
./scripts/jarvis_doctor.sh     # concise local diagnostics
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
- Does **not** open **Terminal** for `codex` / `claude` unless **`terminal_open_codex_claude`** is `true` (then **`terminal_app`** runs those CLIs in separate tabs).

To use Kiro’s terminal only: leave `terminal_open_codex_claude` false and use Kiro’s own automation or run the CLIs manually.

## Desktop HUD (no clap / no speech)

When you cannot double-clap or speak stand-down phrases (meeting, library, broken mic), use one of these:

For full HUD architecture, launch modes, and debugging notes, see [docs/HUD.md](docs/HUD.md).

### A. Native dialog (recommended if Tk fails)

**No Tkinter required** — uses a standard macOS list dialog:

```bash
export JARVIS_CONFIG="$PWD/config/jarvis.json"
./scripts/jarvis_hud_dialog.sh
```

Pick **Welcome** or **Stand down**; optional stand-down confirmation matches **`hud_slider.confirm_stand_down`**.

### B. Floating slider (Tk → AppKit → dialog)

**`./scripts/jarvis_hud_slider.sh`** picks the first backend that works: **Tk** window, then **native AppKit** slider (**no Tk** — install **`pip install pyobjc-framework-Cocoa`** in your venv or system Python), then falls back to the **same dialog** as §A so something always appears.

The **Tk** strip keeps the older mapping: drag **left** → welcome, **right** → stand-down (welcome blocked if a lab session is already active). **Center** → idle.

The **native AppKit** HUD (preferred on macOS) is a **borderless liquid-glass slider** at the top (or bottom) of the screen: move the pointer within **`hud_slider.hover_zone_px`** of the **top** (or **bottom**, when **`position`** is **`bottom`**) of the visible desktop and, by default, hold there briefly using **`hud_slider.reveal_mode = "edge_dwell"`** plus **`hud_slider.reveal_dwell_seconds`** before a centered **340×58** pill track **drifts down** from above the edge. Set **`reveal_mode`** to **`edge`** if you want the older immediate reveal behavior. The HUD hides again after **`hide_delay_seconds`** once the cursor leaves both that edge band and the HUD window. The actual HUD window footprint matches the control itself instead of using a full-width transparent strip, and it re-centers on the display under the pointer before revealing. Reveal detection uses a short cursor poll backed by AppKit mouse monitors. **Drag** the knob to snap **left** (stand down) or **right** (welcome / operational), or **click anywhere on the pill** to slide the knob across. AppKit stand-down fires immediately with **no confirmation prompt**. **Right-click** the control for **Quit** (there is no title-bar close button). Set **`use_blur`** to **`false`** to use a drawn “pseudo-glass” fallback instead of **`NSVisualEffectView`** (WithinWindow blur on the pill only). If you run from Terminal, stderr shows **`Jarvis HUD: build=…`** plus the chosen visible frame, window frame, slider frame, and whether the blur or fallback host was used. Voice and wallpaper copy still come only from **`welcome_message`** / **`welcome_messages`** in your JSON; if **`welcome_messages`** is a non-empty list, it **replaces** **`welcome_message`**, so put your opening line as the **first** entry.

The **Tk** strip is still **top-center** (`hud_slider.position`: **`top`**, **`margin_from_top`** ~**44** px) or **`bottom`** with **`margin_from_bottom`**.

**Standalone app + login (no Terminal):** From the repo root run **`./scripts/install_hud_login.sh`**. It copies **[`macos/Jarvis HUD.app`](macos/Jarvis HUD.app)** to **`~/Applications/Jarvis HUD.app`**, writes **`~/.jarvis/repository_path`** (absolute path to this clone), and installs LaunchAgent **`com.jarvis.hud`** with **RunAtLoad** + **KeepAlive** so the HUD starts at login and respawns if you close the window. The app’s launcher runs **`.venv/bin/python3`** + **[`scripts/jarvis_hud_appkit.py`](scripts/jarvis_hud_appkit.py)** (install **`pyobjc-framework-Cocoa`** in the venv first). Remove with **`./scripts/uninstall_hud_login.sh`** (same as **`./scripts/uninstall_hud_launch_agent.sh`**). Logs: **`~/.jarvis/hud.app.log`** and **`hud.app.err.log`**. If macOS blocks the unsigned app the first time, open **Jarvis HUD** once from **Finder → ~/Applications** via **Right-click → Open**, then approve.

**Manual run (development):**

```bash
cd /path/to/Jarvis
source .venv/bin/activate   # optional
pip install pyobjc-framework-Cocoa
export JARVIS_CONFIG="$PWD/config/jarvis.json"
./scripts/jarvis_hud_slider.sh
```

Optional **`hud_slider`**: AppKit — **`reveal_mode`** (`edge_dwell` or `edge`), **`reveal_dwell_seconds`**, **`hover_zone_px`**, **`hide_delay_seconds`**, **`use_blur`**, **`cooldown_seconds`**, **`position`** (`top` / `bottom`), **`margin_from_bottom`**, **`enabled`**, and **`debug_visibility_mode`** (`normal`, `always_visible`, `titled_debug`). Tk/dialog legacy paths still use **`confirm_stand_down`**, **`threshold_left`**, and **`threshold_right`**. Keys like **`margin_from_top`**, **`peek_on_launch_seconds`**, and **`show_top_anchor_strip`** are mainly for AppKit / older / Tk layout behavior rather than the dialog path. For one-off debugging without editing JSON, you can also launch with **`JARVIS_HUD_DEBUG_VISIBILITY_MODE=always_visible`** (or **`titled_debug`**) before **`./scripts/jarvis_hud_slider.sh`**. See [docs/HUD.md](docs/HUD.md) for the full debug flow.

**Custom appearance:** When you have mockups, tune colors, fonts, and window chrome in **`jarvis_hud_appkit.py`** (and optionally **`jarvis_hud_slider.py`** for the Tk fallback); new optional JSON keys can be added under **`hud_slider`** as needed.

## Iron Man–style ideas (backlog)

Stronger preset glow (tweak **`holographic_wallpaper`** JSON), optional **`welcome_sound`** / **`stand_down_sound`**, chained **`welcome_messages`**, extra Shortcuts via **`welcome_shortcuts_chain`**, and future upgrades (phoneme sync, richer HUD themes, etc.) are natural extensions; the config keys above cover the common ones. For a **local health report**, use **`./scripts/jarvis_doctor.sh`** (read-only checks: config, imports, state, LaunchAgents, HUD runtime drift).

## State files

Stored under `~/.jarvis/` (or `state_dir` in config):

- `lab_session.json` — lab session active flag and start time
- `wallpaper_restore.json` — previous desktop picture paths for restore
- `repository_path` — one line: absolute path to the Jarvis repo (written by **`install_hud_login.sh`** for **`Jarvis HUD.app`**)

## Troubleshooting

- **Quick health check**: Run **`./scripts/jarvis_doctor.sh`** for a concise read-only report covering config resolution, Python/runtime imports, state files, LaunchAgents, and HUD runtime drift.
- **Double-clap does nothing**: If a **lab session** is still active from last time, the listener only listens for the **stand-down phrase**, not claps. Run `./scripts/jarvis_stand_down.sh` or delete `~/.jarvis/lab_session.json`. The listener prints a warning on startup if this is the case. While active, a **successful double-clap** is **ignored** and logs **`Double-clap ignored — lab session already ACTIVE`** (at most about once every 25 seconds) so it is obvious you are not in “fresh” clap mode.
- **Background listener (LaunchAgent) never starts Jarvis**: The listener now runs **welcome** with the **same Python** as itself (your `.venv`), so Pillow/Shortcuts still work. If it used to fail silently, reinstall: `./scripts/install_launch_agent.sh` then `tail -f ~/.jarvis/listener.err.log` while clapping — you should see `Double-clap detected` or a **Welcome script failed** line with the real error.
- **Calibration**: On startup the listener measures **~1.2s** of background noise (`calibrate_seconds` in JSON; set to **0** to skip). Stay quiet during that window. Then clap sharply twice with a short pause between. It also prints **`JARVIS // MIC ONLINE // …`** with the input device name (see LaunchAgent logs).
- **HUD slider not visible / Tk broken**: Use **`./scripts/jarvis_hud_dialog.sh`** instead — it does not use Tkinter. If the AppKit HUD exists but you still do not see it, launch with **`JARVIS_HUD_DEBUG_VISIBILITY_MODE=always_visible ./scripts/jarvis_hud_slider.sh`** first; if needed, use **`titled_debug`** next to isolate borderless-window issues. The production AppKit HUD is a **small floating window** rather than a full-width transparent strip. **`System Settings → Privacy & Security → Automation`** may prompt for **Terminal** or **Python** the first time **`osascript`** runs the dialog HUD. See [docs/HUD.md](docs/HUD.md) for the full debug flow.
- **`No module named '_tkinter'`** / **Tkinter**: **`jarvis_hud_slider.sh`** picks the first Python that can **`import tkinter`** (venv if it has Tk, else **Apple `/usr/bin/python3`**, else `python3` on `PATH`). Homebrew Python often ships **without** Tk; use Apple’s Python for the HUD or install **`brew install python-tk`** and recreate the venv if you need Tk inside `.venv`. To force an interpreter: **`PYTHON_JARVIS_HUD=/path/to/python3 ./scripts/jarvis_hud_slider.sh`**.
- **`Python quit unexpectedly`** when opening the HUD: Usually **Tk** + **Homebrew Python** (bad Tcl/Tk). The launcher now prefers **AppKit** (`jarvis_hud_appkit.py`) on macOS first; run **`pip install pyobjc-framework-Cocoa`** and **`./scripts/jarvis_hud_slider.sh`** again. To force Tk anyway: **`JARVIS_HUD_BACKEND=tk ./scripts/jarvis_hud_slider.sh`**. Or use **`./scripts/jarvis_hud_dialog.sh`** (no GUI toolkit).
- **HUD does not appear at login:** Run **`./scripts/install_hud_login.sh`** from the repo (updates **`~/Applications/Jarvis HUD.app`** and **`~/.jarvis/repository_path`**). Check **`launchctl list | grep jarvis`** and **`tail -f ~/.jarvis/hud.app.err.log`**. Re-run install after moving the repo so **`repository_path`** stays correct. If **`~/Applications`** does not exist, the script creates it.
- **`macOS 15 (1507) or later required` / Welcome script failed**: Was usually **tkinter** (removed) plus **Pillow 12+** on slightly older macOS builds. Run `pip install 'Pillow>=10,<12'` in `.venv`, pull latest Jarvis scripts, reinstall the LaunchAgent.
- **Silent mic / AirPods**: Background listeners often get **zeros** from Bluetooth. In **System Settings → Sound → Input** choose **MacBook Microphone**, then run `python3 scripts/list_audio_devices.py`, put that device’s **index** (or a unique **name substring**) in **`clap.input_device`** in `jarvis.json`, and restart the listener.
- **Claps not detected**: set `"clap.debug": true` in `jarvis.json` and watch `peak=` lines while clapping — then set `peak_threshold` **just below** the peaks you see when you clap (typical range **0.08–0.2** on laptop mics). Increase `max_clap_gap_ms` if your second clap is slow (up to **1200**). Allow a brief quiet moment between the two claps.
- **False claps**: raise `peak_threshold` or shorten `max_clap_gap_ms`.
- **Phrase / stand-down never fires**: After welcome, logs should show `Heard: '…'` as you speak. Set `"phrase.debug": true` to see skipped chunks. Defaults now use **`vad_filter: false`** (VAD often dropped speech), **longer chunks + overlap** so phrases are not split, **lower `min_rms`**, and **fuzzy** matching for small Whisper mistakes. Tune `phrase.fuzzy_ratio` (lower = more lenient). If stand-down runs but nothing happens, check **`Stand-down script failed`** in `listener.err.log`.
- **Wallpaper**: multi-Space behavior varies by macOS version; we set **every desktop** exposed to AppleScript. If one screen does not restore, re-save `wallpaper_restore.json` by running welcome once with a known-good wallpaper.

## Privacy

Audio is processed **locally** (clap energy + Whisper). No cloud STT is used by this repo’s scripts.
