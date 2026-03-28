"""
Author:
    Inspyre Softworks

Project:
    PolyFi: Ranked

File:
    config.py

Description:
    TOML-backed configuration loading for PolyFi: Ranked.

Functions:
    save_config:
        Persist an AppConfig instance to a TOML file.

Constants:
    DEFAULT_CONFIG_TEMPLATE:
        First-run configuration file contents.

Dependencies:
    pathlib
    tomllib
    wifi_pref_manager.models
    wifi_pref_manager.paths

Example Usage:
    loader = ConfigLoader()
    config = loader.load()
"""

from __future__ import annotations

from pathlib import Path
import tomllib

from wifi_pref_manager.models import AppConfig, WiFiProfilePreference
from wifi_pref_manager.paths import AppPaths


DEFAULT_CONFIG_TEMPLATE = """[general]
scan_interval = 10
connect_timeout = 8
sync_profile_order_on_start = true
log_level = 'INFO'
log_file = ''
interface_name = ''
start_minimized_to_tray = false
auto_disable_wifi_on_ethernet = false

[[networks]]
ssid = 'MyBestWiFi'
auto_switch = true

[[networks]]
ssid = 'MySecondChoice'
auto_switch = true

[[networks]]
ssid = 'PhoneHotspot'
auto_switch = true
"""


class ConfigError(RuntimeError):
    """Raised when configuration is invalid or missing."""


class ConfigLoader:
    """
    Loads and validates TOML configuration.

    Methods:
        load:
            Load an AppConfig from disk.
        ensure_default_config:
            Create a default configuration file if one does not exist.
        has_changed:
            Determine whether the configuration file has changed.
    """

    def __init__(self, config_path: str | Path | None = None) -> None:
        """
        Parameters:
            config_path:
                Optional custom configuration path.
        """
        self.paths = AppPaths()
        self.paths.ensure_directories()
        self.config_path = Path(config_path).expanduser() if config_path else self.paths.config_file
        self._last_mtime_ns: int | None = None

    def ensure_default_config(self) -> Path:
        """
        Ensure a usable configuration file exists.

        Returns:
            Path to the active configuration file.
        """
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.config_path.exists():
            self.config_path.write_text(DEFAULT_CONFIG_TEMPLATE, encoding='utf-8')

        if self.config_path != self.paths.example_config_file and not self.paths.example_config_file.exists():
            self.paths.example_config_file.write_text(DEFAULT_CONFIG_TEMPLATE, encoding='utf-8')

        self._last_mtime_ns = self.get_mtime_ns()
        return self.config_path

    def get_mtime_ns(self) -> int | None:
        """
        Get the current file modification timestamp.

        Returns:
            Nanosecond mtime value or None if the file is missing.
        """
        if not self.config_path.exists():
            return None
        return self.config_path.stat().st_mtime_ns

    def has_changed(self) -> bool:
        """
        Determine whether the configuration file has changed.

        Returns:
            True when the file timestamp differs from the cached value.
        """
        current_mtime = self.get_mtime_ns()
        return current_mtime is not None and current_mtime != self._last_mtime_ns

    def mark_loaded(self) -> None:
        """
        Cache the current file timestamp as the loaded version.
        """
        self._last_mtime_ns = self.get_mtime_ns()

    def load(self) -> AppConfig:
        """
        Load the application configuration.

        Returns:
            Parsed AppConfig instance.

        Raises:
            ConfigError:
                If the file is missing or invalid.
        """
        if not self.config_path.exists():
            raise ConfigError(
                f'Config file not found: {self.config_path}. '
                'A default config should have been created on first run.'
            )

        with self.config_path.open('rb') as handle:
            raw = tomllib.load(handle)

        general = raw.get('general', {})
        networks = raw.get('networks', [])

        preferred_networks = [
            WiFiProfilePreference(
                ssid=str(entry['ssid']).strip(),
                auto_switch=bool(entry.get('auto_switch', True)),
            )
            for entry in networks
            if str(entry.get('ssid', '')).strip()
        ]

        if not preferred_networks:
            raise ConfigError('At least one [[networks]] entry with an ssid is required.')

        interface_name = str(general.get('interface_name', '')).strip() or None
        log_file = str(general.get('log_file', '')).strip()
        if not log_file:
            log_file = str(self.paths.log_file)

        config = AppConfig(
            preferred_networks=preferred_networks,
            interface_name=interface_name,
            scan_interval=max(1, int(general.get('scan_interval', 10))),
            connect_timeout=max(1, int(general.get('connect_timeout', 8))),
            sync_profile_order_on_start=bool(general.get('sync_profile_order_on_start', True)),
            log_level=str(general.get('log_level', 'INFO')).upper(),
            log_file=log_file,
            start_minimized_to_tray=bool(general.get('start_minimized_to_tray', False)),
            auto_disable_wifi_on_ethernet=bool(general.get('auto_disable_wifi_on_ethernet', False)),
        )
        self.mark_loaded()
        return config


def save_config(config: AppConfig, config_path: Path) -> None:
    """
    Persist an AppConfig to a TOML file.

    Parameters:
        config:
            Application configuration to write.
        config_path:
            Destination path for the TOML file.
    """

    def _bool(value: bool) -> str:
        return 'true' if value else 'false'

    def _str(value: str) -> str:
        escaped = value.replace('\\', '\\\\').replace("'", "\\'")
        return f"'{escaped}'"

    lines: list[str] = [
        '[general]\n',
        f'scan_interval = {config.scan_interval}\n',
        f'connect_timeout = {config.connect_timeout}\n',
        f'sync_profile_order_on_start = {_bool(config.sync_profile_order_on_start)}\n',
        f'log_level = {_str(config.log_level)}\n',
        f'log_file = {_str(config.log_file)}\n',
        f'interface_name = {_str(config.interface_name or "")}\n',
        f'start_minimized_to_tray = {_bool(config.start_minimized_to_tray)}\n',
        f'auto_disable_wifi_on_ethernet = {_bool(config.auto_disable_wifi_on_ethernet)}\n',
    ]

    for network in config.preferred_networks:
        lines.append('\n[[networks]]\n')
        escaped_ssid = network.ssid.replace('\\', '\\\\').replace("'", "\\'")
        lines.append(f"ssid = '{escaped_ssid}'\n")
        lines.append(f'auto_switch = {_bool(network.auto_switch)}\n')

    config_path.write_text(''.join(lines), encoding='utf-8')
