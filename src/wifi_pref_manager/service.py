"""
Author:
    Inspyre Softworks

Project:
    PolyFi: Ranked

File:
    service.py

Description:
    Core Wi-Fi preference management loop.

Functions:
    None.

Constants:
    None.

Dependencies:
    logging
    threading
    wifi_pref_manager.config
    wifi_pref_manager.models
    wifi_pref_manager.netsh_wifi

Example Usage:
    service = WiFiPreferenceService(config=config, wifi_api=api, logger=logger)
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from wifi_pref_manager.config import ConfigError, ConfigLoader
from wifi_pref_manager.models import AppConfig
from wifi_pref_manager.netsh_wifi import NetshError, NetshWiFiApi


class WiFiPreferenceService:
    """
    Background service that keeps the system attached to the highest-priority
    available configured Wi-Fi network.

    Methods:
        start:
            Start the background thread.
        stop:
            Stop the background thread.
        run_forever:
            Run the polling loop in the current thread.
        evaluate_and_switch:
            Perform a single preference evaluation.
        reload_config:
            Apply a freshly loaded configuration at runtime.
    """

    def __init__(
        self,
        config: AppConfig,
        wifi_api: NetshWiFiApi,
        logger: logging.Logger,
        config_loader: ConfigLoader | None = None,
        on_config_reloaded: Callable[[AppConfig], logging.Logger] | None = None,
    ) -> None:
        """
        Parameters:
            config:
                Application configuration.
            wifi_api:
                Windows Wi-Fi API wrapper.
            logger:
                Application logger.
            config_loader:
                Optional configuration loader used for hot reload checks.
            on_config_reloaded:
                Optional callback invoked after config reload.
        """
        self.config = config
        self.wifi_api = wifi_api
        self.logger = logger
        self.config_loader = config_loader
        self.on_config_reloaded = on_config_reloaded
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._wifi_disabled_by_ethernet: bool = False

        if not self.config.interface_name:
            self.config.interface_name = self.wifi_api.detect_wifi_interface()

    @property
    def interface_name(self) -> str:
        """Return the active wireless interface name."""
        if not self.config.interface_name:
            raise NetshError('No interface name resolved.')
        return self.config.interface_name

    def start(self) -> None:
        """Start the service in a daemon thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self.run_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Signal the service loop to stop."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def preference_index(self, ssid: str | None) -> int:
        """
        Get the configured rank for an SSID.

        Parameters:
            ssid:
                SSID to rank.

        Returns:
            Rank index, where lower is better.
        """
        if ssid is None:
            return 10**9

        for index, preference in enumerate(self.config.preferred_networks):
            if preference.ssid == ssid:
                return index

        return 10**9

    def best_available_ssid(self, visible_ssids: list[str]) -> str | None:
        """
        Determine the highest-priority visible SSID.

        Parameters:
            visible_ssids:
                Currently visible SSIDs.

        Returns:
            Best visible SSID or None.
        """
        visible_set = set(visible_ssids)
        for preference in self.config.preferred_networks:
            if preference.auto_switch and preference.ssid in visible_set:
                return preference.ssid
        return None

    def reload_config(self, new_config: AppConfig) -> None:
        """
        Apply a freshly loaded configuration without restarting the process.

        Parameters:
            new_config:
                New configuration object.
        """
        previous_interface_name = self.config.interface_name
        self.config = new_config

        if not self.config.interface_name:
            self.config.interface_name = previous_interface_name or self.wifi_api.detect_wifi_interface()

        if self.on_config_reloaded is not None:
            self.logger = self.on_config_reloaded(self.config)

        self.logger.info('Configuration reloaded from disk.')
        self.logger.info('Updated preferred SSID order: %s', ', '.join(entry.ssid for entry in self.config.preferred_networks))

        if self.config.sync_profile_order_on_start:
            self.logger.info('Re-syncing Windows Wi-Fi profile order after config reload...')
            self.wifi_api.sync_profile_order(
                interface_name=self.interface_name,
                ssids=[entry.ssid for entry in self.config.preferred_networks],
            )

    def reload_config_if_needed(self) -> None:
        """
        Reload configuration when the config file changes.
        """
        if self.config_loader is None or not self.config_loader.has_changed():
            return

        try:
            new_config = self.config_loader.load()
        except ConfigError as exc:
            self.logger.error('Config reload failed; keeping previous config: %s', exc)
            return

        self.reload_config(new_config)

    def evaluate_and_switch(self) -> None:
        """
        Perform one scan/evaluation cycle.

        Raises:
            NetshError:
                If netsh operations fail.
        """
        if self.config.auto_disable_wifi_on_ethernet:
            ethernet_active = self.wifi_api.is_ethernet_connected(self.interface_name)
            self.logger.debug('Ethernet connection check: ethernet_active=%s, _wifi_disabled_by_ethernet=%s',
                            ethernet_active, self._wifi_disabled_by_ethernet)
            
            if ethernet_active:
                # Ethernet is connected - disable WiFi adapter completely
                if not self._wifi_disabled_by_ethernet:
                    self.logger.info('Ethernet connection detected. Disabling Wi-Fi adapter completely.')
                    try:
                        self.wifi_api.disable_wifi_adapter(self.interface_name)
                        self._wifi_disabled_by_ethernet = True
                    except NetshError as exc:
                        self.logger.error('Failed to disable Wi-Fi adapter: %s', exc)
                return
            else:
                # Ethernet is not connected - re-enable WiFi if it was disabled
                if self._wifi_disabled_by_ethernet:
                    self.logger.info('Ethernet disconnected. Re-enabling Wi-Fi adapter.')
                    try:
                        self.wifi_api.enable_wifi_adapter(self.interface_name)
                        self._wifi_disabled_by_ethernet = False
                        # Give the adapter a moment to come back up
                        import time
                        time.sleep(2)
                    except NetshError as exc:
                        self.logger.error('Failed to re-enable Wi-Fi adapter: %s', exc)
                        # Clear the flag anyway to avoid getting stuck
                        self._wifi_disabled_by_ethernet = False

        current_ssid = self.wifi_api.get_current_ssid()
        visible_ssids = self.wifi_api.get_visible_ssids()
        best_available = self.best_available_ssid(visible_ssids)

        self.logger.info('Current SSID: %r', current_ssid)
        self.logger.info('Visible SSIDs: %s', ', '.join(visible_ssids) if visible_ssids else '[none]')
        self.logger.info('Best available preferred SSID: %r', best_available)

        if best_available is None:
            self.logger.info('No preferred network currently visible.')
            return

        if current_ssid == best_available:
            self.logger.info('Already connected to the best available network.')
            return

        current_rank = self.preference_index(current_ssid)
        best_rank = self.preference_index(best_available)

        if current_ssid is None or best_rank < current_rank:
            if current_ssid is not None:
                self.logger.info(
                    'Switching from %r to more preferred network %r',
                    current_ssid,
                    best_available,
                )
                self.wifi_api.disconnect(self.interface_name)
            else:
                self.logger.info('No active Wi-Fi connection. Connecting to %r', best_available)

            success = self.wifi_api.connect(
                interface_name=self.interface_name,
                ssid=best_available,
                timeout=self.config.connect_timeout,
            )
            if success:
                self.logger.info('Connected to %r', best_available)
            else:
                self.logger.warning('Connection attempt to %r could not be confirmed.', best_available)

    def run_forever(self) -> None:
        """
        Run the monitoring loop in the current thread.
        """
        self.logger.info('Using interface: %s', self.interface_name)

        if self.config.sync_profile_order_on_start:
            self.logger.info('Syncing Windows Wi-Fi profile order...')
            self.wifi_api.sync_profile_order(
                interface_name=self.interface_name,
                ssids=[entry.ssid for entry in self.config.preferred_networks],
            )

        self.logger.info('Wi-Fi preference service started.')
        if self.config.auto_disable_wifi_on_ethernet:
            self.logger.info('Ethernet detection: ENABLED — Wi-Fi will be disconnected when Ethernet is active.')
        else:
            self.logger.warning(
                'Ethernet detection: DISABLED '
                '(auto_disable_wifi_on_ethernet = false in config). '
                'Set it to true to enable automatic Wi-Fi disable on Ethernet.'
            )

        while not self._stop_event.is_set():
            try:
                self.reload_config_if_needed()
                self.evaluate_and_switch()
            except NetshError as exc:
                self.logger.error('Wi-Fi command error: %s', exc)
            except Exception as exc:  # noqa: BLE001
                self.logger.exception('Unexpected runtime error: %s', exc)

            self._stop_event.wait(self.config.scan_interval)
