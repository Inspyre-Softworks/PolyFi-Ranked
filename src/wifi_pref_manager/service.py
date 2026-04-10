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
    time
    wifi_pref_manager.config
    wifi_pref_manager.models
    wifi_pref_manager.netsh_wifi

Example Usage:
    service = WiFiPreferenceService(config=config, wifi_api=api, logger=logger)
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

try:
    from easy_exit_calls import ExitCallHandler
except ImportError:  # pragma: no cover - optional dependency on Python 3.12+
    ExitCallHandler = None

from wifi_pref_manager.config import ConfigError, ConfigLoader
from wifi_pref_manager.managed_interface_state import ManagedInterfaceStateStore
from wifi_pref_manager.models import AppConfig, SpeedTestResult
from wifi_pref_manager.netsh_wifi import NetshError, NetshWiFiApi
from wifi_pref_manager.paths import AppPaths
from wifi_pref_manager.speedtest_history import SpeedTestHistoryWriter
from wifi_pref_manager.speedtest_runner import SpeedTestRunner


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
        self.paths = AppPaths()
        self.managed_interface_state_store = ManagedInterfaceStateStore(self.paths.managed_interface_file)
        self.speed_test_history_writer = SpeedTestHistoryWriter(logger=logger)
        self.speed_test_runner = SpeedTestRunner(logger=logger)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._wifi_disabled_by_ethernet: bool = False
        self._status_changed_callback: Callable[[], None] | None = None
        self._runtime_warning_callback: Callable[[str, str], None] | None = None
        self._wifi_adapter_disabled_callback: Callable[[list[str]], None] | None = None
        self._wifi_network_changed_callback: Callable[[str | None, str], None] | None = None
        self._speed_test_lock = threading.Lock()
        self._speed_test_thread: threading.Thread | None = None
        self._latest_speed_test_result = SpeedTestResult(
            status='waiting',
            message='Waiting for an active network connection.',
        )
        self._last_observed_ssid: str | None = None
        self._connected_ssid_since: float | None = None
        self._last_speed_test_attempt_ssid: str | None = None
        self._last_speed_test_at: float | None = None
        self._startup_wifi_adapter_enabled: bool | None = None
        self._startup_ssid: str | None = None
        self._last_known_wifi_ssid: str | None = None
        self._ethernet_disable_permission_warning_shown = False

        self.config.interface_name = self._resolve_managed_interface_name()
        if not self.config.speed_test_history_file:
            self.config.speed_test_history_file = str(self.paths.speed_test_history_file)
        self._capture_startup_network_state()
        self._register_exit_restore_handler()
        self._sync_speed_test_state_with_config()

    def _format_ethernet_connection_label(self, active_ethernet_interfaces: list[str]) -> str:
        """
        Build a human-readable speed-test label for the active Ethernet path.

        Parameters:
            active_ethernet_interfaces:
                Active Ethernet interface names.

        Returns:
            Ethernet connection label.
        """
        return f'Ethernet ({", ".join(active_ethernet_interfaces)})'

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

    def best_available_ssid(self, visible_networks: dict[str, int]) -> str | None:
        """
        Determine the highest-priority visible SSID.

        Parameters:
            visible_networks:
                Currently visible SSIDs mapped to their strongest observed dBm values.

        Returns:
            Best visible SSID or None.
        """
        for preference in self.config.preferred_networks:
            signal_dbm = visible_networks.get(preference.ssid)
            if signal_dbm is None:
                continue
            if not preference.auto_switch:
                continue
            min_db = preference.min_db
            if min_db is not None and signal_dbm < min_db:
                self.logger.debug(
                    'Ignoring %r because its signal (%s dBm) is below the configured minimum (%s dBm).',
                    preference.ssid,
                    signal_dbm,
                    min_db,
                )
                continue
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
        speed_tests_were_enabled = self.config.enable_speed_tests
        self.config = new_config

        if not self.config.interface_name:
            self.config.interface_name = previous_interface_name or self._resolve_managed_interface_name()
        if not self.config.speed_test_history_file:
            self.config.speed_test_history_file = str(self.paths.speed_test_history_file)

        if self.on_config_reloaded is not None:
            self.logger = self.on_config_reloaded(self.config)
            self.speed_test_runner.logger = self.logger
            self.speed_test_history_writer.logger = self.logger

        self.logger.info('Configuration reloaded from disk.')
        self.logger.debug('Updated preferred SSID order: %s', ', '.join(entry.ssid for entry in self.config.preferred_networks))
        self._sync_speed_test_state_with_config()

        if self.config.sync_profile_order_on_start:
            self.logger.debug('Re-syncing Windows Wi-Fi profile order after config reload...')
            self.wifi_api.sync_profile_order(
                interface_name=self.interface_name,
                ssids=[entry.ssid for entry in self.config.preferred_networks],
            )

        if not speed_tests_were_enabled and self.config.enable_speed_tests:
            self._start_immediate_speed_test_for_current_connection()

    def set_status_changed_callback(self, callback: Callable[[], None] | None) -> None:
        """
        Register a callback invoked when tray-visible status changes.

        Parameters:
            callback:
                Callback to invoke after status updates.
        """
        self._status_changed_callback = callback

    def set_runtime_warning_callback(self, callback: Callable[[str, str], None] | None) -> None:
        """
        Register a callback used for one-off runtime warning dialogs.

        Parameters:
            callback:
                Callback invoked with a title and message.
        """
        self._runtime_warning_callback = callback

    def set_wifi_adapter_disabled_callback(self, callback: Callable[[list[str]], None] | None) -> None:
        """
        Register a callback invoked when PolyFi disables the Wi-Fi adapter.

        Parameters:
            callback:
                Callback invoked with the active Ethernet interface names.
        """
        self._wifi_adapter_disabled_callback = callback

    def set_wifi_network_changed_callback(self, callback: Callable[[str | None, str], None] | None) -> None:
        """
        Register a callback invoked when the active Wi-Fi SSID changes.

        Parameters:
            callback:
                Callback invoked with the previous and new SSID.
        """
        self._wifi_network_changed_callback = callback

    def _capture_startup_network_state(self) -> None:
        """
        Snapshot the Wi-Fi adapter and SSID state present when the app starts.
        """
        self._startup_wifi_adapter_enabled = self.wifi_api.is_interface_enabled(self.interface_name)
        self._startup_ssid = self.wifi_api.get_current_ssid() if self._startup_wifi_adapter_enabled else None
        self._last_known_wifi_ssid = self._startup_ssid
        self.logger.debug(
            'Captured startup network state: adapter_enabled=%s, ssid=%r',
            self._startup_wifi_adapter_enabled,
            self._startup_ssid,
        )

    def _resolve_managed_interface_name(self) -> str:
        """
        Resolve the Wi-Fi interface name, falling back to persisted state.

        Returns:
            Managed Wi-Fi interface name.

        Raises:
            NetshError:
                If no Wi-Fi interface can be resolved.
        """
        if self.config.interface_name:
            interface_name = self.config.interface_name.strip()
            if interface_name:
                self.managed_interface_state_store.save(interface_name)
                self.logger.debug('Using configured Wi-Fi interface: %s', interface_name)
                return interface_name

        try:
            interface_name = self.wifi_api.detect_wifi_interface()
            self.managed_interface_state_store.save(interface_name)
            self.logger.debug(
                'Detected managed Wi-Fi interface %s and refreshed %s.',
                interface_name,
                self.paths.managed_interface_file,
            )
            return interface_name
        except NetshError:
            saved_state = self.managed_interface_state_store.load()
            if saved_state is None:
                raise

            self.logger.warning(
                'No active Wi-Fi interface detected. Falling back to saved managed interface %s from %s.',
                saved_state.interface_name,
                self.paths.managed_interface_file,
            )
            return saved_state.interface_name

    def _register_exit_restore_handler(self) -> None:
        """
        Register the startup-state restoration callback for process exit.
        """
        if ExitCallHandler is None:
            self.logger.warning('easy-exit-calls is unavailable; exit-state restoration is disabled.')
            return

        ExitCallHandler().register_handler(self.restore_startup_network_state)
        self.logger.debug('Registered startup network-state restoration with easy-exit-calls.')

    def _notify_status_changed(self) -> None:
        """
        Notify observers that tray-visible state has changed.
        """
        if self._status_changed_callback is None:
            return
        try:
            self._status_changed_callback()
        except Exception:  # noqa: BLE001
            self.logger.debug('Status-changed callback failed.', exc_info=True)

    def _notify_runtime_warning(self, title: str, message: str) -> None:
        """
        Notify observers about a runtime warning that should be surfaced to the user.

        Parameters:
            title:
                Short warning title.
            message:
                Human-readable warning details.
        """
        if self._runtime_warning_callback is not None:
            try:
                self._runtime_warning_callback(title, message)
                return
            except Exception:  # noqa: BLE001
                self.logger.debug('Runtime-warning callback failed.', exc_info=True)

        try:
            from wifi_pref_manager.ui.dialogs import show_dialog_async  # noqa: PLC0415

            show_dialog_async('warning', title, message)
        except Exception:  # noqa: BLE001
            self.logger.debug('Fallback runtime-warning dialog failed.', exc_info=True)

    def _notify_wifi_adapter_disabled(self, active_ethernet_interfaces: list[str]) -> None:
        """
        Notify observers that Wi-Fi was disabled because Ethernet became active.

        Parameters:
            active_ethernet_interfaces:
                Active Ethernet interface names.
        """
        if self._wifi_adapter_disabled_callback is None:
            return
        try:
            self._wifi_adapter_disabled_callback(active_ethernet_interfaces)
        except Exception:  # noqa: BLE001
            self.logger.debug('Wi-Fi-adapter-disabled callback failed.', exc_info=True)

    def _notify_wifi_network_changed(self, previous_ssid: str | None, new_ssid: str) -> None:
        """
        Notify observers that the active Wi-Fi SSID changed.

        Parameters:
            previous_ssid:
                Previously active SSID, if any.
            new_ssid:
                Newly active SSID.
        """
        if self._wifi_network_changed_callback is None:
            return
        try:
            self._wifi_network_changed_callback(previous_ssid, new_ssid)
        except Exception:  # noqa: BLE001
            self.logger.debug('Wi-Fi-network-changed callback failed.', exc_info=True)

    def _track_current_wifi_network(self, current_ssid: str | None, *, notify: bool = True) -> None:
        """
        Track the current Wi-Fi SSID and optionally notify when it changes.

        Parameters:
            current_ssid:
                Currently active Wi-Fi SSID.
            notify:
                Whether to emit a network-changed notification.
        """
        previous_ssid = self._last_known_wifi_ssid
        if current_ssid == previous_ssid:
            return
        self._last_known_wifi_ssid = current_ssid
        if notify and current_ssid is not None:
            self._notify_wifi_network_changed(previous_ssid, current_ssid)

    def _set_speed_test_result(self, result: SpeedTestResult) -> None:
        """
        Store the latest speed-test state and refresh the tray menu.

        Parameters:
            result:
                Latest speed-test state.
        """
        with self._speed_test_lock:
            self._latest_speed_test_result = result
        self._notify_status_changed()

    def _sync_speed_test_state_with_config(self) -> None:
        """
        Align runtime speed-test state with the current configuration.
        """
        if not self.config.enable_speed_tests:
            self._set_speed_test_result(
                SpeedTestResult(
                    status='disabled',
                    message='Speed tests disabled in config.',
                )
            )
            return

        with self._speed_test_lock:
            current_status = self._latest_speed_test_result.status

        if current_status == 'disabled':
            self._set_speed_test_result(
                SpeedTestResult(
                    status='waiting',
                    message='Waiting for an active network connection.',
                )
            )

    def restore_startup_network_state(self) -> None:
        """
        Restore the Wi-Fi adapter and SSID state captured at startup.
        """
        if self._startup_wifi_adapter_enabled is None:
            return

        self.logger.debug('Restoring startup network state before exit.')

        try:
            current_adapter_enabled = self.wifi_api.is_interface_enabled(self.interface_name)
        except NetshError as exc:
            self.logger.error('Could not determine current Wi-Fi adapter state during exit restore: %s', exc)
            return

        if self._startup_wifi_adapter_enabled and not current_adapter_enabled:
            self.logger.info('Restoring Wi-Fi adapter to enabled state.')
            try:
                self.enable_wifi_adapter()
            except NetshError as exc:
                self.logger.error('Failed to re-enable Wi-Fi adapter during exit restore: %s', exc)
                return
        elif not self._startup_wifi_adapter_enabled and current_adapter_enabled:
            self.logger.info('Restoring Wi-Fi adapter to disabled state.')
            try:
                self.wifi_api.disable_wifi_adapter(self.interface_name)
            except NetshError as exc:
                self.logger.error('Failed to disable Wi-Fi adapter during exit restore: %s', exc)
            return

        if not self._startup_wifi_adapter_enabled:
            return

        current_ssid = self.wifi_api.get_current_ssid()
        if self._startup_ssid:
            if current_ssid == self._startup_ssid:
                return

            self.logger.info('Restoring Wi-Fi connection to startup SSID %r.', self._startup_ssid)
            try:
                if current_ssid is not None:
                    self.wifi_api.disconnect(self.interface_name)
                self.wifi_api.connect(
                    interface_name=self.interface_name,
                    ssid=self._startup_ssid,
                    timeout=self.config.connect_timeout,
                )
            except NetshError as exc:
                self.logger.error('Failed to restore startup SSID %r: %s', self._startup_ssid, exc)
        elif current_ssid is not None:
            self.logger.info('Disconnecting Wi-Fi to restore the startup disconnected state.')
            try:
                self.wifi_api.disconnect(self.interface_name)
            except NetshError as exc:
                self.logger.error('Failed to restore startup disconnected state: %s', exc)

    def get_speed_test_status_text(self) -> str:
        """
        Return a compact tray-friendly summary of the latest speed-test state.

        Returns:
            Status text for the tray context menu.
        """
        with self._speed_test_lock:
            result = self._latest_speed_test_result

        if result.status == 'disabled':
            return 'Speed Test: Disabled'
        if result.status == 'running':
            return f'Speed Test: Running on {result.ssid or "current connection"}...'
        if result.status == 'success':
            return (
                f'Speed Test: {result.ssid or "Connection"} | '
                f'D {result.download_mbps:.1f} Mbps | '
                f'U {result.upload_mbps:.1f} Mbps | '
                f'P {result.ping_ms:.0f} ms'
            )
        if result.status == 'error':
            summary = result.message.strip() or 'Unknown error.'
            if len(summary) > 48:
                summary = f'{summary[:45]}...'
            return f'Speed Test: Failed on {result.ssid or "Connection"} ({summary})'
        return f'Speed Test: {result.message or "Waiting for a connection"}'

    def set_auto_disable_wifi_on_ethernet(self, enabled: bool) -> None:
        """
        Update the runtime Ethernet auto-detection setting.

        Parameters:
            enabled:
                Desired auto-detection state.
        """
        self.config.auto_disable_wifi_on_ethernet = enabled
        if not enabled:
            self._wifi_disabled_by_ethernet = False
            self.logger.warning('Ethernet detection disabled at runtime.')
        else:
            self._ethernet_disable_permission_warning_shown = False
            self.logger.info('Ethernet detection enabled at runtime.')

    def _handle_non_admin_ethernet_disable(
        self,
        active_ethernet_interfaces: list[str],
        exc: NetshError,
    ) -> None:
        """
        Handle the case where Ethernet auto-disable needs elevation.

        Parameters:
            active_ethernet_interfaces:
                Active Ethernet interface names.
            exc:
                Underlying adapter-disable failure.
        """
        interfaces = ', '.join(active_ethernet_interfaces) if active_ethernet_interfaces else 'Ethernet'
        self.logger.warning(
            'Ethernet auto-disable requires administrator rights on %s. '
            'Disabling that feature for this running instance: %s',
            interfaces,
            exc,
        )
        self.set_auto_disable_wifi_on_ethernet(False)

        if self._ethernet_disable_permission_warning_shown:
            return

        self._ethernet_disable_permission_warning_shown = True
        self._notify_runtime_warning(
            'Administrator Required',
            'PolyFi detected an active Ethernet connection, but Windows denied the Wi-Fi disable step because '
            'this app is not running as administrator.\n\n'
            'Automatic "disable Wi-Fi on Ethernet" has been turned off for this session. '
            'Restart PolyFi as administrator if you want this feature.',
        )

    def enable_wifi_adapter(self) -> None:
        """
        Re-enable the managed Wi-Fi adapter and clear Ethernet-disable state.
        """
        self.wifi_api.enable_wifi_adapter(self.interface_name)
        self._wifi_disabled_by_ethernet = False
        time.sleep(2)

    def _run_speed_test(self, connection_name: str, reason: str) -> None:
        """
        Run a speed test in the background for the specified connection.

        Parameters:
            connection_name:
                Human-readable label for the active connection.
            reason:
                Human-readable reason for the run.
        """
        self.logger.debug('Queueing speed test for %r (%s).', connection_name, reason)
        try:
            result = self.speed_test_runner.run(connection_name)
        except Exception as exc:  # noqa: BLE001
            self.logger.exception('Unexpected speed-test failure for %r: %s', connection_name, exc)
            result = SpeedTestResult(
                status='error',
                ssid=connection_name,
                message='Unexpected speed-test failure.',
                tested_at=time.time(),
            )

        if not self.config.enable_speed_tests:
            self.logger.debug('Speed test finished for %r, but speed tests are now disabled.', connection_name)
            return

        if self.config.save_speed_test_history:
            try:
                self.speed_test_history_writer.append(self.config.speed_test_history_file, result)
            except OSError as exc:
                self.logger.error('Failed to save speed-test history to %s: %s', self.config.speed_test_history_file, exc)

        self._set_speed_test_result(result)

    def _start_speed_test(self, connection_name: str, reason: str) -> None:
        """
        Start a background speed test immediately.

        Parameters:
            connection_name:
                Human-readable label for the active connection.
            reason:
                Human-readable reason for the run.
        """
        now = time.time()
        self._last_speed_test_attempt_ssid = connection_name
        self._last_speed_test_at = now
        self._set_speed_test_result(
            SpeedTestResult(
                status='running',
                ssid=connection_name,
                message=f'Running speed test on {connection_name}.',
            )
        )
        self._speed_test_thread = threading.Thread(
            target=self._run_speed_test,
            args=(connection_name, reason),
            daemon=True,
        )
        self._speed_test_thread.start()

    def _get_active_connection_name(self) -> str | None:
        """
        Resolve the currently active connection label for speed-test purposes.

        Returns:
            Wi-Fi SSID, Ethernet label, or None when no active connection is detected.
        """
        current_ssid = self.wifi_api.get_current_ssid()
        if current_ssid:
            return current_ssid

        active_ethernet_interfaces = self.wifi_api.get_active_ethernet_interfaces(self.interface_name)
        if active_ethernet_interfaces:
            return self._format_ethernet_connection_label(active_ethernet_interfaces)

        return None

    def _start_immediate_speed_test_for_current_connection(self) -> None:
        """
        Trigger a speed test immediately for the current active connection.
        """
        if self._speed_test_thread is not None and self._speed_test_thread.is_alive():
            self.logger.debug('Skipping immediate speed test because a speed test is already running.')
            return

        connection_name = self._get_active_connection_name()
        if connection_name is None:
            self._set_speed_test_result(
                SpeedTestResult(
                    status='waiting',
                    message='Waiting for an active network connection.',
                )
            )
            return

        self.logger.info('Speed tests enabled at runtime. Starting an immediate speed test for %r.', connection_name)
        self._start_speed_test(connection_name, 'speed tests enabled at runtime')

    def _maybe_schedule_speed_test(
        self,
        current_ssid: str | None,
        connection_changed: bool | None = None,
    ) -> None:
        """
        Start a background speed test when the config and connection state require it.

        Parameters:
            current_ssid:
                Human-readable label for the currently active connection.
            connection_changed:
                Optional explicit connection-change signal for immediate post-connect runs.
        """
        now = time.time()
        observed_change = current_ssid != self._last_observed_ssid if connection_changed is None else connection_changed

        if current_ssid != self._last_observed_ssid:
            self._connected_ssid_since = now if current_ssid is not None else None
        self._last_observed_ssid = current_ssid

        if not self.config.enable_speed_tests:
            return

        if current_ssid is None:
            with self._speed_test_lock:
                current_status = self._latest_speed_test_result.status
            if current_status not in {'success', 'error'}:
                self._set_speed_test_result(
                    SpeedTestResult(
                        status='waiting',
                        message='Waiting for an active network connection.',
                    )
                )
            return

        if self._speed_test_thread is not None and self._speed_test_thread.is_alive():
            return

        should_run = False
        reason = ''

        if observed_change and self.config.speed_test_on_new_connection:
            should_run = True
            reason = 'new network connection'
        elif self.config.speed_test_interval > 0:
            reference_time = (
                self._last_speed_test_at
                if self._last_speed_test_attempt_ssid == current_ssid and self._last_speed_test_at is not None
                else self._connected_ssid_since
            )
            if reference_time is not None and now - reference_time >= self.config.speed_test_interval:
                should_run = True
                reason = 'periodic interval reached'

        if not should_run:
            with self._speed_test_lock:
                current_status = self._latest_speed_test_result.status
            if current_status in {'waiting', 'disabled'}:
                self._set_speed_test_result(
                    SpeedTestResult(
                        status='waiting',
                        ssid=current_ssid,
                        message=f'Waiting to test {current_ssid}.',
                    )
                )
            return

        self._start_speed_test(current_ssid, reason)

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
            active_ethernet_interfaces = self.wifi_api.get_active_ethernet_interfaces(self.interface_name)
            ethernet_active = bool(active_ethernet_interfaces)
            self.logger.debug(
                'Ethernet connection check: active=%s, interfaces=%s',
                ethernet_active,
                ', '.join(active_ethernet_interfaces) if active_ethernet_interfaces else '[none]',
            )
            self.logger.debug(
                'Ethernet connection check state: _wifi_disabled_by_ethernet=%s',
                self._wifi_disabled_by_ethernet,
            )
            
            if ethernet_active:
                # Ethernet is connected - disable WiFi adapter completely
                if not self._wifi_disabled_by_ethernet:
                    self.logger.info(
                        'Ethernet connection detected on %s. Disabling Wi-Fi adapter completely.',
                        ', '.join(active_ethernet_interfaces),
                    )
                    try:
                        self.wifi_api.disable_wifi_adapter(self.interface_name)
                        self._wifi_disabled_by_ethernet = True
                        if self.config.show_wifi_disabled_dialog:
                            self._notify_wifi_adapter_disabled(active_ethernet_interfaces)
                    except NetshError as exc:
                        if NetshWiFiApi.is_elevation_required_error(exc):
                            self._handle_non_admin_ethernet_disable(active_ethernet_interfaces, exc)
                        else:
                            self.logger.error('Failed to disable Wi-Fi adapter: %s', exc)
                if self.config.auto_disable_wifi_on_ethernet:
                    self._maybe_schedule_speed_test(
                        self._format_ethernet_connection_label(active_ethernet_interfaces)
                    )
                    return
            else:
                # Ethernet is not connected - re-enable WiFi if it was disabled
                if self._wifi_disabled_by_ethernet:
                    self.logger.info('Ethernet disconnected. Re-enabling Wi-Fi adapter.')
                    try:
                        self.enable_wifi_adapter()
                    except NetshError as exc:
                        self.logger.error('Failed to re-enable Wi-Fi adapter: %s', exc)
                        # Clear the flag anyway to avoid getting stuck
                        self._wifi_disabled_by_ethernet = False

        current_ssid = self.wifi_api.get_current_ssid()
        self._track_current_wifi_network(current_ssid)
        visible_networks = self.wifi_api.get_visible_network_signals()
        best_available = self.best_available_ssid(visible_networks)

        self.logger.debug('Current SSID: %r', current_ssid)
        self.logger.debug(
            'Visible SSIDs: %s',
            ', '.join(f'{ssid} ({signal_dbm} dBm)' for ssid, signal_dbm in visible_networks.items())
            if visible_networks
            else '[none]',
        )
        self.logger.debug('Best available preferred SSID: %r', best_available)

        if best_available is None:
            self.logger.debug('No preferred network currently visible.')
            self._maybe_schedule_speed_test(current_ssid)
            return

        if current_ssid == best_available:
            self.logger.debug('Already connected to the best available network.')
            self._maybe_schedule_speed_test(current_ssid)
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
                self._track_current_wifi_network(best_available)
                self._maybe_schedule_speed_test(best_available, connection_changed=True)
            else:
                self.logger.warning('Connection attempt to %r could not be confirmed.', best_available)
                self._maybe_schedule_speed_test(self.wifi_api.get_current_ssid())
            return

        self._maybe_schedule_speed_test(current_ssid)

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
            active_ethernet_interfaces = self.wifi_api.get_active_ethernet_interfaces(self.interface_name)
            self.logger.info(
                'Ethernet detection: ENABLED. Active Ethernet interfaces right now: %s',
                ', '.join(active_ethernet_interfaces) if active_ethernet_interfaces else '[none]',
            )
        else:
            self.logger.warning(
                'Ethernet detection: DISABLED '
                '(auto_disable_wifi_on_ethernet = false in config). '
                'Set it to true to enable automatic Wi-Fi disable on Ethernet.'
            )
        if self.config.enable_speed_tests:
            self.logger.info(
                'Speed tests: ENABLED (on_new_connection=%s, interval=%ss, history=%s)',
                self.config.speed_test_on_new_connection,
                self.config.speed_test_interval,
                self.config.save_speed_test_history,
            )
        else:
            self.logger.info('Speed tests: DISABLED.')

        while not self._stop_event.is_set():
            try:
                self.reload_config_if_needed()
                self.evaluate_and_switch()
            except NetshError as exc:
                self.logger.error('Wi-Fi command error: %s', exc)
            except Exception as exc:  # noqa: BLE001
                self.logger.exception('Unexpected runtime error: %s', exc)

            self._stop_event.wait(self.config.scan_interval)
