# 4 — Configuration

[← Back to index](README.md)

## Locating and loading config

- **Default path:** `config/jarvis.json` at the repository root (resolved relative to scripts).
- **Override:** set environment variable **`JARVIS_CONFIG`** to an absolute or user-expanded path.
- **CLI:** most Python entry points accept an optional path as the first argument after flags.

**Starting point:** copy [`config/jarvis.example.json`](../config/jarvis.example.json) to `config/jarvis.json` and edit.

## Configuration philosophy

- **One JSON file** holds voice copy, app names, clap tuning, Whisper tuning, and HUD layout.
- **Welcome copy** for holographic mode: `welcome_message` / `welcome_messages` drive **both** on-screen typing and `say` — keep them in sync by editing JSON only.
- **Reference vs tutorial:** use this chapter as a map; the root [README.md](../README.md) has a dense bullet list of every behavioral nuance.

## Environment variables (common)

| Variable | Purpose |
|----------|---------|
| `JARVIS_CONFIG` | Path to `jarvis.json` for almost all scripts. `jarvis_doctor` prints the resolved path (and warns if unset vs default). |
| `JARVIS_REPO_ROOT` | Optional override for repo root (HUD lib resolution). |
| `PYTHON_JARVIS_HUD` | Force a specific Python for HUD scripts. |
| `JARVIS_HUD_BACKEND` | `tk` forces Tk-first order on `jarvis_hud_slider.sh` (see [08-hud.md](08-hud.md)). |
| `JARVIS_HUD_DEBUG_VISIBILITY_MODE` | Overrides `hud_slider.debug_visibility_mode` for HUD debugging. |

## Grouped key reference

### Voice and copy

| Key | Meaning |
|-----|---------|
| `say_voice` | Voice passed to macOS `say`. |
| `say_words_per_minute` | Optional `say -r` rate; omit or `null` for system default. |
| `welcome_message` | Primary welcome line if `welcome_messages` is empty or omitted. |
| `welcome_messages` | Non-empty list → sequential “mission brief” lines; **replaces** sole `welcome_message` when used. |
| `stand_down_ack_message` | Ack line for stand-down (holographic or plain `say`). |
| `stand_down_ack_enabled` | If false, skip spoken ack where applicable. |
| `welcome_sound` / `stand_down_sound` | Optional paths to audio files played with `afplay` at start of each phase. |

### Focus and Shortcuts

| Key | Meaning |
|-----|---------|
| `shortcut_focus_on` | Shortcuts name run after welcome content (lab Focus on). |
| `shortcut_focus_off` | Shortcuts name run during stand-down. |
| `welcome_shortcuts_chain` | Extra Shortcut names run after `shortcut_focus_on`. |

### Wallpaper

| Key | Meaning |
|-----|---------|
| `wallpaper_lab_image` | Required if holographic mode is **disabled** — path to static lab image. |
| `holographic_wallpaper` | Object: `enabled`, typing timings, glow, layout (`subtitle` vs `center`), erase behavior, dimensions. See [07-wallpaper-and-holographic.md](07-wallpaper-and-holographic.md). |

### Desktop prep and apps (welcome)

| Key | Meaning |
|-----|---------|
| `welcome_prepare_desktop` | Finder forward + optional Hide Others. |
| `welcome_hide_other_apps` | Hide Others when prepare is true. |
| `welcome_open_apps_background` | Use `open -g` style launches. |
| `welcome_launch_apps_hidden` | Hidden launch for background opens. |
| `welcome_dock_lab_after_apps` | After launches, hide lab app processes and re-activate Finder (needs Automation). |
| `welcome_delay_terminal_seconds` | Delay before Terminal / codex / claude when enabled. |
| `welcome_terminal_hidden_launch` | Launch terminal hidden vs foreground behavior. |
| `welcome_terminal_activate_after_delay` | iTerm/Terminal activation nuances. |
| `terminal_open_codex_claude` | When true, open terminal and send `codex` / `claude` scripts. |
| `terminal_app` | Terminal app name (Terminal vs iTerm2). |
| `apps.kiro` / `apps.cursor` | App names for `open -a`. |

### Spotify

| Key | Meaning |
|-----|---------|
| `spotify_track_uri` | Spotify URI for stinger. |
| `music_preview_seconds` | How long to let play before pause. |

### Stand-down quits

| Key | Meaning |
|-----|---------|
| `stand_down_apps_quit` | Base list of apps to quit. |
| `stand_down_quit_spotify` | Merge Spotify into quit list (default true in example). |
| `stand_down_quit_terminal` | Merge `terminal_app` into quit list when true. |

### Speech and clap

| Key | Meaning |
|-----|---------|
| `stand_down_phrases` | List of phrases to match after Whisper (fuzzy). |
| `wake_phrases` | Optional list — voice alternative to double-clap when idle. |
| `lab_session_max_minutes` | Auto stand-down after N minutes (0 disables cap). |
| `phrase.*` | Chunk length, overlap, Whisper model, `vad_filter`, `fuzzy_ratio`, `min_rms`, debug. |

#### `clap` (explicit keys)

