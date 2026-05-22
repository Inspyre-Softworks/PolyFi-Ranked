"""
Author:
    Inspyre Softworks

Project:
    PolyFi: Ranked

File:
    ui/settings.py

Description:
    Tkinter-based settings window for managing network priority order and
    Ethernet auto-disable behaviour.

Classes:
    SettingsWindow

Dependencies:
    tkinter
    wifi_pref_manager.config
    wifi_pref_manager.models
    wifi_pref_manager.service

Example Usage:
    window = SettingsWindow(service=service, config_loader=loader, logger=logger)
    window.open()
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk

from wifi_pref_manager.config import save_config
from wifi_pref_manager.models import (
    ETHERNET_WIFI_MODE_DISABLE_ADAPTER,
    ETHERNET_WIFI_MODE_DISCONNECT,
    AppConfig,
    WiFiProfilePreference,
)
from wifi_pref_manager.service import WiFiPreferenceService
from wifi_pref_manager.ui.dialogs import run_on_ui_thread


class SettingsWindow:
    """
    Manages the network-priority settings window.

    Methods:
        open:
            Open (or raise) the settings window.
    """

    def __init__(
        self,
        service: WiFiPreferenceService,
        config_loader,
        logger: logging.Logger,
    ) -> None:
        """
        Parameters:
            service:
                Running Wi-Fi preference service.
            config_loader:
                ConfigLoader used to resolve the config file path and trigger
                hot-reload detection.
            logger:
                Application logger.
        """
        self.service = service
        self.config_loader = config_loader
        self.logger = logger
        self._window: tk.Toplevel | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def open(self) -> None:
        """Open the settings window, or bring it to the foreground if already open."""
        def _open_window(root: tk.Tk) -> None:
            if self._window is not None and self._window.winfo_exists():
                self._window.lift()
                self._window.focus_force()
                return

            self._build_window(root)

        run_on_ui_thread(_open_window, wait=False)

    # ------------------------------------------------------------------
    # Window construction
    # ------------------------------------------------------------------

    def _build_window(self, root: tk.Tk) -> None:
        """Create and show the settings Toplevel window."""
        win = tk.Toplevel(root)
        win.title('PolyFi: Ranked – Network Settings')
        win.resizable(False, False)
        win.protocol('WM_DELETE_WINDOW', lambda: self._on_cancel(win))
        self._window = win

        config = self.service.config
        enable_speed_tests = getattr(config, 'enable_speed_tests', False)
        speed_test_on_new_connection = getattr(config, 'speed_test_on_new_connection', True)
        speed_test_interval = getattr(config, 'speed_test_interval', 1800)
        save_speed_test_history = getattr(config, 'save_speed_test_history', False)
        speed_test_history_file = getattr(config, 'speed_test_history_file', '')

        # ---- Network list frame ----------------------------------------
        frame_list = ttk.LabelFrame(win, text='Network Priority (highest first)', padding=6)
        frame_list.grid(row=0, column=0, padx=10, pady=(10, 4), sticky='nsew')

        network_list: list[WiFiProfilePreference] = list(config.preferred_networks)
        listbox = tk.Listbox(frame_list, width=40, height=10, selectmode=tk.SINGLE)
        listbox.grid(row=0, column=0, rowspan=6, sticky='ns')

        scrollbar = ttk.Scrollbar(frame_list, orient='vertical', command=listbox.yview)
        scrollbar.grid(row=0, column=1, rowspan=6, sticky='ns')
        listbox.configure(yscrollcommand=scrollbar.set)

        def _refresh_list() -> None:
            listbox.delete(0, tk.END)
            for idx, pref in enumerate(network_list):
                label = f'{idx + 1}. {pref.ssid}'
                if not pref.auto_switch:
                    label += ' [manual]'
                if pref.min_db is not None:
                    label += f' [>= {pref.min_db} dBm]'
                listbox.insert(tk.END, label)

        _refresh_list()

        # ---- Side buttons ----------------------------------------------
        btn_frame = ttk.Frame(frame_list)
        btn_frame.grid(row=0, column=2, rowspan=6, padx=(6, 0), sticky='n')

        def _move_up() -> None:
            sel = listbox.curselection()
            if not sel or sel[0] == 0:
                return
            i = sel[0]
            network_list[i - 1], network_list[i] = network_list[i], network_list[i - 1]
            _refresh_list()
            listbox.selection_set(i - 1)

        def _move_down() -> None:
            sel = listbox.curselection()
            if not sel or sel[0] >= len(network_list) - 1:
                return
            i = sel[0]
            network_list[i + 1], network_list[i] = network_list[i], network_list[i + 1]
            _refresh_list()
            listbox.selection_set(i + 1)

        def _add_network() -> None:
            existing_ssids = {profile.ssid for profile in network_list}
            try:
                available_networks = [
                    ssid
                    for ssid in self.service.wifi_api.get_saved_profiles()
                    if ssid not in existing_ssids
                ]
            except Exception as exc:  # noqa: BLE001
                self.logger.error('Failed to load saved Wi-Fi profiles for Add Network: %s', exc)
                messagebox.showerror(
                    'Add Network Failed',
                    f'Could not load saved Windows Wi-Fi profiles:\n{exc}',
                    parent=win,
                )
                return

            if not available_networks:
                messagebox.showinfo(
                    'No Networks Available',
                    'No additional saved Windows Wi-Fi profiles are available to add.',
                    parent=win,
                )
                return

            selected_network: dict[str, str | None] = {'ssid': None}
            dialog = tk.Toplevel(win)
            dialog.title('Add Network')
            dialog.resizable(False, False)
            dialog.transient(win)
            dialog.grab_set()

            ttk.Label(dialog, text='Choose a saved Wi-Fi profile:').grid(
                row=0,
                column=0,
                padx=12,
                pady=(12, 6),
                sticky='w',
            )

            network_var = tk.StringVar()
            combo = ttk.Combobox(dialog, textvariable=network_var, values=available_networks, width=36)
            combo.grid(row=1, column=0, padx=12, pady=(0, 12), sticky='ew')

            def _filter_network_choices(*_args) -> None:
                typed = network_var.get().strip().lower()
                if not typed:
                    combo['values'] = available_networks
                    return
                combo['values'] = [
                    ssid for ssid in available_networks
                    if typed in ssid.lower()
                ]

            def _confirm_add() -> None:
                ssid = network_var.get().strip()
                if not ssid:
                    return
                if ssid not in available_networks:
                    messagebox.showerror(
                        'Unknown Network',
                        'Select one of the saved Windows Wi-Fi profiles from the dropdown list.',
                        parent=dialog,
                    )
                    return
                selected_network['ssid'] = ssid
                dialog.destroy()

            def _cancel_add() -> None:
                dialog.destroy()

            combo.bind('<KeyRelease>', _filter_network_choices)
            combo.bind('<Return>', lambda _event: _confirm_add())
            combo.focus_set()

            button_row = ttk.Frame(dialog)
            button_row.grid(row=2, column=0, padx=12, pady=(0, 12), sticky='e')
            ttk.Button(button_row, text='Add', command=_confirm_add, width=10).pack(side='right', padx=(4, 0))
            ttk.Button(button_row, text='Cancel', command=_cancel_add, width=10).pack(side='right')

            dialog.protocol('WM_DELETE_WINDOW', _cancel_add)
            dialog.wait_window()

            ssid = selected_network['ssid']
            if not ssid:
                return

            network_list.append(WiFiProfilePreference(ssid=ssid, auto_switch=True, min_db=None))
            _refresh_list()
            listbox.selection_set(tk.END)

        def _remove_network() -> None:
            sel = listbox.curselection()
            if not sel:
                return
            i = sel[0]
            pref = network_list[i]
            if not messagebox.askyesno(
                'Remove Network',
                f'Remove "{pref.ssid}" from the list?',
                parent=win,
            ):
                return
            del network_list[i]
            _refresh_list()
            if network_list:
                listbox.selection_set(min(i, len(network_list) - 1))

        def _toggle_auto_switch() -> None:
            sel = listbox.curselection()
            if not sel:
                return
            i = sel[0]
            pref = network_list[i]
            network_list[i] = WiFiProfilePreference(
                ssid=pref.ssid,
                auto_switch=not pref.auto_switch,
                min_db=pref.min_db,
            )
            _refresh_list()
            listbox.selection_set(i)

        ttk.Button(btn_frame, text='▲ Up', command=_move_up, width=10).pack(pady=2)
        ttk.Button(btn_frame, text='▼ Down', command=_move_down, width=10).pack(pady=2)
        ttk.Separator(btn_frame, orient='horizontal').pack(fill='x', pady=4)
        ttk.Button(btn_frame, text='＋ Add', command=_add_network, width=10).pack(pady=2)
        ttk.Button(btn_frame, text='✕ Remove', command=_remove_network, width=10).pack(pady=2)
        ttk.Separator(btn_frame, orient='horizontal').pack(fill='x', pady=4)
        ttk.Button(btn_frame, text='Auto ⇄', command=_toggle_auto_switch, width=10).pack(pady=2)

        # ---- General options frame -------------------------------------
        frame_opts = ttk.LabelFrame(win, text='General Options', padding=6)
        frame_opts.grid(row=1, column=0, padx=10, pady=4, sticky='ew')

        auto_eth_var = tk.BooleanVar(value=config.auto_disable_wifi_on_ethernet)
        ttk.Checkbutton(
            frame_opts,
            text='Automatically turn off Wi-Fi behavior when Ethernet is connected',
            variable=auto_eth_var,
        ).grid(row=0, column=0, sticky='w')

        ttk.Label(frame_opts, text='Ethernet action:').grid(row=1, column=0, pady=(6, 0), sticky='w')
        ethernet_mode_choices = [
            ('Disconnect + disable auto-connect (recommended)', ETHERNET_WIFI_MODE_DISCONNECT),
            ('Disable Wi-Fi adapter', ETHERNET_WIFI_MODE_DISABLE_ADAPTER),
        ]
        ethernet_mode_var = tk.StringVar(
            value=getattr(config, 'ethernet_wifi_mode', ETHERNET_WIFI_MODE_DISCONNECT)
        )
        ethernet_mode_combo = ttk.Combobox(
            frame_opts,
            state='readonly',
            width=48,
            values=[label for label, _ in ethernet_mode_choices],
        )
        selected_mode = next(
            (label for label, value in ethernet_mode_choices if value == ethernet_mode_var.get()),
            ethernet_mode_choices[0][0],
        )
        ethernet_mode_combo.set(selected_mode)
        ethernet_mode_combo.grid(row=2, column=0, sticky='w')

        def _sync_mode_control_state(*_args) -> None:
            ethernet_mode_combo.configure(state='readonly' if auto_eth_var.get() else 'disabled')

        def _on_mode_selected(_event=None) -> None:
            selected_label = ethernet_mode_combo.get()
            for label, value in ethernet_mode_choices:
                if label == selected_label:
                    ethernet_mode_var.set(value)
                    break

        auto_eth_var.trace_add('write', _sync_mode_control_state)
        ethernet_mode_combo.bind('<<ComboboxSelected>>', _on_mode_selected)
        _sync_mode_control_state()

        splash_var = tk.BooleanVar(value=getattr(config, 'show_startup_splash', True))
        ttk.Checkbutton(
            frame_opts,
            text='Show startup splash',
            variable=splash_var,
        ).grid(row=3, column=0, pady=(8, 0), sticky='w')

        startup_programs_var = tk.BooleanVar(value=getattr(config, 'add_to_startup_programs', False))
        ttk.Checkbutton(
            frame_opts,
            text='Run at Windows startup',
            variable=startup_programs_var,
        ).grid(row=4, column=0, pady=(4, 0), sticky='w')

        # ---- Action buttons --------------------------------------------
        frame_btns = ttk.Frame(win)
        frame_btns.grid(row=2, column=0, padx=10, pady=(4, 10), sticky='e')

        def _on_save() -> None:
            if not network_list:
                messagebox.showerror(
                    'Validation Error',
                    'At least one network entry is required.',
                    parent=win,
                )
                return

            new_config = AppConfig(
                preferred_networks=list(network_list),
                interface_name=config.interface_name,
                scan_interval=config.scan_interval,
                connect_timeout=config.connect_timeout,
                sync_profile_order_on_start=config.sync_profile_order_on_start,
                log_level=config.log_level,
                log_file=config.log_file,
                start_minimized_to_tray=config.start_minimized_to_tray,
                auto_disable_wifi_on_ethernet=auto_eth_var.get(),
                ethernet_wifi_mode=ethernet_mode_var.get(),
                show_wifi_disabled_dialog=getattr(config, 'show_wifi_disabled_dialog', True),
                add_to_startup_programs=startup_programs_var.get(),
                show_startup_splash=splash_var.get(),
                splash_image_path=getattr(config, 'splash_image_path', ''),
                splash_fade_in_ms=getattr(config, 'splash_fade_in_ms', 280),
                splash_hold_ms=getattr(config, 'splash_hold_ms', 1100),
                splash_fade_out_ms=getattr(config, 'splash_fade_out_ms', 280),
                enable_speed_tests=enable_speed_tests,
                speed_test_on_new_connection=speed_test_on_new_connection,
                speed_test_interval=speed_test_interval,
                save_speed_test_history=save_speed_test_history,
                speed_test_history_file=speed_test_history_file,
            )

            try:
                save_config(new_config, self.config_loader.config_path)
            except OSError as exc:
                self.logger.error('Failed to save config: %s', exc)
                messagebox.showerror(
                    'Save Failed',
                    f'Could not write configuration file:\n{exc}',
                    parent=win,
                )
                return

            self.logger.info('Settings saved to %s', self.config_loader.config_path)
            self.service.reload_config(new_config)
            self.config_loader.mark_loaded()

            messagebox.showinfo('Saved', 'Settings have been saved and applied.', parent=win)
            win.destroy()
            self._window = None

        ttk.Button(frame_btns, text='Save', command=_on_save, width=10).pack(side='right', padx=(4, 0))
        ttk.Button(
            frame_btns,
            text='Cancel',
            command=lambda: self._on_cancel(win),
            width=10,
        ).pack(side='right')

    def _on_cancel(self, win: tk.Toplevel) -> None:
        """Close the window without saving."""
        win.destroy()
        self._window = None
