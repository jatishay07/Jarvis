#!/usr/bin/env python3
"""
Render a black desktop image with blue/cyan holographic-style text, then set it via wallpaper_util.
Used so on-screen text matches whatever macOS `say` will speak.
"""
from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path


def screen_dimensions() -> tuple[int, int]:
    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        w = root.winfo_screenwidth()
        h = root.winfo_screenheight()
        root.destroy()
        return int(w), int(h)
    except Exception:
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
    r = subprocess.run(
        [sys.executable, str(util), "set", str(out)],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "wallpaper set failed")


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
