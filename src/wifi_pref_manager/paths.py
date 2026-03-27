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
    os
    pathlib

Example Usage:
    from wifi_pref_manager.paths import AppPaths
    paths = AppPaths()
    print(paths.config_file)
"""

from __future__ import annotations

import os
from pathlib import Path


APP_AUTHOR = 'Inspyre Softworks'
APP_NAME = 'PolyFi Ranked'
APP_SLUG = 'polyfi_ranked'


class AppPaths:
    """
    Resolve platform-appropriate application paths.

    Methods:
        ensure_directories:
            Create required directories.
    """

    def __init__(self) -> None:
        self.roaming_root = self._get_roaming_root()
        self.local_root = self._get_local_root()
        self.config_dir = self.roaming_root / APP_SLUG
        self.log_dir = self.local_root / APP_SLUG / 'logs'
        self.config_file = self.config_dir / 'wifi_preferences.toml'
        self.example_config_file = self.config_dir / 'wifi_preferences.example.toml'
        self.log_file = self.log_dir / 'polyfi_ranked.log'

    def _get_roaming_root(self) -> Path:
        """
        Get the roaming application-data root.

        Returns:
            Path to the roaming application-data directory.
        """
        return Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming'))

    def _get_local_root(self) -> Path:
        """
        Get the local application-data root.

        Returns:
            Path to the local application-data directory.
        """
        return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))

    def ensure_directories(self) -> None:
        """
        Create required application directories.
        """
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
