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
auto_disable_wifi_on_ethernet = true
show_wifi_disabled_dialog = true
enable_speed_tests = false
speed_test_on_new_connection = true
speed_test_interval = 1800
save_speed_test_history = false
speed_test_history_file = ''

[[networks]]
ssid = 'MyBestWiFi'
auto_switch = true
# min_db = -72

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
        write_default_config:
            Write the current default configuration template to disk.
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

    def write_default_config(self, overwrite: bool = False) -> Path:
        """
        Write the default configuration template to the active config path.

        Parameters:
            overwrite:
                Whether an existing file may be replaced.

        Returns:
            Path to the written configuration file.

        Raises:
            ConfigError:
                If the destination already exists and overwrite is False.
        """
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        if self.config_path.exists() and not overwrite:
            raise ConfigError(
                f'Config file already exists: {self.config_path}. '
                'Use overwrite=True to replace it.'
            )

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
                min_db=(
                    int(entry.get('min_db', entry.get('minimum_signal_dbm')))
                    if entry.get('min_db', entry.get('minimum_signal_dbm')) not in (None, '')
                    else None
                ),
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
        speed_test_history_file = str(general.get('speed_test_history_file', '')).strip()
        if not speed_test_history_file:
            speed_test_history_file = str(self.paths.speed_test_history_file)

        config = AppConfig(
            preferred_networks=preferred_networks,
            interface_name=interface_name,
            scan_interval=max(1, int(general.get('scan_interval', 10))),
            connect_timeout=max(1, int(general.get('connect_timeout', 8))),
            sync_profile_order_on_start=bool(general.get('sync_profile_order_on_start', True)),
            log_level=str(general.get('log_level', 'INFO')).upper(),
            log_file=log_file,
            start_minimized_to_tray=bool(general.get('start_minimized_to_tray', False)),
            auto_disable_wifi_on_ethernet=bool(general.get('auto_disable_wifi_on_ethernet', True)),
            show_wifi_disabled_dialog=bool(general.get('show_wifi_disabled_dialog', True)),
            enable_speed_tests=bool(general.get('enable_speed_tests', False)),
            speed_test_on_new_connection=bool(general.get('speed_test_on_new_connection', True)),
            speed_test_interval=max(0, int(general.get('speed_test_interval', 1800))),
            save_speed_test_history=bool(general.get('save_speed_test_history', False)),
            speed_test_history_file=speed_test_history_file,
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
        f'show_wifi_disabled_dialog = {_bool(config.show_wifi_disabled_dialog)}\n',
        f'enable_speed_tests = {_bool(config.enable_speed_tests)}\n',
        f'speed_test_on_new_connection = {_bool(config.speed_test_on_new_connection)}\n',
        f'speed_test_interval = {config.speed_test_interval}\n',
        f'save_speed_test_history = {_bool(config.save_speed_test_history)}\n',
        f'speed_test_history_file = {_str(config.speed_test_history_file)}\n',
    ]

    for network in config.preferred_networks:
        lines.append('\n[[networks]]\n')
        escaped_ssid = network.ssid.replace('\\', '\\\\').replace("'", "\\'")
        lines.append(f"ssid = '{escaped_ssid}'\n")
        lines.append(f'auto_switch = {_bool(network.auto_switch)}\n')
        if network.min_db is not None:
            lines.append(f'min_db = {network.min_db}\n')

    config_path.write_text(''.join(lines), encoding='utf-8')
