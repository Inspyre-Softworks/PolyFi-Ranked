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
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from wifi_pref_manager.config import save_config
from wifi_pref_manager.models import AppConfig, WiFiProfilePreference
from wifi_pref_manager.service import WiFiPreferenceService


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
        self._open_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def open(self) -> None:
        """Open the settings window, or bring it to the foreground if already open."""
        if not self._open_lock.acquire(blocking=False):
            # Another thread is already opening the window
            return
        try:
            if self._window is not None and tk.Toplevel.winfo_exists(self._window):
                self._window.lift()
                self._window.focus_force()
                return

            self._build_window()
        finally:
            self._open_lock.release()

    # ------------------------------------------------------------------
    # Window construction
    # ------------------------------------------------------------------

    def _build_window(self) -> None:
        """Create and show the settings Toplevel window."""
        root = tk.Tk()
        root.withdraw()  # Hide the invisible root window

        win = tk.Toplevel(root)
        win.title('PolyFi: Ranked – Network Settings')
        win.resizable(False, False)
        win.protocol('WM_DELETE_WINDOW', lambda: self._on_cancel(win, root))
        self._window = win

        config = self.service.config

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
            ssid = simpledialog.askstring(
                'Add Network',
                'Enter the SSID (network name):',
                parent=win,
            )
            if not ssid:
                return
            ssid = ssid.strip()
            if not ssid:
                return
            if any(p.ssid == ssid for p in network_list):
                messagebox.showwarning(
                    'Duplicate SSID',
                    f'"{ssid}" is already in the list.',
                    parent=win,
                )
                return
            network_list.append(WiFiProfilePreference(ssid=ssid, auto_switch=True))
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
            text='Automatically disconnect Wi-Fi when Ethernet is connected',
            variable=auto_eth_var,
        ).grid(row=0, column=0, sticky='w')

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
            root.destroy()
            self._window = None

        ttk.Button(frame_btns, text='Save', command=_on_save, width=10).pack(side='right', padx=(4, 0))
        ttk.Button(
            frame_btns,
            text='Cancel',
            command=lambda: self._on_cancel(win, root),
            width=10,
        ).pack(side='right')

        win.mainloop()

    def _on_cancel(self, win: tk.Toplevel, root: tk.Tk) -> None:
        """Close the window without saving."""
        win.destroy()
        root.destroy()
        self._window = None
