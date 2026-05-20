"""
Detached output-viewer helpers for tray launches on Windows.
"""

from __future__ import annotations

from collections import deque
import ctypes
from ctypes import wintypes
import io
import logging
from pathlib import Path
import queue
import sys
import threading


IS_WINDOWS = sys.platform == 'win32'
DEFAULT_HISTORY_FORMAT = '[%(asctime)s] - %(levelname)s - %(name)s - %(message)s'

if IS_WINDOWS:
    KERNEL32 = ctypes.WinDLL('kernel32', use_last_error=True)
    KERNEL32.FreeConsole.argtypes = []
    KERNEL32.FreeConsole.restype = wintypes.BOOL
else:
    KERNEL32 = None


class OutputHistoryBuffer:
    """
    Keep a bounded in-memory transcript of output lines.
    """

    def __init__(self, max_chars: int = 250_000) -> None:
        self.max_chars = max_chars
        self._chunks: deque[str] = deque()
        self._char_count = 0
        self._lock = threading.Lock()

    def append(self, text: str) -> None:
        """
        Append text to the rolling history buffer.
        """
        if not text:
            return
        with self._lock:
            self._chunks.append(text)
            self._char_count += len(text)
            while self._char_count > self.max_chars and self._chunks:
                removed = self._chunks.popleft()
                self._char_count -= len(removed)

    def snapshot(self) -> str:
        """
        Return the current buffered transcript.
        """
        with self._lock:
            return ''.join(self._chunks)


class BufferedConsoleStream(io.TextIOBase):
    """
    ``sys.stdout`` / ``sys.stderr`` proxy that records output without owning a console window.
    """

    def __init__(self, manager: 'ConsoleOutputManager', stream_name: str) -> None:
        self.manager = manager
        self.stream_name = stream_name

    @property
    def encoding(self) -> str:
        return 'utf-8'

    def writable(self) -> bool:
        return True

    def isatty(self) -> bool:
        return False

    def fileno(self) -> int:
        stream = self.manager.get_fallback_stream(self.stream_name)
        if stream is None:
            raise OSError('No backing stream is currently available.')
        return stream.fileno()

    def write(self, text: str) -> int:
        self.manager.record_stream_output(text)
        return len(text)

    def flush(self) -> None:
        self.manager.flush_transcript()

    def __getattr__(self, name: str):
        stream = self.manager.get_fallback_stream(self.stream_name)
        if stream is None:
            raise AttributeError(name)
        return getattr(stream, name)


class BufferedLogHandler(logging.Handler):
    """
    Logging handler that records rendered log output into the transcript.
    """

    def __init__(self, manager: 'ConsoleOutputManager') -> None:
        super().__init__()
        self.manager = manager

    def emit(self, record: logging.LogRecord) -> None:
        try:
            rendered = self.format(record)
        except Exception:  # noqa: BLE001
            self.handleError(record)
            return
        self.manager.record_stream_output(f'{rendered}\n')


