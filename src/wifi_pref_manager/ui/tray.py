"""
Author:
    Inspyre Softworks

Project:
    PolyFi: Ranked

File:
    tray.py

Description:
    Minimal system tray integration for controlling the Wi-Fi preference service.

Functions:
    None.

Constants:
    None.

Dependencies:
    pystray
    PIL
    wifi_pref_manager.service
    wifi_pref_manager.ui.settings (lazy import)

Example Usage:
    tray = TrayApplication(service=service, config_loader=loader, logger=logger)
    tray.run()
"""

from __future__ import annotations

from dataclasses import replace
import logging
from pathlib import Path
import sys
import threading
import time
from typing import TYPE_CHECKING, Callable
import webbrowser

from PIL import Image
import pystray

from wifi_pref_manager import __version__
from wifi_pref_manager.config import ConfigLoader, save_config
from wifi_pref_manager.icon_assets import create_app_icon_image
from wifi_pref_manager.models import AppConfig, ETHERNET_WIFI_MODE_DISABLE_ADAPTER, ETHERNET_WIFI_MODE_DISCONNECT
from wifi_pref_manager.paths import APP_NAME
from wifi_pref_manager.service import WiFiPreferenceService
from wifi_pref_manager.startup_trace import append_startup_trace_line
from wifi_pref_manager.ui.dialogs import show_custom_dialog_async, show_dialog_async, show_native_message_box
from wifi_pref_manager.updates import (
    DOCS_URL,
    GITHUB_REPOSITORY_URL,
    UpdateError,
    UpdateInfo,
    UpdateManager,
)

if TYPE_CHECKING:
    from wifi_pref_manager.ui.settings import SettingsWindow


