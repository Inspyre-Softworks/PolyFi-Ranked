"""
Application-wide configuration window for PolyFi: Ranked.

The network-priority editor intentionally lives in ``ui.settings``; this
window owns settings that affect the application as a whole.
"""

from __future__ import annotations

from dataclasses import replace
import logging
import tkinter as tk
from tkinter import messagebox, ttk

from wifi_pref_manager.config import ConfigLoader, save_config
from wifi_pref_manager.models import (
    ETHERNET_WIFI_MODE_DISABLE_ADAPTER,
    ETHERNET_WIFI_MODE_DISCONNECT,
)
from wifi_pref_manager.service import WiFiPreferenceService
from wifi_pref_manager.ui.dialogs import run_on_ui_thread


ETHERNET_ACTION_CHOICES = (
    ('Disconnect + disable auto-connect (recommended)', ETHERNET_WIFI_MODE_DISCONNECT),
    ('Disable WiFi adapter', ETHERNET_WIFI_MODE_DISABLE_ADAPTER),
)


class GlobalConfigurationWindow:
    """Manage application-wide configuration in a single Tkinter window."""

    def __init__(
        self,
        service: WiFiPreferenceService,
        config_loader: ConfigLoader,
        logger: logging.Logger,
    ) -> None:
        self.service = service
        self.config_loader = config_loader
        self.logger = logger
        self._window: tk.Toplevel | None = None

    def open(self) -> None:
        """Open the window, or raise the existing instance."""

        def _open_window(root: tk.Tk) -> None:
            if self._window is not None and self._window.winfo_exists():
                self._window.lift()
                self._window.focus_force()
                return
            self._build_window(root)

        run_on_ui_thread(_open_window, wait=False)

    @staticmethod
    def _set_visible(widget: tk.Widget, visible: bool) -> None:
        """Show or hide a grid-managed dependent control immediately."""
        if visible:
            widget.grid()
        else:
            widget.grid_remove()

    def _build_window(self, root: tk.Tk) -> None:
        win = tk.Toplevel(root)
        win.title('PolyFi: Ranked – Global Configuration')
        win.resizable(False, False)
        win.protocol('WM_DELETE_WINDOW', lambda: self._on_cancel(win))
        self._window = win

        config = self.service.config
        content = ttk.Frame(win, padding=10)
        content.grid(row=0, column=0, sticky='nsew')

        # General
        general = ttk.LabelFrame(content, text='General', padding=8)
        general.grid(row=0, column=0, sticky='ew')
        general.columnconfigure(1, weight=1)

        ttk.Label(general, text='Scan interval (seconds):').grid(row=0, column=0, sticky='w')
        scan_interval_var = tk.StringVar(value=str(config.scan_interval))
        ttk.Spinbox(general, from_=1, to=86400, textvariable=scan_interval_var, width=10).grid(
            row=0, column=1, padx=(8, 0), sticky='w'
        )

        splash_var = tk.BooleanVar(value=config.show_startup_splash)
        ttk.Checkbutton(
            general,
            text='Show splash on app start',
            variable=splash_var,
        ).grid(row=1, column=0, columnspan=2, pady=(6, 0), sticky='w')

        start_with_windows_var = tk.BooleanVar(value=config.add_to_startup_programs)
        ttk.Checkbutton(
            general,
            text='Start with Windows',
            variable=start_with_windows_var,
        ).grid(row=2, column=0, columnspan=2, pady=(4, 0), sticky='w')

        scheduled_task_var = tk.BooleanVar(value=bool(config.add_scheduled_logon_task))
        scheduled_task_control = ttk.Checkbutton(
            general,
            text='Schedule with Task Scheduler (for earlier start)',
            variable=scheduled_task_var,
        )
        scheduled_task_control.grid(row=3, column=0, columnspan=2, padx=(20, 0), pady=(4, 0), sticky='w')

        def _sync_startup_dependents(*_args: object) -> None:
            self._set_visible(scheduled_task_control, start_with_windows_var.get())

        start_with_windows_var.trace_add('write', _sync_startup_dependents)
        _sync_startup_dependents()

        # Speed tests
        speed_tests = ttk.LabelFrame(content, text='Speed Tests', padding=8)
        speed_tests.grid(row=1, column=0, pady=(8, 0), sticky='ew')
        speed_tests.columnconfigure(0, weight=1)

        enable_speed_tests_var = tk.BooleanVar(value=config.enable_speed_tests)
        ttk.Checkbutton(
            speed_tests,
            text='Enable speed tests',
            variable=enable_speed_tests_var,
        ).grid(row=0, column=0, sticky='w')

        speed_test_details = ttk.Frame(speed_tests)
        speed_test_details.grid(row=1, column=0, padx=(20, 0), pady=(4, 0), sticky='ew')
        ttk.Label(speed_test_details, text='Test interval (seconds):').grid(row=0, column=0, sticky='w')
        speed_test_interval_var = tk.StringVar(value=str(config.speed_test_interval))
        ttk.Spinbox(
            speed_test_details,
            from_=0,
            to=604800,
            textvariable=speed_test_interval_var,
            width=10,
        ).grid(row=0, column=1, padx=(8, 0), sticky='w')
        speed_test_on_connect_var = tk.BooleanVar(value=config.speed_test_on_new_connection)
        ttk.Checkbutton(
            speed_test_details,
            text='Test on connect',
            variable=speed_test_on_connect_var,
        ).grid(row=1, column=0, columnspan=2, pady=(4, 0), sticky='w')

        def _sync_speed_test_dependents(*_args: object) -> None:
            self._set_visible(speed_test_details, enable_speed_tests_var.get())

        enable_speed_tests_var.trace_add('write', _sync_speed_test_dependents)
        _sync_speed_test_dependents()

        # Ethernet handling
        ethernet = ttk.LabelFrame(content, text='Ethernet Handling', padding=8)
        ethernet.grid(row=2, column=0, pady=(8, 0), sticky='ew')

        wifi_off_var = tk.BooleanVar(value=config.auto_disable_wifi_on_ethernet)
        ttk.Checkbutton(
            ethernet,
            text='Automatically turn off Wi-Fi when Ethernet is connected',
            variable=wifi_off_var,
        ).grid(row=0, column=0, columnspan=2, sticky='w')

        connect_after_ethernet_var = tk.BooleanVar(
            value=config.connect_preferred_after_ethernet_disconnect
        )
        ttk.Checkbutton(
            ethernet,
            text='Automatically connect to preferred Wi-Fi network when Ethernet disconnects',
            variable=connect_after_ethernet_var,
        ).grid(row=1, column=0, columnspan=2, pady=(4, 0), sticky='w')

        ttk.Label(ethernet, text='Ethernet action:').grid(row=2, column=0, pady=(6, 0), sticky='w')
        ethernet_action_var = tk.StringVar(value=config.ethernet_wifi_mode)
        ethernet_action_combo = ttk.Combobox(
            ethernet,
            state='readonly',
            width=48,
            values=[label for label, _value in ETHERNET_ACTION_CHOICES],
        )
        ethernet_action_combo.set(
            next(
                (
                    label
                    for label, value in ETHERNET_ACTION_CHOICES
                    if value == ethernet_action_var.get()
                ),
                ETHERNET_ACTION_CHOICES[0][0],
            )
        )
        ethernet_action_combo.grid(row=3, column=0, columnspan=2, sticky='w')

        def _on_ethernet_action_selected(_event: object | None = None) -> None:
            selected_label = ethernet_action_combo.get()
            ethernet_action_var.set(
                next(
                    value
                    for label, value in ETHERNET_ACTION_CHOICES
                    if label == selected_label
                )
            )

        ethernet_action_combo.bind('<<ComboboxSelected>>', _on_ethernet_action_selected)

        # Updates
        updates = ttk.LabelFrame(content, text='Updates', padding=8)
        updates.grid(row=3, column=0, pady=(8, 0), sticky='ew')

        auto_updates_var = tk.BooleanVar(value=config.auto_check_for_updates)
        ttk.Checkbutton(
            updates,
            text='Check for updates automatically',
            variable=auto_updates_var,
        ).grid(row=0, column=0, sticky='w')
        prerelease_var = tk.BooleanVar(value=config.allow_prerelease_updates)
        prerelease_control = ttk.Checkbutton(
            updates,
            text='Allow pre-release versions',
            variable=prerelease_var,
        )
        prerelease_control.grid(row=1, column=0, padx=(20, 0), pady=(4, 0), sticky='w')

        def _sync_update_dependents(*_args: object) -> None:
            self._set_visible(prerelease_control, auto_updates_var.get())

        auto_updates_var.trace_add('write', _sync_update_dependents)
        _sync_update_dependents()

        buttons = ttk.Frame(content)
        buttons.grid(row=4, column=0, pady=(8, 0), sticky='e')

        def _parse_interval(value: str, label: str, minimum: int) -> int | None:
            try:
                parsed = int(value)
            except ValueError:
                messagebox.showerror('Validation Error', f'{label} must be a whole number.', parent=win)
                return None
            if parsed < minimum:
                messagebox.showerror(
                    'Validation Error',
                    f'{label} must be at least {minimum}.',
                    parent=win,
                )
                return None
            return parsed

        def _on_save() -> None:
            scan_interval = _parse_interval(scan_interval_var.get(), 'Scan interval', 1)
            if scan_interval is None:
                return
            speed_test_interval = _parse_interval(
                speed_test_interval_var.get(),
                'Test interval',
                0,
            )
            if speed_test_interval is None:
                return

            _on_ethernet_action_selected()
            new_config = replace(
                config,
                scan_interval=scan_interval,
                show_startup_splash=splash_var.get(),
                add_to_startup_programs=start_with_windows_var.get(),
                add_scheduled_logon_task=(
                    scheduled_task_var.get() if start_with_windows_var.get() else False
                ),
                enable_speed_tests=enable_speed_tests_var.get(),
                speed_test_interval=speed_test_interval,
                speed_test_on_new_connection=speed_test_on_connect_var.get(),
                auto_disable_wifi_on_ethernet=wifi_off_var.get(),
                connect_preferred_after_ethernet_disconnect=connect_after_ethernet_var.get(),
                ethernet_wifi_mode=ethernet_action_var.get(),
                auto_check_for_updates=auto_updates_var.get(),
                allow_prerelease_updates=prerelease_var.get(),
            )

            try:
                save_config(new_config, self.config_loader.config_path)
            except OSError as exc:
                self.logger.error('Failed to save global configuration: %s', exc)
                messagebox.showerror(
                    'Save Failed',
                    f'Could not write configuration file:\n{exc}',
                    parent=win,
                )
                return

            self.logger.info('Global configuration saved to %s', self.config_loader.config_path)
            self.service.reload_config(new_config)
            self.config_loader.mark_loaded()
            messagebox.showinfo(
                'Saved',
                'Global configuration has been saved and applied.',
                parent=win,
            )
            win.destroy()
            self._window = None

        ttk.Button(buttons, text='Save', command=_on_save, width=10).pack(side='right', padx=(4, 0))
        ttk.Button(
            buttons,
            text='Cancel',
            command=lambda: self._on_cancel(win),
            width=10,
        ).pack(side='right')

    def _on_cancel(self, win: tk.Toplevel) -> None:
        win.destroy()
        self._window = None
