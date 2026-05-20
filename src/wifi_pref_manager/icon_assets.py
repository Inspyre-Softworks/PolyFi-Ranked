"""
Author:
    Inspyre Softworks

Project:
    PolyFi: Ranked

File:
    icon_assets.py

Description:
    Shared application icon helpers for tray and Windows shell integrations.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


def create_app_icon_image(size: int = 64) -> Image.Image:
    """
    Create the shared PolyFi icon artwork at the requested size.

    Parameters:
        size:
            Square icon size in pixels.

    Returns:
        Pillow image instance.
    """
    canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    scale = size / 64
    line_width = max(2, int(round(5 * scale)))

    def scaled(bounds: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        return tuple(int(round(value * scale)) for value in bounds)

    draw.rounded_rectangle(
        scaled((6, 6, 58, 58)),
        radius=max(6, int(round(14 * scale))),
        fill='#0f766e',
    )
    draw.rounded_rectangle(
        scaled((10, 10, 54, 54)),
        radius=max(5, int(round(11 * scale))),
        outline='#5eead4',
        width=max(1, int(round(2 * scale))),
    )
    draw.arc(scaled((11, 20, 53, 57)), start=204, end=336, fill='white', width=line_width)
    draw.arc(scaled((20, 29, 44, 50)), start=210, end=330, fill='white', width=line_width)
    draw.ellipse(scaled((27, 41, 37, 51)), fill='#f8fafc')
    return canvas


def write_app_icon_file(icon_path: Path) -> Path:
    """
    Write the shared PolyFi icon to a multi-resolution Windows ICO file.

    Parameters:
        icon_path:
            Destination ICO path.

    Returns:
        Written icon path.
    """
    icon_path.parent.mkdir(parents=True, exist_ok=True)
    icon = create_app_icon_image(256)
    icon.save(
        icon_path,
        format='ICO',
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    return icon_path
