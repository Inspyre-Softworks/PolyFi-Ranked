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
import threading
from datetime import datetime
from typing import TYPE_CHECKING, Callable

from PIL import Image
import pystray

from wifi_pref_manager.config import save_config
from wifi_pref_manager.icon_assets import create_app_icon_image
from wifi_pref_manager.paths import APP_NAME
from wifi_pref_manager.service import WiFiPreferenceService
from wifi_pref_manager.ui.dialogs import show_custom_dialog_async, show_dialog_async, show_native_message_box

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

    def __init__(
        self,
        service: WiFiPreferenceService,
        logger: logging.Logger,
        config_loader=None,
        restart_as_admin_callback: Callable[[], bool] | None = None,
        show_output_console_callback: Callable[[], None] | None = None,
        startup_marker_path: Path | None = None,
        startup_trace_path: Path | None = None,
        post_icon_ready_callback: Callable[[], None] | None = None,
    ) -> None:
        self.service = service
        self.logger = logger
        self.config_loader = config_loader
        self.restart_as_admin_callback = restart_as_admin_callback
        self.show_output_console_callback = show_output_console_callback
        self._startup_marker_path = startup_marker_path
        self._startup_trace_path = startup_trace_path
        self._post_icon_ready_callback = post_icon_ready_callback
        self.icon: pystray.Icon | None = None
        self._settings_window: SettingsWindow | None = None
        self._icon_ready_event: threading.Event | None = None
        self._icon_run_done_event: threading.Event | None = None
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
            timestamp = datetime.now().isoformat(timespec='seconds')
            self._startup_trace_path.parent.mkdir(parents=True, exist_ok=True)
            with self._startup_trace_path.open('a', encoding='utf-8') as handle:
                handle.write(f'[{timestamp}] tray:{message}\n')
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

    def _save_and_reload_config(self, new_config) -> bool:
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
        Turn off automatic Ethernet Wi-Fi disable and persist the change.

        Returns:
            True when the runtime/config update succeeded.
        """
        new_config = replace(self.service.config, auto_disable_wifi_on_ethernet=False)
        if not self._save_and_reload_config(new_config):
            return False
        self.service.set_auto_disable_wifi_on_ethernet(False)
        self.logger.info('Disabled automatic Wi-Fi disable on Ethernet from the tray UI.')
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
        Disable Ethernet auto-detection, re-enable Wi-Fi, and rescan.
        """
        self.logger.warning('Tray recovery requested: disabling Ethernet auto-detection and re-enabling Wi-Fi.')
        if not self.disable_auto_ethernet_feature():
            return

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

        # Run the settings window in its own thread so the tray stays responsive.
        thread = threading.Thread(target=self._settings_window.open, daemon=True)
        thread.start()

    def on_show_output_console(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        """
        Reveal the buffered output console for the tray session.
        """
        del icon, item
        if self.show_output_console_callback is None:
            return
        self.logger.info('Showing the buffered output console from the tray.')
        self.show_output_console_callback()

    def on_quit(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        """
        Stop the service and exit the tray app.
        """
        del item
        self.logger.info('Tray app shutdown requested.')
        self.service.stop()
        icon.stop()

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
        if title == 'Administrator Required' and self.restart_as_admin_callback is not None:
            show_dialog_async(
                'warning',
                title,
                message,
                action_label='Restart as Administrator',
                action_callback=self.restart_as_administrator,
                continue_label='Continue Without Auto Ethernet',
            )
            return
        show_dialog_async('warning', title, message)

    def show_wifi_adapter_disabled_dialog(self, active_ethernet_interfaces: list[str]) -> None:
        """
        Show a dialog after PolyFi disables the Wi-Fi adapter.

        Parameters:
            active_ethernet_interfaces:
                Active Ethernet interface names that triggered the disable.
        """
        if not self.service.config.show_wifi_disabled_dialog:
            return

        interface_text = ', '.join(active_ethernet_interfaces) if active_ethernet_interfaces else 'Ethernet'
        show_custom_dialog_async(
            title='Wi-Fi Adapter Disabled',
            message=(
                'PolyFi disabled the Wi-Fi adapter because an active Ethernet connection was detected on '
                f'{interface_text}.\n\n'
                'You can acknowledge this, re-enable the Wi-Fi adapter now, or turn the automatic feature off.'
            ),
            buttons=(
                ('OK', None),
                ('Re-enable WiFi adapter', self.reenable_wifi_adapter_and_disable_auto_ethernet),
                ('Turn Feature Off', self.disable_auto_ethernet_feature),
            ),
            checkbox_label='Do not show this dialog again',
            on_checkbox_checked=self.suppress_wifi_disabled_dialog,
        )

    def show_wifi_network_changed_notification(self, previous_ssid: str | None, new_ssid: str) -> None:
        """
        Send a toast notification when the active Wi-Fi SSID changes.

        Parameters:
            previous_ssid:
                Previously active SSID, if any.
            new_ssid:
                Newly active SSID.
        """
        if self.icon is None or not hasattr(self.icon, 'notify'):
            return

        title = 'Wi-Fi Network Changed'
        if previous_ssid:
            message = f'Switched from {previous_ssid} to {new_ssid}.'
        else:
            message = f'Connected to {new_ssid}.'

        try:
            self.icon.notify(message, title=title)
        except Exception:  # noqa: BLE001
            self.logger.debug('Tray notification failed.', exc_info=True)

    def restart_as_administrator(self) -> None:
        """
        Relaunch the app with elevation and stop the current tray instance.
        """
        if self.restart_as_admin_callback is None:
            return

        try:
            launched = self.restart_as_admin_callback()
        except Exception as exc:  # noqa: BLE001
            self.logger.exception('Failed to restart with administrator privileges: %s', exc)
            show_dialog_async(
                'error',
                'Restart Failed',
                f'PolyFi could not restart as administrator:\n\n{exc}',
            )
            return

        if not launched:
            self.logger.warning('Administrator restart was cancelled or could not be started.')
            return

        self.logger.info('Administrator restart launched successfully. Shutting down current tray instance.')
        self.service.stop()
        if self.icon is not None:
            self.icon.stop()

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
        self._icon_ready_event = threading.Event()
        self._icon_run_done_event = threading.Event()
        self.service.start()
        self.icon = pystray.Icon(
            'polyfi_ranked',
            self.create_image(),
            'PolyFi: Ranked',
            menu=pystray.Menu(
                pystray.MenuItem(
                    lambda item: self.service.get_speed_test_status_text(),
                    lambda icon, item: None,
                    enabled=False,
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem('Manage Networks…', self.on_manage_networks),
                pystray.MenuItem('Rescan Now', self.on_rescan),
                pystray.MenuItem('Re-enable Wi-Fi (Disable Auto Ethernet)', self.on_reenable_wifi),
                pystray.MenuItem(
                    'Show Output Console',
                    self.on_show_output_console,
                    enabled=lambda item: self.show_output_console_callback is not None,
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem('Quit', self.on_quit),
            ),
        )
        watchdog = threading.Thread(
            target=self._setup_watchdog,
            daemon=True,
            name='polyfi-tray-watchdog',
        )
        watchdog.start()
        try:
            self.icon.run(setup=self._on_icon_ready)
        finally:
            self._icon_run_done_event.set()

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
        If a post-icon-ready callback was registered (e.g. deferred task setup),
        it is fired on a background thread so the icon loop is not blocked.
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

        # Deferred one-time setup (e.g. scheduled task installation) runs here
        # so the icon is already visible when the UAC prompt appears.
        if self._post_icon_ready_callback is not None:
            self._append_startup_trace('starting post-icon callback')
            threading.Thread(
                target=self._post_icon_ready_callback,
                daemon=True,
                name='polyfi-post-icon-setup',
            ).start()