| Key | Meaning |
|-----|---------|
| `input_device` | `null` = system default; or **integer index** / **name substring** (see `list_audio_devices.py`). Invalid indices fall back to default with a log line. |
| `sample_rate` | Mic sample rate (default 16000). |
| `block_ms` | Audio block length for processing. |
| `peak_threshold` | Base threshold; adaptive calibration may raise it. |
| `calibrate_seconds` | Noise sample duration at startup (`0` skips). |
| `hysteresis` | Fraction of threshold for “quiet” between claps. |
| `min_clap_gap_ms` / `max_clap_gap_ms` | Allowed time between first and second clap. |
| `cooldown_seconds` | Minimum time between successful double-clap triggers. |
| `adaptive_calibration` | When `true` (default), adjust threshold from measured noise; when `false`, use JSON `peak_threshold` exactly after calibration window. |
| `debug` | Log peaks and spectral flatness while tuning. |
| `min_spectral_flatness_db` | Broadband “clap-shaped” detection; speech/music tends to score lower. |
| `max_onset_duration_ms` | If the first transient stays loud too long, treat as not a clap and reset. |

### HUD (`hud_slider`)

| Key | Meaning |
|-----|---------|
| `enabled` | Whether HUD features are relevant in your workflow (scripts may still check other keys). |
| `position` | `top` or `bottom` (AppKit). |
| `reveal_mode` | AppKit: **`edge_dwell`** (default) requires the cursor to stay in the hover band for **`reveal_dwell_seconds`** before the slider appears (reduces accidental reveals). **`edge`** reveals as soon as the pointer enters the band (older behavior). Aliases normalized to **`edge`**: `immediate`, `edge_immediate`, `hover`. Unknown values fall back to **`edge_dwell`**. |
| `reveal_dwell_seconds` | Seconds to hold in the edge band when `reveal_mode` is **`edge_dwell`**. If the key is **omitted**, the code default is **0.4**; [`jarvis.example.json`](../config/jarvis.example.json) uses **3.0** for a more deliberate dwell. |
| `hover_zone_px` | Edge band that reveals the HUD. |
| `hide_delay_seconds` | Hide after pointer leaves edge + HUD. |
| `cooldown_seconds` | Cooldown after actions. |
| `use_blur` | `NSVisualEffectView` vs drawn fallback. |
| `debug_visibility_mode` | `normal`, `always_visible`, `titled_debug`. |
| `confirm_stand_down` | Dialog path: confirm before stand-down. |
| `threshold_left` / `threshold_right` | Tk slider thresholds (legacy path). |
| `margin_from_top` / `margin_from_bottom` | Tk / layout margins. |
| `peek_on_launch_seconds` | **AppKit** (normal mode): seconds to **force the slider visible** right after launch, then hide if the pointer is not in the hover zone. **Tk:** same idea for the floating strip. Use **`0`** to disable. |
| `show_top_anchor_strip` | **AppKit** (normal mode, **`position` = `top`**): show a visual **indicator** on the edge **hover sensor** windows. When **`position`** is **`bottom`**, AppKit forces this off. **Tk:** optional top anchor strip styling. |

### HUD lab chrome (`hud_overlay`)

Used only by the **AppKit** HUD ([`jarvis_hud_appkit.py`](../scripts/jarvis_hud_appkit.py)). Set **`"enabled": false`** at the top level to disable all overlay windows.

| Block | Role |
|-------|------|
| **`hud_overlay.enabled`** | Master switch for overlay feature. |
| **`background`** | Per-screen borderless layer: `base_alpha`, `grid_size_px`, `grid_alpha`, `scan_period_seconds`; each sub-key has its own `enabled`. |
| **`arc_reactor`** | Centered decorative animation on the main display: size, ring, orbit, particle count, rotation period. |
| **`dictation`** | Typing-style strip reading **`state_dir/dictation_text.txt`**. Welcome writes that file (combined welcome lines); stand-down deletes it. Keys include `window_width`, `window_height`, **`screen_y_fraction`** (main display: **larger** values place the strip **lower** toward the bottom edge; code default **0.60**, example JSON **0.90**), `font_size_pt`, `ms_per_char`, `cursor_blink_period_seconds`. |

Defaults and full structure: [`config/jarvis.example.json`](../config/jarvis.example.json).

### State

| Key | Meaning |
|-----|---------|
| `state_dir` | Default `~/.jarvis` — session JSON, wallpaper restore, HUD lock, etc. |

## Scenario recipes

**Quieter room / false claps:** raise `clap.peak_threshold`, shorten `max_clap_gap_ms`, ensure calibration window was quiet.

**Bluetooth mic silence:** set `clap.input_device` using output of `scripts/list_audio_devices.py`.

**More lenient stand-down:** lower `phrase.fuzzy_ratio` slightly; enable `phrase.debug` to see skipped chunks.

**HUD at bottom edge:** `hud_slider.position` = `bottom`, tune `margin_from_bottom`.

**Slider only (no arc/grid/dictation):** set **`hud_overlay.enabled`** to **`false`**.

## Related chapters

- [05-listener-and-speech.md](05-listener-and-speech.md) — clap + Whisper details
- [07-wallpaper-and-holographic.md](07-wallpaper-and-holographic.md) — holographic keys
- [08-hud.md](08-hud.md) — HUD behavior
