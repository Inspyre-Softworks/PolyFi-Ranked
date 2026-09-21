from __future__ import annotations

import builtins
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from wifi_pref_manager.ui.splash import (
    DEFAULT_SPLASH_FILENAME,
    _bounded_image_size,
    _run_splash_for_duration,
    resolve_splash_image_path,
    show_startup_splash,
    startup_splash_available,
)

REAL_IMPORT = builtins.__import__


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


class SplashInspyreAdapterTests(unittest.TestCase):
    @patch('inspyre_splash.discover_splash_definitions')
    def test_startup_splash_available_uses_packaged_polyfi_definition(
        self,
        mock_discover_splash_definitions: Mock,
    ) -> None:
        mock_discover_splash_definitions.return_value = [object()]

        self.assertTrue(startup_splash_available())
        mock_discover_splash_definitions.assert_called_once_with(
            'wifi_pref_manager',
            name='intro',
            search_user_data=False,
        )

    @patch('builtins.__import__')
    def test_startup_splash_available_returns_false_when_inspyre_splash_import_fails(
        self,
        mock_import: Mock,
    ) -> None:
        logger = Mock()

        def _raising_import(name: str, *args: object, **kwargs: object) -> object:
            if name == 'inspyre_splash':
                raise ModuleNotFoundError('missing inspyre_splash')
            return REAL_IMPORT(name, *args, **kwargs)

        mock_import.side_effect = _raising_import

        self.assertFalse(startup_splash_available(logger=logger))
        logger.debug.assert_called_once()

    @patch('inspyre_splash.discover_splash_definitions', side_effect=RuntimeError('bad splash'))
    def test_startup_splash_available_returns_false_when_discovery_raises(
        self,
        mock_discover_splash_definitions: Mock,
    ) -> None:
        logger = Mock()

        self.assertFalse(startup_splash_available(logger=logger))
        mock_discover_splash_definitions.assert_called_once()
        logger.debug.assert_called_once()

    def test_bounded_image_size_limits_legacy_image_splash_dimensions(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            image_path = Path(tmp_dir) / 'large.png'
            Image.new('RGBA', (1800, 1200)).save(image_path)

            self.assertEqual(_bounded_image_size(image_path), (840, 560))

    def test_run_splash_for_duration_uses_inspyre_run_until(self) -> None:
        splash = Mock()

        _run_splash_for_duration(splash, 0)

        splash.run_until.assert_called_once()
        work = splash.run_until.call_args.args[0]
        self.assertIsNone(work())

    @patch('wifi_pref_manager.ui.splash._run_splash_for_duration')
    @patch('wifi_pref_manager.ui.splash._build_packaged_splash')
    def test_show_startup_splash_uses_packaged_definition_by_default(
        self,
        mock_build_packaged_splash: Mock,
        mock_run_splash_for_duration: Mock,
    ) -> None:
        splash = object()
        mock_build_packaged_splash.return_value = splash

        show_startup_splash(None, fade_in_ms=280, hold_ms=1100, fade_out_ms=280)

        mock_build_packaged_splash.assert_called_once_with()
        mock_run_splash_for_duration.assert_called_once_with(splash, 1100)

    @patch('wifi_pref_manager.ui.splash._run_splash_for_duration')
    @patch('wifi_pref_manager.ui.splash._build_image_splash')
    def test_show_startup_splash_uses_legacy_image_when_provided(
        self,
        mock_build_image_splash: Mock,
        mock_run_splash_for_duration: Mock,
    ) -> None:
        splash = object()
        image_path = Path(r'C:\splash.png')
        mock_build_image_splash.return_value = splash

        show_startup_splash(image_path, fade_in_ms=280, hold_ms=1100, fade_out_ms=280)

        mock_build_image_splash.assert_called_once_with(image_path)
        mock_run_splash_for_duration.assert_called_once_with(splash, 1100)


if __name__ == '__main__':
    unittest.main()
