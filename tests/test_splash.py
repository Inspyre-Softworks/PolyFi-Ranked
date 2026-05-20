from __future__ import annotations

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from wifi_pref_manager.ui.splash import (
    DEFAULT_SPLASH_FILENAME,
    TRANSPARENT_KEY_RGB,
    _premultiply_bgra_bytes,
    _prepare_chroma_key_image,
    resolve_splash_image_path,
)


class _PathsStub:
    def __init__(self, local_data_dir: Path) -> None:
        self.local_data_dir = local_data_dir


class SplashPathResolutionTests(unittest.TestCase):
    def test_prefers_configured_splash_path(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            splash_file = Path(tmp_dir) / 'custom.png'
            splash_file.write_bytes(b'not-a-real-image')
            app_paths = _PathsStub(local_data_dir=Path(tmp_dir))

            resolved = resolve_splash_image_path(str(splash_file), app_paths)  # type: ignore[arg-type]
            self.assertEqual(resolved, splash_file)

    def test_falls_back_to_local_data_splash_file(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            splash_file = Path(tmp_dir) / DEFAULT_SPLASH_FILENAME
            splash_file.write_bytes(b'not-a-real-image')
            app_paths = _PathsStub(local_data_dir=Path(tmp_dir))

            resolved = resolve_splash_image_path('', app_paths)  # type: ignore[arg-type]
            self.assertEqual(resolved, splash_file)

    def test_missing_configured_path_falls_back_to_local_data_splash_file(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            splash_file = Path(tmp_dir) / DEFAULT_SPLASH_FILENAME
            splash_file.write_bytes(b'not-a-real-image')
            app_paths = _PathsStub(local_data_dir=Path(tmp_dir))

            resolved = resolve_splash_image_path(
                str(Path(tmp_dir) / 'missing_splash.png'),
                app_paths,  # type: ignore[arg-type]
            )
            self.assertEqual(resolved, splash_file)

    def test_returns_none_when_no_splash_candidate_exists(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            app_paths = _PathsStub(local_data_dir=Path(tmp_dir))
            with patch('wifi_pref_manager.ui.splash.Path.home', return_value=Path(tmp_dir)):
                resolved = resolve_splash_image_path(
                    str(Path(tmp_dir) / 'missing_splash.png'),
                    app_paths,  # type: ignore[arg-type]
                )
            self.assertIsNone(resolved)


class SplashImagePreparationTests(unittest.TestCase):
    def test_premultiply_bgra_bytes_preserves_alpha_and_channel_order(self) -> None:
        source = Image.new('RGBA', (1, 1), (10, 20, 30, 128))

        prepared = _premultiply_bgra_bytes(source)

        self.assertEqual(prepared, bytes((15, 10, 5, 128)))

    def test_prepare_chroma_key_image_maps_transparent_pixels_to_key_color(self) -> None:
        source = Image.new('RGBA', (2, 1), (0, 0, 0, 0))
        source.putpixel((1, 0), (0, 0, 0, 255))

        prepared = _prepare_chroma_key_image(source)

        self.assertEqual(prepared.mode, 'RGB')
        self.assertEqual(prepared.getpixel((0, 0)), TRANSPARENT_KEY_RGB)
        self.assertEqual(prepared.getpixel((1, 0)), (0, 0, 0))


if __name__ == '__main__':
    unittest.main()
