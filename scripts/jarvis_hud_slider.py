#!/usr/bin/env python3
"""
Floating HUD strip: drag slider left → welcome, right → stand-down (when clap/speech is impractical).
Run manually: python3 scripts/jarvis_hud_slider.py [path/to/jarvis.json]
Respects JARVIS_CONFIG when no path is given.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path


def _load_cfg(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _state_dir(cfg: dict) -> Path:
    return Path(os.path.expanduser(cfg.get("state_dir", "~/.jarvis"))).resolve()


def _lab_active(cfg: dict) -> bool:
    sp = _state_dir(cfg) / "lab_session.json"
    if not sp.is_file():
        return False
    try:
        return bool(json.loads(sp.read_text(encoding="utf-8")).get("active"))
    except (json.JSONDecodeError, OSError):
        return False


def main() -> int:
    root_dir = Path(__file__).resolve().parent.parent
    cfg_path = Path(
        os.environ.get("JARVIS_CONFIG", str(root_dir / "config" / "jarvis.json"))
    ).expanduser().resolve()
    if len(sys.argv) > 1:
        cfg_path = Path(sys.argv[1]).expanduser().resolve()

    cfg = _load_cfg(cfg_path)
    hud = cfg.get("hud_slider") or {}

    thresh_l = float(hud.get("threshold_left", 0.35))
    thresh_r = float(hud.get("threshold_right", 0.65))
    cooldown = float(hud.get("cooldown_seconds", 2.5))
    confirm_sd = hud.get("confirm_stand_down", True)
    pos = str(hud.get("position", "bottom")).lower()

    scripts = Path(__file__).resolve().parent
    last_fire = 0.0

    import tkinter as tk
    from tkinter import messagebox, ttk

    win = tk.Tk()
    win.title("Jarvis HUD")
    win.attributes("-topmost", True)
    win.configure(bg="#1a1a20")
    w_win, h_win = 400, 76
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    x = max(0, (sw - w_win) // 2)
    y = sh - h_win - 48 if pos == "bottom" else 36
    win.geometry(f"{w_win}x{h_win}+{x}+{y}")

    var = tk.DoubleVar(value=0.5)
    scale = ttk.Scale(
        win, from_=0.0, to=1.0, variable=var, orient=tk.HORIZONTAL, length=360
    )
    scale.pack(pady=(28, 8))
    tk.Label(win, text="◀ Welcome", bg="#1a1a20", fg="#6ad4ff", font=("Helvetica", 10)).place(
        x=12, y=6
    )
    tk.Label(win, text="Stand down ▶", bg="#1a1a20", fg="#6ad4ff", font=("Helvetica", 10)).place(
        x=268, y=6
    )

    env_base = {**os.environ, "JARVIS_CONFIG": str(cfg_path)}

    def on_release(_event: object) -> None:
        nonlocal last_fire
        now = time.time()
        if now - last_fire < cooldown:
            var.set(0.5)
            return
        v = var.get()
        var.set(0.5)
        if v < thresh_l:
            if _lab_active(cfg):
                messagebox.showinfo("Jarvis", "Lab session already active.", parent=win)
                return
            subprocess.Popen(
                [str(scripts / "jarvis_welcome.sh")],
                cwd=str(root_dir),
                env=env_base,
            )
            last_fire = now
        elif v > thresh_r:
            if confirm_sd and not messagebox.askyesno(
                "Jarvis", "Stand down and quit lab apps?", parent=win
            ):
                return
            subprocess.Popen(
                [str(scripts / "jarvis_stand_down.sh")],
                cwd=str(root_dir),
                env=env_base,
            )
            last_fire = now

    scale.bind("<ButtonRelease-1>", on_release)

    win.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