class TrayApplication:
    """
    Minimal Windows system tray UI.

    Methods:
        run:
            Launch the tray icon event loop.
    """

    # Seconds to wait for the pystray setup callback before showing a diagnostic.
    _TRAY_SETUP_TIMEOUT: float = 30.0
    _TRAY_UNEXPECTED_EXIT_THRESHOLD: float = 5.0
    _TRAY_UNEXPECTED_EXIT_MAX_RETRIES: int = 2
    _TRAY_UNEXPECTED_EXIT_RETRY_DELAY: float = 3.0

    def __init__(
        self,
        service: WiFiPreferenceService,
        logger: logging.Logger,
        config_loader: ConfigLoader | None = None,
        needs_admin_notification: bool = False,
        show_output_console_callback: Callable[[], None] | None = None,
        startup_marker_path: Path | None = None,
        startup_trace_path: Path | None = None,
        post_icon_ready_callback: Callable[[], None] | None = None,
    ) -> None:
        self.service = service
        self.logger = logger
        self.config_loader = config_loader
        self._needs_admin_notification = needs_admin_notification
        self.show_output_console_callback = show_output_console_callback
        self._startup_marker_path = startup_marker_path
        self._startup_trace_path = startup_trace_path
        self._post_icon_ready_callback = post_icon_ready_callback
        self.icon: pystray.Icon | None = None
        self._settings_window: SettingsWindow | None = None
        self._icon_ready_event: threading.Event | None = None
        self._icon_run_done_event: threading.Event | None = None
        self._update_check_lock = threading.Lock()
        self._update_check_in_progress = False
        self.update_manager = UpdateManager()
        self._quit_requested = False
        self.service.set_status_changed_callback(self.refresh_menu)
        self.service.set_runtime_warning_callback(self.show_runtime_warning)
        self.service.set_wifi_adapter_disabled_callback(self.show_wifi_adapter_disabled_dialog)
        self.service.set_wifi_network_changed_callback(self.show_wifi_network_changed_notification)

    def create_image(self) -> Image.Image:
        """
        Create a simple tray icon image.

        Returns:
            Pillow image instance.
        """
        return create_app_icon_image(64)

    def _append_startup_trace(self, message: str) -> None:
        """
        Append a tray-startup diagnostic line when a trace file is configured.

        Parameters:
            message:
                Diagnostic message to record.
        """
        if self._startup_trace_path is None:
            return
        try:
            append_startup_trace_line(self._startup_trace_path, f'tray:{message}')
        except OSError:
            return

    def on_rescan(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        """
        Trigger an immediate preference evaluation.
        """
        del icon, item
        self.logger.info('Manual rescan requested from tray.')
        self.service.reload_config_if_needed()
        self.service.evaluate_and_switch()

    def on_reenable_wifi(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        """
        Disable Ethernet auto-detection, re-enable Wi-Fi, and rescan.
        """
        del icon, item
        self.reenable_wifi_adapter_and_disable_auto_ethernet()

    def _save_and_reload_config(self, new_config: AppConfig) -> bool:
        """
        Persist and apply an updated config object.

        Parameters:
            new_config:
                Updated config object to persist.

        Returns:
            True when the config was applied successfully.
        """
        if self.config_loader is not None:
            try:
                save_config(new_config, self.config_loader.config_path)
                self.config_loader.mark_loaded()
            except OSError as exc:
                self.logger.error('Failed to save updated config: %s', exc)
                show_dialog_async(
                    'error',
                    'Save Failed',
                    f'Could not update the configuration file:\n\n{exc}',
                )
                return False

        self.service.reload_config(new_config)
        return True

    def disable_auto_ethernet_feature(self) -> bool:
        """
        Turn off automatic Ethernet Wi-Fi action and persist the change.

        Returns:
            True when the runtime/config update succeeded.
        """
        new_config = replace(self.service.config, auto_disable_wifi_on_ethernet=False)
        if not self._save_and_reload_config(new_config):
            return False
        self.service.set_auto_disable_wifi_on_ethernet(False)
        self.logger.info('Disabled automatic Wi-Fi Ethernet action from the tray UI.')
        return True

    def suppress_wifi_disabled_dialog(self) -> None:
        """
        Persist the preference to suppress future Wi-Fi-disabled dialogs.
        """
        if not self.service.config.show_wifi_disabled_dialog:
            return
        new_config = replace(self.service.config, show_wifi_disabled_dialog=False)
        if self._save_and_reload_config(new_config):
            self.logger.info('Suppressed future Wi-Fi-disabled dialogs.')

    def reenable_wifi_adapter_and_disable_auto_ethernet(self) -> None:
        """
        Disable Ethernet auto-detection, then restore Wi-Fi behavior and rescan.
        """
        self.logger.warning('Tray recovery requested: disabling Ethernet auto-detection and restoring Wi-Fi.')
        if not self.disable_auto_ethernet_feature():
            return

        mode = getattr(self.service.config, 'ethernet_wifi_mode', ETHERNET_WIFI_MODE_DISCONNECT)
        if mode == ETHERNET_WIFI_MODE_DISABLE_ADAPTER:
            try:
                self.service.enable_wifi_adapter()
                self.logger.info('Wi-Fi adapter re-enabled from tray action.')
            except Exception as exc:  # noqa: BLE001
                self.logger.exception('Failed to re-enable Wi-Fi adapter from tray action: %s', exc)
                return

        self.service.evaluate_and_switch()

    def on_manage_networks(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        """
        Open the network management settings window.
        """
        del icon, item
        self.logger.info('Opening network settings window.')
        if self._settings_window is None:
            from wifi_pref_manager.ui.settings import SettingsWindow  # noqa: PLC0415
            self._settings_window = SettingsWindow(
                service=self.service,
                config_loader=self.config_loader,
                logger=self.logger,
            )
        self._settings_window.open()

    def on_show_output_console(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        """
        Reveal the buffered output console for the tray session.
        """
        del icon, item
        if self.show_output_console_callback is None:
            return
        self.logger.info('Showing the buffered output console from the tray.')
        self.show_output_console_callback()

    def on_check_for_updates(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        """
        Start a manual update check.
        """
        del icon, item
        self.check_for_updates(auto=False)

    def check_for_updates(self, *, auto: bool) -> None:
        """
        Check GitHub Releases for a newer PolyFi installer.
        """
        with self._update_check_lock:
            if self._update_check_in_progress:
                if not auto:
                    show_dialog_async(
                        'info',
                        'Update Check',
                        'An update check is already running.',
                    )
                return
            self._update_check_in_progress = True

        threading.Thread(
            target=self._run_update_check,
            kwargs={'auto': auto},
            daemon=True,
            name='polyfi-update-check',
        ).start()

    def _run_update_check(self, *, auto: bool) -> None:
        try:
            update = self.update_manager.check_for_update(__version__)
        except UpdateError as exc:
            self.logger.warning('Update check failed: %s', exc)
            if not auto:
                show_dialog_async(
                    'error',
                    'Update Check Failed',
                    f'Could not check for updates:\n\n{exc}',
                )
            return
        finally:
            with self._update_check_lock:
                self._update_check_in_progress = False

        if update is None:
            self.logger.info('No PolyFi update available.')
            if not auto:
                show_dialog_async(
                    'info',
                    'PolyFi Is Up To Date',
                    f'{APP_NAME} {__version__} is the latest available release.',
                )
            return

        self.logger.info('PolyFi update available: %s', update.version)
        self._show_update_available_dialog(update)

    def _show_update_available_dialog(self, update: UpdateInfo) -> None:
        message = (
            f'{APP_NAME} {update.version} is available.\n\n'
            f'Current version: {__version__}\n'
            f'Release: {update.release_url}'
        )
        buttons: tuple[tuple[str, Callable[[], None] | None], ...]
        if update.installer_asset is not None:
            buttons = (
                ('Later', None),
                ('Open Release Page', lambda: webbrowser.open(update.release_url)),
                ('Download and Install', lambda: self.download_and_install_update(update)),
            )
        else:
            buttons = (
                ('Later', None),
                ('Open Release Page', lambda: webbrowser.open(update.release_url)),
            )

        show_custom_dialog_async(
            title='PolyFi Update Available',
            message=message,
            buttons=buttons,
        )

    def download_and_install_update(self, update: UpdateInfo) -> None:
        """
        Download an available installer and launch it.
        """
        threading.Thread(
            target=self._download_and_install_update,
            args=(update,),
            daemon=True,
            name='polyfi-update-install',
        ).start()

    def _download_and_install_update(self, update: UpdateInfo) -> None:
        try:
            installer_path = self.update_manager.download_installer(update)
            self.update_manager.launch_installer(installer_path)
        except UpdateError as exc:
            self.logger.warning('Update install failed: %s', exc)
            show_dialog_async(
                'error',
                'Update Install Failed',
                f'Could not download or start the update installer:\n\n{exc}',
            )
            return

        self.logger.info('Launched PolyFi update installer: %s', installer_path)
        show_dialog_async(
            'info',
            'Update Installer Started',
            f'The {APP_NAME} {update.version} installer has been downloaded and started.\n\n'
            f'Installer path:\n{installer_path}',
        )

    def on_about(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        """
        Show product and runtime version details.
        """
        del icon, item
        show_custom_dialog_async(
            title=f'About {APP_NAME}',
            message=(
                f'{APP_NAME}\n\n'
                f'PolyFi: Ranked version: {__version__}\n'
                f'Python version: {sys.version.split()[0]}'
            ),
            buttons=(
                ('Close', None),
                ('Docs', lambda: webbrowser.open(DOCS_URL)),
                ('GitHub', lambda: webbrowser.open(GITHUB_REPOSITORY_URL)),
            ),
        )

    def on_quit(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        """
        Stop the service and exit the tray app.
        """
        del item
        self.logger.info('Tray app shutdown requested.')
        self._quit_requested = True
        self.service.stop()
        icon.stop()

    def _build_icon(self, icon_title: str) -> pystray.Icon:
        """
        Build the tray icon object for a run attempt.
        """
        return pystray.Icon(
            'polyfi_ranked',
            self.create_image(),
            icon_title,
            menu=pystray.Menu(
                pystray.MenuItem(
                    lambda item: self.service.get_speed_test_status_text(),
                    lambda icon, item: None,
                    enabled=False,
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    '\u26a0 Restart as Administrator for Ethernet control',
                    lambda icon, item: None,
                    enabled=False,
                    visible=lambda item: self._needs_admin_notification,
                ),
                pystray.MenuItem('Manage Networks…', self.on_manage_networks),
                pystray.MenuItem('Rescan Now', self.on_rescan),
                pystray.MenuItem('Restore Wi-Fi (Disable Auto Ethernet)', self.on_reenable_wifi),
                pystray.MenuItem(
                    'Show Output Console',
                    self.on_show_output_console,
                    enabled=lambda item: self.show_output_console_callback is not None,
                ),
                pystray.MenuItem('Check for Updates', self.on_check_for_updates),
                pystray.MenuItem('About PolyFi: Ranked...', self.on_about),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem('Quit', self.on_quit),
            ),
        )

    def show_runtime_warning(self, title: str, message: str) -> None:
        """
        Display a runtime warning dialog for important recoverable issues.

        Parameters:
            title:
                Warning title.
            message:
                Warning body text.
        """
        self.logger.warning('%s: %s', title, message.replace('\n', ' '))
        show_dialog_async('warning', title, message)

    def show_wifi_adapter_disabled_dialog(self, active_ethernet_interfaces: list[str]) -> None:
        """
        Show a dialog after PolyFi applies the Ethernet Wi-Fi action.

        Parameters:
            active_ethernet_interfaces:
                Active Ethernet interface names that triggered the disable.
        """
        if not self.service.config.show_wifi_disabled_dialog:
            return

        interface_text = ', '.join(active_ethernet_interfaces) if active_ethernet_interfaces else 'Ethernet'
        mode = getattr(self.service.config, 'ethernet_wifi_mode', ETHERNET_WIFI_MODE_DISCONNECT)
        if mode == ETHERNET_WIFI_MODE_DISABLE_ADAPTER:
            title = 'Wi-Fi Adapter Disabled'
            message = (
                'PolyFi disabled the Wi-Fi adapter because an active Ethernet connection was detected on '
                f'{interface_text}.\n\n'
                'You can acknowledge this, re-enable the Wi-Fi adapter now, or turn the automatic feature off.'
            )
            recover_label = 'Re-enable WiFi adapter'
        else:
            title = 'Wi-Fi Auto-Connect Paused'
            message = (
                'PolyFi detected active Ethernet on '
                f'{interface_text} and temporarily disconnected Wi-Fi while setting saved Wi-Fi profiles to '
                'manual connect.\n\n'
                'PolyFi restores your previous Wi-Fi state when Ethernet disconnects or when the app exits.'
            )
            recover_label = 'Restore WiFi now'

        show_custom_dialog_async(
            title=title,
            message=message,
            buttons=(
                ('OK', None),
                (recover_label, self.reenable_wifi_adapter_and_disable_auto_ethernet),
                ('Turn Feature Off', self.disable_auto_ethernet_feature),
            ),
            checkbox_label='Do not show this dialog again',
            on_checkbox_checked=self.suppress_wifi_disabled_dialog,
        )

    def show_wifi_network_changed_notification(
        self,
        previous_ssid: str | None,
        new_ssid: str,
        reason: str | None = None,
    ) -> None:
        """
        Send a toast notification when the active Wi-Fi SSID changes.

        Parameters:
            previous_ssid:
                Previously active SSID, if any.
            new_ssid:
                Newly active SSID.
            reason:
                Optional human-readable explanation for the switch.
        """
        if self.icon is None or not hasattr(self.icon, 'notify'):
            return

        title = 'Wi-Fi Network Changed'
        if previous_ssid:
            message = f'Switched from {previous_ssid} to {new_ssid}.'
        else:
            message = f'Connected to {new_ssid}.'
        if reason:
            message = f'{message} {reason}'

        try:
            self.icon.notify(message, title=title)
        except Exception:  # noqa: BLE001
            self.logger.debug('Tray notification failed.', exc_info=True)

    def refresh_menu(self) -> None:
        """
        Refresh the tray menu so dynamic labels pick up new state.
        """
        if self.icon is not None:
            self.icon.update_menu()

    def run(self) -> None:
        """
        Start the service and tray icon loop.
        """
        self._quit_requested = False
        self.service.start()
        icon_title = (
            'PolyFi: Ranked \u26a0 Restart as Administrator for Ethernet control'
            if self._needs_admin_notification
            else 'PolyFi: Ranked'
        )
        unexpected_exit_retries = 0

        while True:
            self._icon_ready_event = threading.Event()
            self._icon_run_done_event = threading.Event()
            self.icon = self._build_icon(icon_title)
            watchdog = threading.Thread(
                target=self._setup_watchdog,
                daemon=True,
                name='polyfi-tray-watchdog',
            )
            watchdog.start()
            loop_started = time.monotonic()
            try:
                self.icon.run(setup=self._on_icon_ready)
            finally:
                self._icon_run_done_event.set()
            loop_duration = max(0.0, time.monotonic() - loop_started)
            if self._quit_requested:
                return
            if loop_duration >= self._TRAY_UNEXPECTED_EXIT_THRESHOLD:
                self.logger.warning(
                    'Tray loop exited after %.2f s without a quit request.',
                    loop_duration,
                )
                self._append_startup_trace(
                    f'tray loop exited after {loop_duration:.2f}s without quit request'
                )
                self.service.stop()
                return

            unexpected_exit_retries += 1
            self.logger.warning(
                'Tray loop exited after %.2f s without a quit request; retrying (%d/%d).',
                loop_duration,
                unexpected_exit_retries,
                self._TRAY_UNEXPECTED_EXIT_MAX_RETRIES,
            )
            self._append_startup_trace(
                f'unexpected tray loop exit after {loop_duration:.2f}s; '
                f'retry {unexpected_exit_retries}/{self._TRAY_UNEXPECTED_EXIT_MAX_RETRIES}'
            )
            if unexpected_exit_retries > self._TRAY_UNEXPECTED_EXIT_MAX_RETRIES:
                self.service.stop()
                raise RuntimeError(
                    'PolyFi could not keep the system tray icon running during startup.'
                )
            time.sleep(self._TRAY_UNEXPECTED_EXIT_RETRY_DELAY)

    def _setup_watchdog(self) -> None:
        """
        Background thread that fires a diagnostic dialog when the pystray setup
        callback is not invoked within ``_TRAY_SETUP_TIMEOUT`` seconds.

        This covers the silent-failure case where ``Shell_NotifyIcon(NIM_ADD)``
        succeeds from pystray's perspective but the icon never appears in the
        notification area, leaving the user with no feedback.
        """
        ready = self._icon_ready_event is not None and self._icon_ready_event.wait(
            timeout=self._TRAY_SETUP_TIMEOUT
        )
        if ready:
            return
        # If icon.run() already exited (e.g. due to an exception) the caller in
        # app.py will handle that path; avoid a redundant second dialog here.
        if self._icon_run_done_event is not None and self._icon_run_done_event.is_set():
            return
        self.logger.warning(
            'Tray icon setup callback was not invoked within %.0f s; '
            'the system tray icon may not have registered successfully.',
            self._TRAY_SETUP_TIMEOUT,
        )
        self._append_startup_trace('setup callback timeout')
        trace_hint = (
            f'\n\nDiagnostic log:\n{self._startup_trace_path}'
            if self._startup_trace_path is not None
            else ''
        )
        show_native_message_box(
            'warning',
            APP_NAME,
            f'{APP_NAME} started but its system tray icon has not appeared.\n\n'
            'PolyFi is running in the background. If the icon is still not visible:\n'
            '\u2022 Open Windows Settings \u2192 Personalization \u2192 Taskbar '
            '\u2192 Other system tray icons, and make sure PolyFi is set to On.\n'
            '\u2022 Check the notification area overflow (\u25b2 chevron near the clock).'
            f'{trace_hint}',
        )

    def _on_icon_ready(self, icon: pystray.Icon) -> None:
        """
        Called once the tray icon is active.  Shows a brief notification so the
        user can locate the icon when it appears in the system tray overflow area.
        On the very first tray launch a native message box is also shown so the
        user can find the hidden-icons area before they know where to look.
        When an admin notification is pending, a toast is also shown to inform
        the user that Ethernet control requires administrator privileges.
        If a post-icon-ready callback was registered, it is fired on a background
        thread so the icon loop is not blocked.
        """
        # Signal the watchdog that icon registration succeeded.
        if self._icon_ready_event is not None:
            self._icon_ready_event.set()
        icon.visible = True
        self._append_startup_trace('icon ready callback fired')
        try:
            icon.notify(f'{APP_NAME} is now running in your system tray.', APP_NAME)
        except Exception:  # noqa: BLE001
            pass

        if self._needs_admin_notification:
            try:
                icon.notify(
                    'The "disable Wi-Fi when Ethernet is connected" feature requires '
                    'administrator privileges. Restart PolyFi as administrator to use it.',
                    title='Administrator Required',
                )
            except Exception:  # noqa: BLE001
                pass

        if self._startup_marker_path is not None and not self._startup_marker_path.exists():
            show_native_message_box(
                'info',
                APP_NAME,
                f'{APP_NAME} is now running in the background.\n\n'
                'Look for the PolyFi icon in the notification area near the clock on your '
                'taskbar. You may need to click the \u25b2 (chevron) arrow to expand '
                'hidden system tray icons.',
            )
            try:
                self._startup_marker_path.touch()
            except OSError:
                pass

        if self._post_icon_ready_callback is not None:
            self._append_startup_trace('starting post-icon callback')
            threading.Thread(
                target=self._post_icon_ready_callback,
                daemon=True,
                name='polyfi-post-icon-setup',
            ).start()

        if getattr(self.service.config, 'auto_check_for_updates', True):
            self.check_for_updates(auto=True)

