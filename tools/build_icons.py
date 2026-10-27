"""
Draws Downbeat's app icons (a crotchet on the theme's accent) as PNGs, with no image library.
Run from the repo root after changing the theme:  .venv\\Scripts\\python tools\\build_icons.py
"""

import json
import math
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "static" / "icons"
TOKENS = ROOT / "static" / "theme" / "tokens.resolved.json"


def hex_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def png(size, pixels):
    """pixels(x, y) -> (r, g, b); returns PNG bytes."""
    rows = b"".join(b"\x00" + b"".join(bytes(pixels(x, y)) for x in range(size)) for y in range(size))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b"")


def crotchet(size, background, ink, safe=1.0):
    """A filled, tilted note head with a stem, inside the central `safe` fraction of the square."""
    scale = size * safe
    offset = (size - scale) / 2
    cx, cy = offset + 0.42 * scale, offset + 0.68 * scale  # note head centre
    rx, ry = 0.17 * scale, 0.12 * scale
    stem_width = 0.055 * scale
    stem_x1 = cx + rx * 0.93  # the stem rises from the head's right-hand side
    stem_x0 = stem_x1 - stem_width
    stem_top = offset + 0.16 * scale
    tilt = -0.45  # radians: the head leans up to the right

    cos_t, sin_t = math.cos(tilt), math.sin(tilt)
    samples = [(0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75)]  # 4x supersampling for smooth edges

    def inside(px, py):
        dx, dy = px - cx, py - cy
        u, v = dx * cos_t + dy * sin_t, -dx * sin_t + dy * cos_t
        if (u / rx) ** 2 + (v / ry) ** 2 <= 1:
            return True
        return stem_x0 <= px <= stem_x1 and stem_top <= py <= cy - ry * 0.2

    def pixel(x, y):
        hits = sum(inside(x + sx, y + sy) for sx, sy in samples) / len(samples)
        return tuple(round(b + (i - b) * hits) for b, i in zip(background, ink, strict=True))

    return png(size, pixel)


def main():
    tokens = json.loads(TOKENS.read_text(encoding="utf-8"))
    background = hex_rgb(tokens["color.action"]["light"])
    ink = hex_rgb(tokens["color.action-text"]["light"])
    OUT.mkdir(parents=True, exist_ok=True)
    for name, size, safe in [
        ("icon-180.png", 180, 1.0),   # iOS home screen
        ("icon-192.png", 192, 1.0),
        ("icon-512.png", 512, 1.0),
        ("maskable-512.png", 512, 0.8),  # Android may crop to a circle; keep the note in the safe zone
    ]:
        (OUT / name).write_bytes(crotchet(size, background, ink, safe))
        print(f"wrote static/icons/{name}")


if __name__ == "__main__":
    main()
