# 7 — Wallpaper and holographic display

[← Back to index](README.md)

## Two modes

| Mode | When | Behavior |
|------|------|----------|
| **Static lab image** | `holographic_wallpaper.enabled` is false | Set `wallpaper_lab_image` on all desktops via AppleScript; voice may still use `say` through helpers. |
| **Holographic** | `enabled` true | Generate PNG frames (Pillow), set as desktop picture per frame; sync typing animation with **`say`** duration probes. |

**Single source of truth for copy:** `welcome_message` / `welcome_messages` and `stand_down_ack_message` drive both voice and on-screen text when holographic typing is used — edit JSON, not a second file.

## `wallpaper_util.py`

CLI contract (see script help):

- **`backup`** — Prints JSON list of desktop picture paths; welcome saves this to `state_dir/wallpaper_restore.json`.
- **`set <path>`** — Apply one image to every desktop.
- **`restore <json_path>`** — Restore per-desktop paths from backup JSON.

Stand-down calls restore **twice** around Focus/app changes to handle flaky desktop state on multi-Space setups.

## `jarvis_holographic_wallpaper.py` (conceptual)

Key functions:

| Function | Purpose |
|----------|---------|
| `apply_black_wallpaper` | Solid black frame — lab “screen off” look between lines. |
| `apply_holographic_wallpaper` | Full typing beat for one line of text. |
| `speak_jarvis_line` | Single entry point for a line of speech: if **`holographic_wallpaper.enabled`**, runs **`play_typing_wallpaper`** (measure `say`, sync typing); otherwise **`run_cli_say`** only. Used for welcome lines; stand-down holo ack calls it directly. |
| `run_cli_say` | Plain macOS **`say`** (with optional `say_words_per_minute`). Stand-down’s non-holo ack path uses this via `_say`. |
| `render_holographic_png` | Pillow render with glow, subtitle layout vs centered layout. |

**Glow** — JSON keys such as `glow_blur`, `glow_color`, multipliers — tune the blue “hologram” look without code changes.

**Layout** — `typing_layout`: `subtitle` (film-style bottom) vs older `center` multi-line wrap.

**Performance** — Frames are written to fresh paths under state with pruning (`_fresh_wallpaper_path`) so disk does not fill with PNGs.

## Dependencies

- **Pillow** — pinned in [`requirements.txt`](../requirements.txt) (`>=10,<12`) for compatibility with older macOS builds per project README notes.

## Related chapters

- [04-configuration.md](04-configuration.md) — holographic keys
- [06-welcome-and-stand-down.md](06-welcome-and-stand-down.md) — when holo runs in the pipeline
