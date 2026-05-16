#!/usr/bin/env python3
"""
Floating HUD strip: drag slider left → welcome, right → stand-down (when clap/speech is impractical).
Run manually: python3 scripts/jarvis_hud_slider.py [path/to/jarvis.json]
Or: ./scripts/jarvis_hud_slider.sh
Respects JARVIS_CONFIG when no path is given.
"""
from __future__ import annotations

import sys
import time

from jarvis_hud_lib import acquire_hud_singleton, lab_active, load_cfg, resolve_cfg_path, spawn_stand_down, spawn_welcome


def _raise_window(win: object, *, grab_focus: bool = True) -> None:
    """Best-effort: keep HUD above normal windows (topmost strip). Avoid grab_focus in timers."""
    try:
        win.deiconify()  # type: ignore[union-attr]
        win.lift()  # type: ignore[union-attr]
        win.attributes("-topmost", True)  # type: ignore[union-attr]
        if grab_focus:
            win.focus_force()  # type: ignore[union-attr]
    except Exception:
        pass


def main() -> int:
    import tkinter as tk
    from tkinter import messagebox

    cfg_path = resolve_cfg_path(sys.argv)

    cfg = load_cfg(cfg_path)
    if not acquire_hud_singleton(cfg):
        print("Jarvis HUD already running; skipping duplicate Tk instance.", file=sys.stderr)
        return 0
    hud = cfg.get("hud_slider") or {}

    thresh_l = float(hud.get("threshold_left", 0.35))
    thresh_r = float(hud.get("threshold_right", 0.65))
    cooldown = float(hud.get("cooldown_seconds", 2.5))
    confirm_sd = hud.get("confirm_stand_down", True)
    pos = str(hud.get("position", "top")).lower()
    # Top: pixels below screen top (menu bar / notch — ~40–50 is usually visible).
    margin_top = int(hud.get("margin_from_top", 44))
    # Bottom: pixels above Dock (when position is bottom).
    margin_bottom = int(hud.get("margin_from_bottom", 100))

    last_fire = 0.0

    win = tk.Tk()
    win.title("Jarvis HUD")
    win.configure(bg="#14141a")
    win.resizable(False, False)

    w_win, h_win = 420, 104
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    x = max(0, (sw - w_win) // 2)
    if pos == "bottom":
        y = max(40, sh - h_win - margin_bottom)
    else:
        # Default and "top": pin under menu bar
        y = max(24, margin_top)
    win.geometry(f"{w_win}x{h_win}+{x}+{y}")

    outer = tk.Frame(
        win,
        bg="#14141a",
        highlightbackground="#2ec4ff",
        highlightthickness=2,
        padx=10,
        pady=8,
    )
    outer.pack(fill=tk.BOTH, expand=True)

    tk.Label(
        outer,
        text="JARVIS // LAB HUD",
        bg="#14141a",
        fg="#7ee0ff",
        font=("Helvetica", 12, "bold"),
    ).pack(anchor=tk.CENTER, pady=(0, 4))

    row = tk.Frame(outer, bg="#14141a")
    row.pack(fill=tk.X)

    tk.Label(row, text="Welcome ◀", bg="#14141a", fg="#9ae6ff", font=("Helvetica", 10)).pack(
        side=tk.LEFT, padx=(0, 6)
    )

    # tk.Scale is much more visible than ttk.Scale on many macOS Tk builds.
    var = tk.IntVar(value=500)

    def _value_as_float() -> float:
        return max(0, min(1000, int(var.get()))) / 1000.0

    scale = tk.Scale(
        row,
        from_=0,
        to=1000,
        orient=tk.HORIZONTAL,
        variable=var,
        length=280,
        width=14,
        showvalue=0,
        sliderlength=22,
        sliderrelief=tk.RAISED,
        troughcolor="#2a3040",
        bg="#1e2430",
        fg="#7ee0ff",
        highlightthickness=0,
        bd=0,
        activebackground="#4a90d9",
    )
    scale.pack(side=tk.LEFT, expand=True, fill=tk.X)

    tk.Label(row, text="▶ Stand down", bg="#14141a", fg="#9ae6ff", font=("Helvetica", 10)).pack(
        side=tk.LEFT, padx=(6, 0)
    )

    tk.Label(
        outer,
        text="Drag, then release toward Welcome or Stand down",
        bg="#14141a",
        fg="#6a7a8a",
        font=("Helvetica", 9),
    ).pack(anchor=tk.CENTER, pady=(6, 0))

    def on_release(_event: object) -> None:
        nonlocal last_fire
        now = time.time()
        if now - last_fire < cooldown:
            var.set(500)
            return
        v = _value_as_float()
        var.set(500)
        if v < thresh_l:
            if lab_active(cfg):
                messagebox.showinfo("Jarvis", "Lab session already active.", parent=win)
                return
            spawn_welcome(cfg_path)
            last_fire = now
        elif v > thresh_r:
            if confirm_sd and not messagebox.askyesno(
                "Jarvis", "Stand down and quit lab apps?", parent=win
            ):
                return
            spawn_stand_down(cfg_path)
            last_fire = now

    scale.bind("<ButtonRelease-1>", on_release)

    win.update_idletasks()
    _raise_window(win)
    win.after(80, lambda: _raise_window(win))
    win.after(400, lambda: _raise_window(win))
    # Stay above other windows if something steals focus (fullscreen apps may still cover).
    def _keep_on_top() -> None:
        _raise_window(win, grab_focus=False)
        win.after(4000, _keep_on_top)

    win.after(2000, _keep_on_top)

    win.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
