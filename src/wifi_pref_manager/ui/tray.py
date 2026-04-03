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

import logging
import subprocess
import sys
import threading
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw
import pystray

from wifi_pref_manager.service import WiFiPreferenceService
from wifi_pref_manager.ui.log_viewer import LogHistoryHandler, LogViewerWindow

if TYPE_CHECKING:
    from wifi_pref_manager.ui.settings import SettingsWindow


class TrayApplication:
    """
    Minimal Windows system tray UI.

    Methods:
        run:
            Launch the tray icon event loop.
    """

    def __init__(
        self,
        service: WiFiPreferenceService,
        logger: logging.Logger,
        config_loader=None,
    ) -> None:
        self.service = service
        self.logger = logger
        self.config_loader = config_loader
        self.icon: pystray.Icon | None = None
        self._settings_window: SettingsWindow | None = None
        self._log_window: LogViewerWindow | None = None
        self.log_handler = LogHistoryHandler()
        self.log_handler.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s'))
        self.logger.addHandler(self.log_handler)

    def create_image(self) -> Image.Image:
        """
        Create a simple tray icon image.

        Returns:
            Pillow image instance.
        """
        image = Image.new('RGB', (64, 64), 'black')
        draw = ImageDraw.Draw(image)
        draw.arc((10, 22, 54, 58), start=200, end=340, fill='white', width=4)
        draw.arc((18, 30, 46, 54), start=210, end=330, fill='white', width=4)
        draw.ellipse((28, 44, 36, 52), fill='white')
        return image

    def on_rescan(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        """
        Trigger an immediate preference evaluation.
        """
        del icon, item
        self.logger.info('Manual rescan requested from tray.')
        self.service.reload_config_if_needed()
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

    def on_quit(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        """
        Stop the service and exit the tray app.
        """
        del item
        self.logger.info('Tray app shutdown requested.')
        self.service.stop()
        icon.stop()

    def on_show_output(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        del icon, item
        if self._log_window is None:
            self._log_window = LogViewerWindow(
                service=self.service,
                config_loader=self.config_loader,
                logger=self.logger,
                log_handler=self.log_handler,
            )
        thread = threading.Thread(target=self._log_window.open, daemon=True)
        thread.start()

    def on_notify(self, title: str, message: str) -> None:
        if self.icon is None:
            return
        try:
            self.icon.notify(message, title=title)
        except Exception:  # noqa: BLE001
            self.logger.debug('Failed to show tray notification.', exc_info=True)

    def on_install_start_menu(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        del icon, item
        subprocess.run([sys.executable, '-m', 'wifi_pref_manager.startup', 'install-shortcuts'], check=False)

    def on_enable_startup(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        del icon, item
        subprocess.run([sys.executable, '-m', 'wifi_pref_manager.startup', 'enable-autostart'], check=False)

    def run(self) -> None:
        """
        Start the service and tray icon loop.
        """
        self.service.start()
        self.service.on_notify = self.on_notify
        self.icon = pystray.Icon(
            'polyfi_ranked',
            self.create_image(),
            'PolyFi: Ranked',
            menu=pystray.Menu(
                pystray.MenuItem('Manage Networks…', self.on_manage_networks),
                pystray.MenuItem('Show Output…', self.on_show_output),
                pystray.MenuItem('Rescan Now', self.on_rescan),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem('Install Start Menu Shortcuts', self.on_install_start_menu),
                pystray.MenuItem('Enable Start With Windows', self.on_enable_startup),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem('Quit', self.on_quit),
            ),
        )
        self.icon.run()
