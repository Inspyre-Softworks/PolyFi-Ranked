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


INSTALLER_WIZARD_IMAGE_SIZE = (240, 459)
INSTALLER_SMALL_IMAGE_SIZE = (147, 147)


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


def create_installer_wizard_image(
    size: tuple[int, int] = INSTALLER_WIZARD_IMAGE_SIZE,
) -> Image.Image:
    """
    Create branded side art for the Inno Setup wizard.

    Parameters:
        size:
            Requested wizard image size.

    Returns:
        Pillow image instance.
    """
    width, height = size
    canvas = Image.new('RGBA', size, '#f3fbfa')
    draw = ImageDraw.Draw(canvas, 'RGBA')

    draw.rounded_rectangle(
        (14, 14, width - 14, height - 14),
        radius=34,
        outline=(94, 234, 212, 140),
        width=3,
    )
    draw.ellipse(
        (-int(width * 0.3), int(height * 0.52), int(width * 0.72), int(height * 1.45)),
        fill=(15, 118, 110, 48),
    )
    draw.ellipse(
        (int(width * 0.28), -int(height * 0.1), int(width * 1.08), int(height * 0.72)),
        fill=(94, 234, 212, 74),
    )
    draw.rounded_rectangle(
        (26, int(height * 0.66), width - 26, height - 28),
        radius=26,
        fill=(15, 118, 110, 220),
    )

    icon_size = min(int(width * 0.58), 144)
    icon = create_app_icon_image(icon_size)
    icon_x = (width - icon_size) // 2
    icon_y = 44
    canvas.alpha_composite(icon, (icon_x, icon_y))

    signal_bounds = (
        int(width * 0.23),
        int(height * 0.73),
        int(width * 0.77),
        int(height * 0.98),
    )
    for inset, stroke_alpha in ((0, 230), (20, 215), (40, 200)):
        left, top, right, bottom = signal_bounds
        draw.arc(
            (left + inset, top + inset, right - inset, bottom - inset),
            start=204,
            end=336,
            fill=(248, 250, 252, stroke_alpha),
            width=7,
        )
    dot_size = 18
    draw.ellipse(
        (
            (width - dot_size) // 2,
            int(height * 0.88),
            (width + dot_size) // 2,
            int(height * 0.88) + dot_size,
        ),
        fill=(248, 250, 252, 255),
    )
    return canvas


def create_installer_small_image(
    size: tuple[int, int] = INSTALLER_SMALL_IMAGE_SIZE,
) -> Image.Image:
    """
    Create branded top-right art for the Inno Setup wizard.

    Parameters:
        size:
            Requested wizard small-image size.

    Returns:
        Pillow image instance.
    """
    width, height = size
    canvas = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas, 'RGBA')
    draw.rounded_rectangle(
        (10, 10, width - 10, height - 10),
        radius=26,
        fill=(243, 251, 250, 255),
        outline=(94, 234, 212, 190),
        width=3,
    )
    draw.ellipse(
        (22, 22, width - 22, height - 22),
        fill=(15, 118, 110, 30),
    )
    icon_size = min(width, height) - 42
    icon = create_app_icon_image(icon_size)
    icon_x = (width - icon_size) // 2
    icon_y = (height - icon_size) // 2
    canvas.alpha_composite(icon, (icon_x, icon_y))
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


def write_installer_art_files(output_dir: Path) -> dict[str, Path]:
    """
    Write the installer-facing icon and wizard artwork files.

    Parameters:
        output_dir:
            Destination directory for generated assets.

    Returns:
        Mapping of generated asset names to written paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    setup_icon_path = output_dir / 'polyfi-ranked-setup.ico'
    wizard_image_path = output_dir / 'polyfi-ranked-wizard.png'
    wizard_small_image_path = output_dir / 'polyfi-ranked-wizard-small.png'

    write_app_icon_file(setup_icon_path)
    create_installer_wizard_image().save(wizard_image_path, format='PNG')
    create_installer_small_image().save(wizard_small_image_path, format='PNG')

    return {
        'setup_icon': setup_icon_path,
        'wizard_image': wizard_image_path,
        'wizard_small_image': wizard_small_image_path,
    }