class ConsoleOutputManager:
    """
    Buffer tray output and expose it through a detached viewer window.
    """

    def __init__(self, transcript_path: Path) -> None:
        self.enabled = IS_WINDOWS
        self.transcript_path = Path(transcript_path)
        self.history = OutputHistoryBuffer()
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        self._console_detached = False
        self._streams_installed = False
        self._transcript_stream: io.TextIOWrapper | None = None
        self._viewer_events: queue.Queue[tuple[str, str | None]] = queue.Queue()
        self._viewer_thread: threading.Thread | None = None
        self._lock = threading.RLock()

    def install_stream_proxies(self) -> None:
        """
        Start buffering stdout/stderr writes for tray sessions.
        """
        if not self.enabled or self._streams_installed:
            return
        self._ensure_transcript_stream(reset_file=True)
        sys.stdout = BufferedConsoleStream(self, 'stdout')
        sys.stderr = BufferedConsoleStream(self, 'stderr')
        self._streams_installed = True

    def attach_logger(self, logger: logging.Logger) -> None:
        """
        Replace direct console logging with transcript-backed logging while preserving file logs.
        """
        if not self.enabled:
            return

        transcript_formatter: logging.Formatter | None = None
        for handler in list(logger.handlers):
            if isinstance(handler, BufferedLogHandler):
                logger.removeHandler(handler)
                handler.close()
                continue
            if isinstance(handler, logging.FileHandler):
                if transcript_formatter is None and handler.formatter is not None:
                    transcript_formatter = handler.formatter
                continue
            if transcript_formatter is None and handler.formatter is not None:
                transcript_formatter = handler.formatter
            logger.removeHandler(handler)
            handler.close()

        buffered_handler = BufferedLogHandler(self)
        buffered_handler.setLevel(logger.level)
        buffered_handler.setFormatter(transcript_formatter or logging.Formatter(DEFAULT_HISTORY_FORMAT))
        logger.addHandler(buffered_handler)

    def hide_console(self) -> None:
        """
        Detach from the process console so closing it cannot terminate the tray app.
        """
        if not self.enabled or self._console_detached:
            return
        if KERNEL32.FreeConsole():
            self._console_detached = True
            return
        if ctypes.get_last_error() == 6:
            self._console_detached = True

    def show_console_with_history(self) -> None:
        """
        Open a detached output viewer window that can be closed safely.
        """
        if not self.enabled:
            return

        self.flush_transcript()
        self._ensure_viewer_thread()
        self._viewer_events.put(('show', self.history.snapshot()))

    def get_fallback_stream(self, stream_name: str):
        """
        Return the original process stream for proxy attribute lookups.
        """
        return self._original_stdout if stream_name == 'stdout' else self._original_stderr

    def record_stream_output(self, text: str) -> None:
        """
        Buffer text in memory and append it to the transcript file.
        """
        if not text:
            return
        self.history.append(text)
        with self._lock:
            self._ensure_transcript_stream(reset_file=False)
            if self._transcript_stream is None:
                return
            self._transcript_stream.write(text)
            self._transcript_stream.flush()
        if self._viewer_thread is not None:
            self._viewer_events.put(('append', text))

    def flush_transcript(self) -> None:
        """
        Flush the on-disk transcript.
        """
        with self._lock:
            if self._transcript_stream is None:
                return
            self._transcript_stream.flush()

    def _ensure_transcript_stream(self, *, reset_file: bool) -> None:
        """
        Open the transcript file for the current tray session.
        """
        self.transcript_path.parent.mkdir(parents=True, exist_ok=True)
        if reset_file:
            self.transcript_path.write_text('', encoding='utf-8')
        if self._transcript_stream is not None:
            return
        self._transcript_stream = self.transcript_path.open(
            'a',
            encoding='utf-8',
            buffering=1,
            errors='replace',
        )

    def _ensure_viewer_thread(self) -> None:
        """
        Start the detached Tk viewer thread once.
        """
        if self._viewer_thread is not None and self._viewer_thread.is_alive():
            return
        self._viewer_thread = threading.Thread(target=self._run_viewer_window, daemon=True)
        self._viewer_thread.start()

    def _run_viewer_window(self) -> None:
        """
        Run the output viewer event loop on a dedicated UI thread.
        """
        import tkinter as tk
        from tkinter import scrolledtext

        root = tk.Tk()
        root.withdraw()
        root.title('PolyFi Output Console')

        window: tk.Toplevel | None = None
        text_widget: scrolledtext.ScrolledText | None = None

        def append_text(text: str) -> None:
            nonlocal text_widget
            if text_widget is None or not text:
                return
            text_widget.configure(state='normal')
            text_widget.insert('end', text)
            text_widget.see('end')
            text_widget.configure(state='disabled')

        def close_window() -> None:
            nonlocal window, text_widget
            if window is not None:
                window.destroy()
            window = None
            text_widget = None

        def show_window(initial_text: str) -> None:
            nonlocal window, text_widget
            if window is not None:
                window.deiconify()
                window.lift()
                window.focus_force()
                return

            window = tk.Toplevel(root)
            window.title('PolyFi Output Console')
            window.geometry('980x600')
            window.minsize(700, 420)
            window.configure(bg='#0b0f12')
            window.protocol('WM_DELETE_WINDOW', close_window)

            header = tk.Label(
                window,
                text='PolyFi output history and live session logs',
                anchor='w',
                bg='#0b0f12',
                fg='#d8e1e8',
                padx=12,
                pady=10,
                font=('Segoe UI', 10, 'bold'),
            )
            header.pack(fill='x')

            text_widget = scrolledtext.ScrolledText(
                window,
                wrap='none',
                bg='#11161c',
                fg='#d8e1e8',
                insertbackground='#d8e1e8',
                selectbackground='#2c4f7b',
                font=('Consolas', 10),
                borderwidth=0,
                padx=10,
                pady=10,
            )
            text_widget.pack(fill='both', expand=True, padx=12, pady=(0, 12))
            text_widget.configure(state='disabled')
            append_text(initial_text)
            window.lift()
            window.focus_force()

        def pump_events() -> None:
            try:
                while True:
                    event_name, payload = self._viewer_events.get_nowait()
                    if event_name == 'show':
                        show_window(payload or '')
                    elif event_name == 'append':
                        append_text(payload or '')
            except queue.Empty:
                pass
            root.after(120, pump_events)

        root.after(120, pump_events)
        root.mainloop()
