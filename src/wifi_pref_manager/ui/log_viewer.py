from __future__ import annotations

import logging
import threading
import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from wifi_pref_manager.config import save_config
from wifi_pref_manager.service import WiFiPreferenceService


class LogHistoryHandler(logging.Handler):
    """In-memory log sink that can stream lines to listeners."""

    def __init__(self, max_lines: int = 2000) -> None:
        super().__init__()
        self.max_lines = max_lines
        self._lines: list[str] = []
        self._listeners: list[Callable[[str], None]] = []
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        line = self.format(record)
        with self._lock:
            self._lines.append(line)
            if len(self._lines) > self.max_lines:
                self._lines = self._lines[-self.max_lines:]
            listeners = list(self._listeners)
        for listener in listeners:
            listener(line)

    def get_lines(self) -> list[str]:
        with self._lock:
            return list(self._lines)

    def add_listener(self, listener) -> None:
        with self._lock:
            self._listeners.append(listener)

    def remove_listener(self, listener) -> None:
        with self._lock:
            self._listeners = [entry for entry in self._listeners if entry != listener]


class LogViewerWindow:
    """Tk-based log history and live-output window."""

    def __init__(
        self,
        service: WiFiPreferenceService,
        config_loader,
        logger: logging.Logger,
        log_handler: LogHistoryHandler,
    ) -> None:
        self.service = service
        self.config_loader = config_loader
        self.logger = logger
        self.log_handler = log_handler
        self._window: tk.Toplevel | None = None
        self._text: tk.Text | None = None
        self._open_lock = threading.Lock()

    def open(self) -> None:
        if not self._open_lock.acquire(blocking=False):
            return
        try:
            if self._window is not None and self._window.winfo_exists():
                self._window.lift()
                self._window.focus_force()
                return
            self._build_window()
        finally:
            self._open_lock.release()

    def _build_window(self) -> None:
        root = tk.Tk()
        root.withdraw()

        win = tk.Toplevel(root)
        win.title('PolyFi: Ranked - Output')
        win.geometry('900x480')
        win.protocol('WM_DELETE_WINDOW', lambda: self._on_close(win, root))
        self._window = win

        text = tk.Text(win, wrap='none')
        text.grid(row=0, column=0, sticky='nsew')
        self._text = text

        scroll_y = ttk.Scrollbar(win, orient='vertical', command=text.yview)
        scroll_y.grid(row=0, column=1, sticky='ns')
        text.configure(yscrollcommand=scroll_y.set)

        win.columnconfigure(0, weight=1)
        win.rowconfigure(0, weight=1)

        for line in self.log_handler.get_lines():
            text.insert('end', line + '\n')
        text.see('end')

        def _on_log_line(line: str) -> None:
            if self._text is None:
                return
            self._text.after(0, lambda: self._append_line(line))

        self.log_handler.add_listener(_on_log_line)

        def _cleanup() -> None:
            self.log_handler.remove_listener(_on_log_line)
            self._text = None
            self._window = None

        win.bind('<Destroy>', lambda _event: _cleanup())
        win.mainloop()

    def _append_line(self, line: str) -> None:
        if self._text is None:
            return
        self._text.insert('end', line + '\n')
        self._text.see('end')

    def _on_close(self, win: tk.Toplevel, root: tk.Tk) -> None:
        config = self.service.config
        if config.show_close_window_hint:
            answer = self._show_close_message_dialog(win)
            if answer == 'cancel':
                return
            if answer == 'dont_tell_again':
                config.show_close_window_hint = False
                save_config(config, self.config_loader.config_path)
                self.config_loader.mark_loaded()
            if answer == 'exit_app':
                self.service.stop()
                root.quit()
                win.destroy()
                root.destroy()
                return

        win.destroy()
        root.destroy()

    def _show_close_message_dialog(self, parent: tk.Toplevel) -> str:
        dialog = tk.Toplevel(parent)
        dialog.title('Window behavior')
        dialog.transient(parent)
        dialog.grab_set()
        dialog.resizable(False, False)

        ttk.Label(
            dialog,
            text='Closing the output window will keep PolyFi running in the tray.',
            wraplength=420,
            justify='left',
        ).grid(row=0, column=0, columnspan=2, padx=12, pady=(12, 8), sticky='w')

        dont_show_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            dialog,
            text="Don't tell me this again",
            variable=dont_show_var,
        ).grid(row=1, column=0, columnspan=2, padx=12, pady=(0, 8), sticky='w')

        result = {'value': 'close_window'}

        def _close_window() -> None:
            result['value'] = 'dont_tell_again' if dont_show_var.get() else 'close_window'
            dialog.destroy()

        def _exit_app() -> None:
            result['value'] = 'exit_app'
            dialog.destroy()

        ttk.Button(dialog, text='Keep Running', command=_close_window, width=14).grid(
            row=2, column=0, padx=(12, 4), pady=(0, 12), sticky='e'
        )
        ttk.Button(dialog, text='Well it Should', command=_exit_app, width=14).grid(
            row=2, column=1, padx=(4, 12), pady=(0, 12), sticky='w'
        )

        dialog.wait_window()
        return result['value']
