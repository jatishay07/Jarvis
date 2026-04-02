#!/usr/bin/env python3
"""
Render a black desktop image with blue/cyan holographic-style text, then set it via wallpaper_util.
Used so on-screen text matches whatever macOS `say` will speak.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path


def screen_dimensions() -> tuple[int, int]:
    """Avoid tkinter (breaks on some macOS/Python combos with version-gate errors)."""
    try:
        out = subprocess.check_output(
            [
                "osascript",
                "-e",
                'tell application "Finder" to get bounds of window of desktop',
            ],
            text=True,
            timeout=8,
        ).strip()
        # e.g. 0, 0, 1710, 1107  → left, top, right, bottom
        cleaned = out.replace("{", "").replace("}", "")
        parts = [int(x.strip()) for x in cleaned.split(",") if x.strip()]
        if len(parts) >= 4:
            left, top, right, bottom = parts[0], parts[1], parts[2], parts[3]
            w, h = right - left, bottom - top
            if w >= 640 and h >= 480:
                return w, h
    except (subprocess.CalledProcessError, ValueError, subprocess.TimeoutExpired, OSError):
        pass
    return 2560, 1600


def _font_candidates() -> list[Path]:
    return [
        Path("/System/Library/Fonts/SFNS.ttf"),
        Path("/System/Library/Fonts/SFNSDisplay.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/Library/Fonts/Arial.ttf"),
    ]


def render_holographic_png(
    text: str,
    out_path: Path,
    width: int,
    height: int,
    style: dict | None = None,
) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFilter, ImageFont
    except ImportError as e:
        raise RuntimeError("Install Pillow: pip install Pillow") from e

    style = style or {}
    font_scale = float(style.get("font_scale", 0.075))
    glow_blur = int(style.get("glow_blur", 12))
    margin = int(width * 0.06)

    base = Image.new("RGB", (width, height), (0, 0, 0))
    rgba = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    font_size = max(24, int(min(width, height) * font_scale))
    font = ImageFont.load_default()
    for fp in _font_candidates():
        if fp.is_file():
            try:
                font = ImageFont.truetype(str(fp), font_size)
                break
            except OSError:
                continue

    # Wrap to fit width
    avg_char = max(1, font_size // 2)
    max_chars = max(12, (width - 2 * margin) // avg_char)
    lines = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        lines.extend(textwrap.wrap(paragraph, width=max_chars) or [paragraph])

    if not lines:
        lines = [" "]

    dummy = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    line_heights: list[int] = []
    line_widths: list[int] = []
    for line in lines:
        bbox = dummy.textbbox((0, 0), line, font=font)
        line_heights.append(bbox[3] - bbox[1])
        line_widths.append(bbox[2] - bbox[0])

    line_gap = int(font_size * 0.25)
    total_h = sum(line_heights) + line_gap * (len(lines) - 1)
    y0 = max(margin, (height - total_h) // 2)

    def draw_line_glow(d: ImageDraw.ImageDraw, x: int, y: int, line: str) -> None:
        glow_color = (40, 140, 255, 90)
        for ox, oy in [
            (0, 0),
            (3, 0),
            (-3, 0),
            (0, 3),
            (0, -3),
            (4, 4),
            (-4, -4),
            (5, -2),
            (-5, 2),
        ]:
            d.text((x + ox, y + oy), line, font=font, fill=glow_color)

    def draw_line_holo(d: ImageDraw.ImageDraw, x: int, y: int, line: str) -> None:
        # Chromatic / holographic offsets
        d.text((x - 2, y), line, font=font, fill=(120, 240, 255, 220))
        d.text((x + 2, y), line, font=font, fill=(100, 100, 255, 180))
        d.text((x, y - 1), line, font=font, fill=(200, 255, 255, 255))
        d.text((x, y + 1), line, font=font, fill=(30, 120, 255, 200))
        d.text((x, y), line, font=font, fill=(160, 230, 255, 255), stroke_width=2, stroke_fill=(0, 60, 140, 255))

    glow_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_layer)
    sharp = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sharp)

    y = y0
    for i, line in enumerate(lines):
        lw = line_widths[i]
        x = (width - lw) // 2
        draw_line_glow(gd, x, y, line)
        draw_line_holo(sd, x, y, line)
        y += line_heights[i] + line_gap

    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(max(1, glow_blur)))
    comp = Image.alpha_composite(rgba, glow_layer)
    comp = Image.alpha_composite(comp, sharp)
    out = Image.alpha_composite(base.convert("RGBA"), comp).convert("RGB")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(out_path, "PNG", optimize=True)


def render_black_png(out_path: Path, width: int, height: int) -> None:
    try:
        from PIL import Image
    except ImportError as e:
        raise RuntimeError("Install Pillow: pip install Pillow") from e
    out_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (width, height), (0, 0, 0)).save(out_path, "PNG", optimize=True)


def _wallpaper_set(util: Path, png: Path) -> None:
    r = subprocess.run(
        [sys.executable, str(util), "set", str(png)],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "wallpaper set failed")


def measure_say_duration_seconds(text: str, voice: str) -> float:
    """Render speech to a temp AIFF and read duration with afinfo (macOS)."""
    fallback = max(1.8, min(12.0, len(text) * 0.068))
    fd, path = tempfile.mkstemp(suffix=".aiff", prefix="jarvis_say_")
    os.close(fd)
    try:
        cmd = ["say", "-o", path]
        if voice:
            cmd.extend(["-v", voice])
        cmd.append(text)
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            return fallback
        info = subprocess.run(["afinfo", path], capture_output=True, text=True)
        if info.returncode != 0:
            return fallback
        m = re.search(r"estimated duration:\s*([\d.]+)\s*sec", info.stdout, re.I)
        if m:
            return max(0.5, float(m.group(1)))
        m = re.search(r"(\d+\.?\d*)\s*sec", info.stdout)
        if m:
            return max(0.5, float(m.group(1)))
        return fallback
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def play_typing_wallpaper(
    cfg: dict,
    state: Path,
    full_text: str,
    voice: str,
    *,
    end_with_black: bool = True,
) -> None:
    """
    Type holographic text in sync with `say` (duration from afinfo).
    If end_with_black, replace with a black frame (welcome / mid-session).
    If False, leave the final typed frame up (stand-down then restores wallpaper).
    """
    hw = cfg.get("holographic_wallpaper", {})
    if not hw.get("enabled", False):
        return

    scripts_dir = Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    sw, sh = screen_dimensions()
    w = int(hw["width"]) if hw.get("width") is not None else sw
    h = int(hw["height"]) if hw.get("height") is not None else sh
    util = scripts_dir / "wallpaper_util.py"
    frame_path = state / "holographic_wallpaper.png"
    black_path = state / "holographic_black.png"

    duration = measure_say_duration_seconds(full_text, voice)
    show_cursor = bool(hw.get("typing_show_cursor", True))
    cursor_char = str(hw.get("typing_cursor_char", "|"))

    display = full_text.replace("\n", " ").strip()
    if not display:
        render_black_png(black_path, w, h)
        _wallpaper_set(util, black_path)
        return

    n = len(display)
    say_cmd = ["say"]
    if voice:
        say_cmd.extend(["-v", voice])
    say_cmd.append(full_text)
    proc = subprocess.Popen(say_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    t0 = time.perf_counter()
    try:
        for i in range(1, n + 1):
            visible = display[:i]
            if show_cursor and i < n:
                visible = visible + cursor_char
            render_holographic_png(visible, frame_path, w, h, hw)
            _wallpaper_set(util, frame_path)
            target = t0 + duration * (i / n)
            delay = target - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
        proc.wait(timeout=duration + 8.0)
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                proc.kill()

    pause = float(hw.get("pause_after_typing_seconds", 0.12))
    time.sleep(pause)
    if end_with_black:
        render_black_png(black_path, w, h)
        _wallpaper_set(util, black_path)


def apply_holographic_wallpaper(cfg: dict, state: Path, text: str) -> None:
    hw = cfg.get("holographic_wallpaper", {})
    if not hw.get("enabled", False):
        raise RuntimeError("holographic_wallpaper.enabled is false")

    sw, sh = screen_dimensions()
    w = int(hw["width"]) if hw.get("width") is not None else sw
    h = int(hw["height"]) if hw.get("height") is not None else sh

    out = state / "holographic_wallpaper.png"
    render_holographic_png(text, out, w, h, hw)
    util = Path(__file__).resolve().parent / "wallpaper_util.py"
    _wallpaper_set(util, out)


def main() -> int:
    if len(sys.argv) < 3:
        print(
            "usage: jarvis_holographic_wallpaper.py render <out.png> <text> [width] [height]",
            file=sys.stderr,
        )
        return 2
    cmd = sys.argv[1]
    if cmd != "render":
        return 2
    out = Path(sys.argv[2])
    text = sys.argv[3]
    w = int(sys.argv[4]) if len(sys.argv) > 4 else screen_dimensions()[0]
    h = int(sys.argv[5]) if len(sys.argv) > 5 else screen_dimensions()[1]
    render_holographic_png(text, out, w, h, {})
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
