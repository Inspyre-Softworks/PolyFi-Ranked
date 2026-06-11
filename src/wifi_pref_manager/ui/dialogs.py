"""
Reusable Tkinter dialog helpers for lightweight runtime notifications.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
import ctypes
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk


MB_OK = 0x00000000
MB_ICONERROR = 0x00000010
MB_ICONWARNING = 0x00000030
MB_ICONINFORMATION = 0x00000040
MB_SETFOREGROUND = 0x00010000
MB_TOPMOST = 0x00040000
UI_QUEUE_POLL_INTERVAL_MS = 100


class _TkUiDispatcher:
    """
    Run all Tk work on a single dedicated UI thread.
    """

    def __init__(self) -> None:
        self._ready_event = threading.Event()
        self._root: tk.Tk | None = None
        self._owner_thread_id: int | None = None
        self._thread: threading.Thread | None = None
        self._start_lock = threading.Lock()
        self._queue: queue.Queue[tuple[Callable[[tk.Tk], object], threading.Event | None, list[object]]] = (
            queue.Queue()
        )

    def _thread_main(self) -> None:
        root = tk.Tk()
        root.withdraw()
        self._root = root
        self._owner_thread_id = threading.get_ident()
        self._ready_event.set()
        root.after(UI_QUEUE_POLL_INTERVAL_MS, self._drain_queue)
        root.mainloop()

    def _ensure_started(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            self._ready_event.wait()
            return

        with self._start_lock:
            if self._thread is None or not self._thread.is_alive():
                self._ready_event.clear()
                self._thread = threading.Thread(
                    target=self._thread_main,
                    daemon=True,
                    name='polyfi-tk-ui',
                )
                self._thread.start()

        self._ready_event.wait()

    def _drain_queue(self) -> None:
        root = self._root
        if root is None:
            return

        while True:
            try:
                callback, done_event, result_holder = self._queue.get_nowait()
            except queue.Empty:
                break

            try:
                result_holder.append(('result', callback(root)))
            except Exception as exc:  # noqa: BLE001
                result_holder.append(('error', exc))
            finally:
                if done_event is not None:
                    done_event.set()

        root.after(UI_QUEUE_POLL_INTERVAL_MS, self._drain_queue)

    def call(self, callback: Callable[[tk.Tk], object], *, wait: bool) -> object | None:
        """
        Execute ``callback`` on the shared Tk UI thread.
        """
        self._ensure_started()

        if threading.get_ident() == self._owner_thread_id and self._root is not None:
            return callback(self._root)

        done_event = threading.Event() if wait else None
        result_holder: list[object] = []
        self._queue.put((callback, done_event, result_holder))
        if done_event is None:
            return None

        done_event.wait()
        result_type, value = result_holder[0]
        if result_type == 'error':
            raise value  # type: ignore[misc]
        return value


_UI_DISPATCHER = _TkUiDispatcher()


def run_on_ui_thread(callback: Callable[[tk.Tk], object], *, wait: bool) -> object | None:
    """
    Execute a callable on the shared Tk UI thread.
    """
    return _UI_DISPATCHER.call(callback, wait=wait)


def show_native_message_box(kind: str, title: str, message: str) -> None:
    """
    Display a native Windows message box when available.

    Parameters:
        kind:
            Dialog kind such as ``warning``, ``error``, or ``info``.
        title:
            Dialog title text.
        message:
            Dialog body text.
    """
    icon_flag = MB_ICONINFORMATION
    if kind == 'error':
        icon_flag = MB_ICONERROR
    elif kind == 'warning':
        icon_flag = MB_ICONWARNING

    try:
        user32 = ctypes.windll.user32
    except AttributeError:
        return

    user32.MessageBoxW(
        None,
        str(message),
        str(title),
        MB_OK | icon_flag | MB_TOPMOST | MB_SETFOREGROUND,
    )


def _show_dialog(
    root: tk.Tk,
    kind: str,
    title: str,
    message: str,
    action_label: str | None = None,
    action_callback: Callable[[], None] | None = None,
    continue_label: str = 'OK',
) -> bool:
    """
    Display a modal Tkinter message box on the shared hidden root.

    Parameters:
        kind:
            Dialog kind such as ``warning``, ``error``, or ``info``.
        title:
            Dialog title text.
        message:
            Dialog body text.
        action_label:
            Optional label for a secondary action button.
        action_callback:
            Optional callback invoked when the action button is pressed.
        continue_label:
            Label for the dismiss/continue button.

    Returns:
        True when the optional action button was pressed, otherwise False.
    """
    action_requested = False

    if action_label and action_callback is not None:
        dialog = tk.Toplevel(root)
        dialog.title(title)
        dialog.attributes('-topmost', True)
        dialog.resizable(False, False)
        dialog.protocol('WM_DELETE_WINDOW', dialog.destroy)

        frame = ttk.Frame(dialog, padding=12)
        frame.grid(row=0, column=0, sticky='nsew')

        icon = 'Warning' if kind == 'warning' else 'Error' if kind == 'error' else 'Information'
        ttk.Label(frame, text=icon, font=('Segoe UI', 10, 'bold')).grid(row=0, column=0, sticky='w')
        ttk.Label(frame, text=message, wraplength=420, justify='left').grid(
            row=1,
            column=0,
            pady=(8, 12),
            sticky='w',
        )

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=2, column=0, sticky='e')

        def _run_action() -> None:
            nonlocal action_requested
            action_requested = True
            dialog.destroy()
            action_callback()

        ttk.Button(button_frame, text=continue_label, command=dialog.destroy).pack(side='right')
        ttk.Button(button_frame, text=action_label, command=_run_action).pack(side='right', padx=(0, 8))

        dialog.update_idletasks()
        dialog.geometry(
            f'+{dialog.winfo_screenwidth() // 2 - dialog.winfo_width() // 2}+'
            f'{dialog.winfo_screenheight() // 2 - dialog.winfo_height() // 2}'
        )
        dialog.grab_set()
        dialog.focus_force()
        dialog.wait_window()
    elif kind == 'error':
        root.attributes('-topmost', True)
        messagebox.showerror(title, message, parent=root)
    elif kind == 'info':
        root.attributes('-topmost', True)
        messagebox.showinfo(title, message, parent=root)
    else:
        root.attributes('-topmost', True)
        messagebox.showwarning(title, message, parent=root)

    return action_requested


def _show_custom_dialog(
    root: tk.Tk,
    title: str,
    message: str,
    buttons: Sequence[tuple[str, Callable[[], None] | None]],
    checkbox_label: str | None = None,
    on_checkbox_checked: Callable[[], None] | None = None,
) -> None:
    """
    Display a custom modal dialog on the shared Tk UI root.
    """
    dialog = tk.Toplevel(root)
    dialog.title(title)
    dialog.attributes('-topmost', True)
    dialog.resizable(False, False)

    frame = ttk.Frame(dialog, padding=12)
    frame.grid(row=0, column=0, sticky='nsew')

    ttk.Label(frame, text=message, wraplength=440, justify='left').grid(
        row=0,
        column=0,
        sticky='w',
    )

    suppress_var = tk.BooleanVar(value=False)
    if checkbox_label:
        ttk.Checkbutton(frame, text=checkbox_label, variable=suppress_var).grid(
            row=1,
            column=0,
            pady=(10, 12),
            sticky='w',
        )
        button_row = 2
    else:
        button_row = 1

    button_frame = ttk.Frame(frame)
    button_frame.grid(row=button_row, column=0, sticky='e')

    def _close(callback: Callable[[], None] | None) -> None:
        checked = suppress_var.get()
        dialog.destroy()
        if checked and on_checkbox_checked is not None:
            on_checkbox_checked()
        if callback is not None:
            callback()

    for index, (label, callback) in enumerate(reversed(tuple(buttons))):
        ttk.Button(
            button_frame,
            text=label,
            command=lambda callback=callback: _close(callback),
        ).pack(side='right', padx=(0 if index == 0 else 8, 0))

    dialog.protocol('WM_DELETE_WINDOW', lambda: _close(None))
    dialog.update_idletasks()
    dialog.geometry(
        f'+{dialog.winfo_screenwidth() // 2 - dialog.winfo_width() // 2}+'
        f'{dialog.winfo_screenheight() // 2 - dialog.winfo_height() // 2}'
    )
    dialog.grab_set()
    dialog.focus_force()
    dialog.wait_window()


def show_dialog(
    kind: str,
    title: str,
    message: str,
    action_label: str | None = None,
    action_callback: Callable[[], None] | None = None,
    continue_label: str = 'OK',
) -> bool:
    """
    Display a modal message dialog on the current thread.

    Parameters:
        kind:
            Dialog kind such as ``warning``, ``error``, or ``info``.
        title:
            Dialog title text.
        message:
            Dialog body text.
        action_label:
            Optional label for a secondary action button.
        action_callback:
            Optional callback invoked when the action button is pressed.
        continue_label:
            Label for the dismiss/continue button.

    Returns:
        True when the optional action button was pressed, otherwise False.
    """
    return bool(
        run_on_ui_thread(
            lambda root: _show_dialog(
                root,
                kind=kind,
                title=title,
                message=message,
                action_label=action_label,
                action_callback=action_callback,
                continue_label=continue_label,
            ),
            wait=True,
        )
    )


def show_dialog_async(
    kind: str,
    title: str,
    message: str,
    action_label: str | None = None,
    action_callback: Callable[[], None] | None = None,
    continue_label: str = 'OK',
) -> None:
    """
    Display a modal message box on a background UI thread.

    Parameters:
        kind:
            Dialog kind such as ``warning``, ``error``, or ``info``.
        title:
            Dialog title text.
        message:
            Dialog body text.
        action_label:
            Optional label for a secondary action button.
        action_callback:
            Optional callback invoked when the action button is pressed.
        continue_label:
            Label for the dismiss/continue button.
    """
    run_on_ui_thread(
        lambda root: _show_dialog(
            root,
            kind=kind,
            title=title,
            message=message,
            action_label=action_label,
            action_callback=action_callback,
            continue_label=continue_label,
        ),
        wait=False,
    )


def show_custom_dialog(
    title: str,
    message: str,
    buttons: Sequence[tuple[str, Callable[[], None] | None]],
    checkbox_label: str | None = None,
    on_checkbox_checked: Callable[[], None] | None = None,
) -> None:
    """
    Display a custom modal dialog with multiple buttons and an optional checkbox.

    Parameters:
        title:
            Dialog title text.
        message:
            Dialog body text.
        buttons:
            Ordered button definitions as ``(label, callback)`` tuples.
        checkbox_label:
            Optional checkbox label.
        on_checkbox_checked:
            Optional callback invoked when the checkbox is checked and the dialog closes.
    """
    run_on_ui_thread(
        lambda root: _show_custom_dialog(
            root,
            title=title,
            message=message,
            buttons=buttons,
            checkbox_label=checkbox_label,
            on_checkbox_checked=on_checkbox_checked,
        ),
        wait=True,
    )


def show_custom_dialog_async(
    title: str,
    message: str,
    buttons: Sequence[tuple[str, Callable[[], None] | None]],
    checkbox_label: str | None = None,
    on_checkbox_checked: Callable[[], None] | None = None,
) -> None:
    """
    Display a custom modal dialog on a background UI thread.

    Parameters:
        title:
            Dialog title text.
        message:
            Dialog body text.
        buttons:
            Ordered button definitions as ``(label, callback)`` tuples.
        checkbox_label:
            Optional checkbox label.
        on_checkbox_checked:
            Optional callback invoked when the checkbox is checked and the dialog closes.
    """
    run_on_ui_thread(
        lambda root: _show_custom_dialog(
            root,
            title=title,
            message=message,
            buttons=buttons,
            checkbox_label=checkbox_label,
            on_checkbox_checked=on_checkbox_checked,
        ),
        wait=False,
    )
