from __future__ import annotations

import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from platformdirs import PlatformDirs

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from wifi_pref_manager.paths import APP_AUTHOR, APP_NAME, APPDATA_ROOT_ENV_VAR, AppPaths


class AppPathsTests(unittest.TestCase):
    def test_custom_appdata_root_override_is_used_for_primary_files(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {APPDATA_ROOT_ENV_VAR: tmp_dir}, clear=False):
                paths = AppPaths()

        expected_root = Path(tmp_dir)
        self.assertEqual(paths.app_data_root, expected_root)
        self.assertEqual(paths.config_dir, expected_root)
        self.assertEqual(paths.local_data_dir, expected_root)
        self.assertEqual(paths.log_dir, expected_root / 'Logs')
        self.assertEqual(paths.config_file, expected_root / 'config.toml')
        self.assertEqual(paths.log_file, expected_root / 'Logs' / 'polyfi_ranked.log')

    def test_default_paths_use_platformdirs_when_override_is_blank(self) -> None:
        with patch.dict(os.environ, {APPDATA_ROOT_ENV_VAR: ''}, clear=False):
            paths = AppPaths()

        expected_root = Path(PlatformDirs(appname=APP_NAME, appauthor=APP_AUTHOR).user_config_dir)
        self.assertIsNone(paths.custom_appdata_root)
        self.assertEqual(paths.app_data_root, expected_root)
        self.assertEqual(paths.config_dir, expected_root)

    def test_start_menu_shortcut_uses_app_named_folder_and_tracks_legacy_path(self) -> None:
        with patch.dict(os.environ, {APPDATA_ROOT_ENV_VAR: ''}, clear=False):
            paths = AppPaths()

        self.assertEqual(paths.start_menu_folder.name, APP_NAME)
        self.assertEqual(paths.start_menu_shortcut_file.parent, paths.start_menu_folder)
        self.assertEqual(paths.legacy_start_menu_folder.name, APP_AUTHOR)
        self.assertEqual(paths.legacy_start_menu_shortcut_file.parent, paths.legacy_start_menu_folder)


if __name__ == '__main__':
    unittest.main()
