"""
Author:
    Inspyre Softworks

Project:
    PolyFi: Ranked

File:
    paths.py

Description:
    Helpers for resolving platform-appropriate application directories.

Functions:
    None.

Constants:
    APP_AUTHOR:
        Project author string used for directory naming.
    APP_NAME:
        User-facing application name.
    APP_SLUG:
        Filesystem-friendly application slug.

Dependencies:
    pathlib
    platformdirs

Example Usage:
    from wifi_pref_manager.paths import AppPaths
    paths = AppPaths()
    print(paths.config_file)
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil

from platformdirs import PlatformDirs


APP_AUTHOR = 'Inspyre-Softworks'
APP_NAME = 'PolyFi-Ranked'
APP_SLUG = 'polyfi_ranked'
APP_USER_MODEL_ID = f'{APP_AUTHOR}.{APP_NAME}'


class AppPaths:
    """
    Resolve platform-appropriate application paths.

    Methods:
        ensure_directories:
            Create required directories.
    """

    def __init__(self) -> None:
        self.platform_dirs = PlatformDirs(appname=APP_NAME, appauthor=APP_AUTHOR)
        self.config_dir = Path(self.platform_dirs.user_config_dir)
        self.local_data_dir = Path(self.platform_dirs.user_data_dir)
        self.log_dir = Path(self.platform_dirs.user_log_dir)
        self.config_file = self.config_dir / 'config.toml'
        self.example_config_file = self.config_dir / 'config.example.toml'
        self.log_file = self.log_dir / 'polyfi_ranked.log'
        self.managed_interface_file = self.local_data_dir / 'managed_wifi_interface.json'
        self.speed_test_history_file = self.local_data_dir / 'speedtest_history.jsonl'
        self.start_menu_icon_file = self.local_data_dir / 'polyfi_ranked.ico'

        roaming_root = Path(os.environ.get('APPDATA', self.config_dir.parent))
        self.start_menu_programs_dir = roaming_root / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs'
        self.start_menu_folder = self.start_menu_programs_dir / APP_AUTHOR
        self.start_menu_shortcut_file = self.start_menu_folder / f'{APP_NAME}.lnk'
        self.first_tray_start_marker_file = self.local_data_dir / 'tray_started.flag'

        legacy_roaming_root = Path.home() / 'AppData' / 'Roaming'
        legacy_local_root = Path.home() / 'AppData' / 'Local'
        self.legacy_config_dir = legacy_roaming_root / APP_SLUG
        self.legacy_local_dir = legacy_local_root / APP_SLUG
        self.legacy_log_dir = self.legacy_local_dir / 'logs'
        self.legacy_config_file = self.legacy_config_dir / 'wifi_preferences.toml'
        self.legacy_example_config_file = self.legacy_config_dir / 'wifi_preferences.example.toml'
        self.legacy_log_file = self.legacy_log_dir / 'polyfi_ranked.log'
        self.legacy_managed_interface_file = self.legacy_local_dir / 'managed_wifi_interface.json'
        self.legacy_speed_test_history_file = self.legacy_local_dir / 'speedtest_history.jsonl'

    def migrate_legacy_files(self) -> None:
        """
        Move legacy app-data files into the current PlatformDirs layout.
        """
        migrations = (
            (self.legacy_config_file, self.config_file),
            (self.legacy_example_config_file, self.example_config_file),
            (self.legacy_log_file, self.log_file),
            (self.legacy_managed_interface_file, self.managed_interface_file),
            (self.legacy_speed_test_history_file, self.speed_test_history_file),
        )
        for legacy_path, new_path in migrations:
            if new_path.exists() or not legacy_path.exists():
                continue
            new_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(legacy_path), str(new_path))

    def ensure_directories(self) -> None:
        """
        Create required application directories.
        """
        self.migrate_legacy_files()
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.local_data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
