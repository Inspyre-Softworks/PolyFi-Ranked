"""
Startup splash-screen helpers.
"""

from __future__ import annotations

from pathlib import Path
import time

from PIL import Image

from wifi_pref_manager.paths import AppPaths


DEFAULT_SPLASH_FILENAME = 'polyfi_ranked_splash.png'
DEFAULT_SPLASH_NAME = 'intro'
_MAX_IMAGE_SPLASH_SIZE = (900, 560)


def resolve_splash_image_path(configured_path: str, app_paths: AppPaths) -> Path | None:
    """
    Resolve a legacy single-image splash path from config and common defaults.

    Parameters:
        configured_path:
            Configured splash image path.
        app_paths:
            Application paths helper.

    Returns:
        Existing splash image path, or ``None`` if no single-image candidate exists.
    """
    configured = configured_path.strip()
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.exists():
            return candidate

    candidates = [
        app_paths.local_data_dir / DEFAULT_SPLASH_FILENAME,
        Path.home() / 'OneDrive' / 'Pictures' / DEFAULT_SPLASH_FILENAME,
        Path.home() / 'Pictures' / DEFAULT_SPLASH_FILENAME,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def startup_splash_available(name: str = DEFAULT_SPLASH_NAME) -> bool:
    """Return whether InspyreSplash can build PolyFi's packaged splash."""
    from inspyre_splash import discover_splash_definitions

    return bool(
        discover_splash_definitions(
            'wifi_pref_manager',
            name=name,
            search_user_data=False,
        )
    )


def show_startup_splash(
    image_path: Path | None = None,
    *,
    fade_in_ms: int,
    hold_ms: int,
    fade_out_ms: int,
) -> None:
    """
    Show the startup splash briefly, then close it.

    A configured image path is rendered as a single InspyreSplash image layer
    for compatibility with older configs. Without a single-image override,
    PolyFi uses the packaged InspyreSplash ``intro`` definition.
    """
    del fade_in_ms
    del fade_out_ms

    splash = _build_image_splash(image_path) if image_path is not None else _build_packaged_splash()
    _run_splash_for_duration(splash, hold_ms)


def _build_packaged_splash():
    from inspyre_splash import auto_splash

    splash = auto_splash(
        'wifi_pref_manager',
        name=DEFAULT_SPLASH_NAME,
        search_user_data=False,
    )
    if splash is None:
        msg = f'Packaged InspyreSplash definition was not found: {DEFAULT_SPLASH_NAME}'
        raise FileNotFoundError(msg)
    return splash


def _build_image_splash(image_path: Path):
    from inspyre_splash import Splash
    from inspyre_splash.layers import ImageLayer

    width, height = _bounded_image_size(image_path)
    splash = Splash(width=width, height=height, transparent=True, stay_on_top=True)
    splash.add_layer(ImageLayer(image_path, scale=1.0, position='center'))
    return splash


def _bounded_image_size(image_path: Path) -> tuple[int, int]:
    with Image.open(image_path) as image:
        width, height = image.size

    max_width, max_height = _MAX_IMAGE_SPLASH_SIZE
    if width <= max_width and height <= max_height:
        return width, height

    scale = min(max_width / width, max_height / height)
    return max(1, int(width * scale)), max(1, int(height * scale))


def _run_splash_for_duration(splash: object, hold_ms: int) -> None:
    duration_seconds = max(0, hold_ms) / 1000.0

    def wait_for_duration() -> None:
        if duration_seconds > 0:
            time.sleep(duration_seconds)

    run_until = getattr(splash, 'run_until')
    run_until(wait_for_duration)
