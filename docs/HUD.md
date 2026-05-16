# Jarvis HUD

The Jarvis HUD is the manual-control path for the project when clap or speech is impractical.

## Overview

There are three HUD backends:

- `jarvis_hud_appkit.py`: native macOS AppKit HUD, preferred on macOS
- `jarvis_hud_slider.py`: Tk fallback
- `jarvis_hud_dialog.py`: native AppleScript dialog fallback

The normal AppKit HUD is a small borderless floating window that uses a short cursor poll plus AppKit mouse monitors to detect when the pointer enters the configured hover band near the top or bottom of the active display. By default it now waits for a brief dwell inside that edge band before revealing, which reduces accidental pop-ups during normal top-edge mouse travel. The actual HUD window footprint matches the control itself rather than spanning the full display width, and the production control is a slim `340×58` liquid-glass slider.

## Launch

Recommended local launch:

```bash
cd /path/to/Jarvis
source .venv/bin/activate
export JARVIS_CONFIG="$PWD/config/jarvis.json"
./scripts/jarvis_hud_slider.sh
```

Direct AppKit launch:

```bash
cd /path/to/Jarvis
source .venv/bin/activate
export JARVIS_CONFIG="$PWD/config/jarvis.json"
./.venv/bin/python3 -B scripts/jarvis_hud_appkit.py
```

`jarvis_hud_slider.sh` now probes the real AppKit HUD module before selecting a Python, so it does not treat a bare `objc` import as sufficient.

## Normal Behavior

In `hud_slider.debug_visibility_mode = "normal"`:

- the HUD starts hidden
- in the default `hud_slider.reveal_mode = "edge_dwell"`, moving the cursor into `hud_slider.hover_zone_px` near the configured edge starts a brief dwell timer and reveals the HUD only after `hud_slider.reveal_dwell_seconds`
- `hud_slider.reveal_mode = "edge"` restores the older immediate reveal behavior
- the HUD stays visible while the pointer is over the HUD window itself
- moving away hides it after `hud_slider.hide_delay_seconds`
- left = stand down, right = operational / welcome
- when the slider appears, the knob **syncs to lab state** (right if a session is already active, left if idle)
- click anywhere on the pill toggles, drag snaps at midpoint; **right-click** or **Control-click** opens a menu (Quit)
- AppKit stand-down fires immediately without a confirmation prompt (use the **dialog** HUD if you want `confirm_stand_down`)

The HUD re-centers on the display that currently contains the pointer before it shows and rests close to the top edge rather than far down the screen.

In **normal** mode, **`hud_slider.peek_on_launch_seconds`**: when set to a **positive** number of seconds, the slider is **shown immediately on launch** for that duration, then hides unless the cursor is in the hover zone.

## Lab chrome overlay (`hud_overlay`, AppKit only)

Optional layers (dim grid background, center “arc reactor” animation, dictation strip) are configured under **`hud_overlay`** in `jarvis.json` (see `config/jarvis.example.json`).

**Stacking:** those windows use a **low window level** so they sit **behind ordinary application windows** on the **desktop wallpaper**. The **slider** stays above apps. If a fullscreen window covers the desktop, you may not see the chrome — that is expected.

**Visibility:** overlays are created at HUD launch but stay **transparent until a lab session is active**, then **fade out after stand down** (~0.5s poll vs `lab_session.json`).

The **dictation** layer types text from **`state_dir/dictation_text.txt`**, which **welcome** writes and **stand down** removes.

For a longer human-oriented write-up, see [project-jarvis/08-hud.md](../project-jarvis/08-hud.md).

## Debug Visibility Modes

Use `hud_slider.debug_visibility_mode` in JSON or `JARVIS_HUD_DEBUG_VISIBILITY_MODE` as an environment override.

Supported modes:

- `normal`: production hover HUD
- `always_visible`: force the HUD visible immediately, bypass hover gating
- `titled_debug`: show the same slider inside a normal titled window for visibility debugging

Example:

```bash
JARVIS_HUD_DEBUG_VISIBILITY_MODE=always_visible ./scripts/jarvis_hud_slider.sh
```

Or:

```bash
JARVIS_HUD_DEBUG_VISIBILITY_MODE=titled_debug ./scripts/jarvis_hud_slider.sh
```

## Relevant Config

The main HUD keys live under `hud_slider` in `config/jarvis.json`:

- `position`: `top` or `bottom`
- `reveal_mode`: `edge_dwell` (default) or `edge` (aliases `immediate`, `edge_immediate`, `hover` map to `edge`)
- `reveal_dwell_seconds`: dwell time in `edge_dwell` mode (code default **0.4** if omitted; example JSON often uses a longer value)
- `hover_zone_px`: edge band that reveals the HUD in normal mode
- `hide_delay_seconds`: delay before hiding after the pointer leaves the edge band and HUD
- `cooldown_seconds`: action cooldown after welcome or stand down
- `margin_from_bottom`: bottom placement offset
- `use_blur`: use `NSVisualEffectView` instead of the drawn pseudo-glass fallback
- `debug_visibility_mode`: `normal`, `always_visible`, or `titled_debug`
- `peek_on_launch_seconds`: optional AppKit/Tk peek-on-launch (see **Normal Behavior**)
- `show_top_anchor_strip`: AppKit (top position): indicator on hover sensor strips; Tk: strip chrome
- `margin_from_top`: Tk / placement

Tk/dialog legacy keys such as `confirm_stand_down`, `threshold_left`, and `threshold_right` still exist for the fallback slider path.

## Diagnostics

When launched from Terminal, the AppKit HUD prints diagnostics such as:

- build id
- visibility mode
- blur host vs fallback host
- **`reveal=`** and **`dwell=`** (reveal mode and dwell seconds)
- hover band px and poll interval
- chosen visible frame
- final window frame
- slider container frame
- whether the slider started hidden
- current slider alpha

This is the first place to look if the HUD does not show.

Normal mode also logs the hover poll interval so you can confirm the reveal loop is running.

## Troubleshooting

For a broader read-only check (config, PyObjC, HUD runtime copies vs repo, LaunchAgents), run **`./scripts/jarvis_doctor.sh`** from the Jarvis clone.

If the HUD does not appear:

1. Launch `always_visible` mode to verify the control actually renders.
2. If it still does not appear, launch `titled_debug` to isolate borderless-window issues from slider-rendering issues.
3. If AppKit fails entirely, run `./scripts/jarvis_hud_dialog.sh` so manual control still works.

If the wrapper selects the wrong Python:

- prefer `.venv/bin/python3`
- verify `pyobjc-framework-Cocoa` is installed in that interpreter
- run the direct AppKit launch command above to bypass wrapper selection

If the HUD works in `always_visible` but not `normal`:

- inspect the printed `visibleFrame`, `window`, and `slide` diagnostics
- confirm `hud_slider.position` and `hover_zone_px`
- confirm the cursor is entering the correct screen edge on the display where the HUD should appear
- if the slider feels slow to appear, you are likely in **`edge_dwell`** — reduce `reveal_dwell_seconds` or set `reveal_mode` to **`edge`**

## Login / Standalone App

For login startup without Terminal:

```bash
./scripts/install_hud_login.sh
```

This installs `~/Applications/Jarvis HUD.app`, writes `~/.jarvis/repository_path`, and loads the `com.jarvis.hud` LaunchAgent.

Remove with:

```bash
./scripts/uninstall_hud_login.sh
```
