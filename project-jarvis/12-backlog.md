# 12 — Backlog and ideas

[← Back to index](README.md)

This chapter lists **possible future work** and product ideas. Nothing here is a commitment or roadmap; it exists so scattered notes have one place to live.

## Diagnostics and config

- **`jarvis_doctor` extensions:** validate `jarvis.json` against a schema, report unknown keys, diff against `jarvis.example.json`, or summarize risky combinations (e.g. holographic on without required keys).
- **Structured logging:** optional JSON lines or a single rotating log for listener, welcome, and stand-down with correlation ids for one “session.”
- **Profiles:** named presets (e.g. `work` / `demo`) switching config paths or overlays without hand-editing JSON.

## HUD and UX

- **Stand-down parity:** optional confirmation in AppKit HUD when `confirm_stand_down` is true (match dialog HUD behavior).
- **Menu bar item:** lightweight status (lab on/off), quick welcome / stand down, open logs.
- **Hooks:** user-defined scripts or Shortcuts invoked at fixed points (before/after welcome, after stand down).

## Listener and speech

- **Wake / stand-down tuning UI:** live meters or a small panel for thresholds without editing JSON.
- **Device health:** remind when input device changes or RMS stays near zero (Bluetooth quirks).

## Ops

- **Packaging:** signed helper app or notarized bundle for wider distribution (out of scope for the current script-first repo).

## Related chapters

- [09-installation-and-launchd.md](09-installation-and-launchd.md) — **`jarvis_doctor`**
- [11-troubleshooting.md](11-troubleshooting.md) — when something breaks today
