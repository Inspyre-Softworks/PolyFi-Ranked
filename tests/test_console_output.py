"""Tests for :mod:`wifi_pref_manager.console_output` null-stream helpers."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from wifi_pref_manager.console_output import NullStream, redirect_none_streams


class NullStreamTests(unittest.TestCase):
    """Tests for :class:`~wifi_pref_manager.console_output.NullStream`."""

    def setUp(self) -> None:
        self.stream = NullStream()

    def test_isatty_returns_false(self) -> None:
        self.assertFalse(self.stream.isatty())

    def test_write_returns_length(self) -> None:
        text = 'hello world'
        result = self.stream.write(text)
        self.assertEqual(result, len(text))

    def test_write_empty_string(self) -> None:
        self.assertEqual(self.stream.write(''), 0)

    def test_read_returns_empty_string(self) -> None:
        self.assertEqual(self.stream.read(), '')

    def test_read_with_size_returns_empty_string(self) -> None:
        self.assertEqual(self.stream.read(10), '')

    def test_readline_returns_empty_string(self) -> None:
        self.assertEqual(self.stream.readline(), '')

    def test_readline_with_size_returns_empty_string(self) -> None:
        self.assertEqual(self.stream.readline(5), '')

    def test_readable_returns_true(self) -> None:
        self.assertTrue(self.stream.readable())

    def test_writable_returns_true(self) -> None:
        self.assertTrue(self.stream.writable())

    def test_flush_does_not_raise(self) -> None:
        self.stream.flush()  # should be a no-op


class RedirectNoneStreamsTests(unittest.TestCase):
    """Tests for :func:`~wifi_pref_manager.console_output.redirect_none_streams`."""

    def _run_with_none_streams(self, stdin=None, stdout=None, stderr=None):
        """
        Temporarily set the given std streams to the supplied values,
        call ``redirect_none_streams()``, capture what they become, then restore.
        """
        original_stdin = sys.stdin
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        try:
            sys.stdin = stdin
            sys.stdout = stdout
            sys.stderr = stderr
            redirect_none_streams()
            return sys.stdin, sys.stdout, sys.stderr
        finally:
            sys.stdin = original_stdin
            sys.stdout = original_stdout
            sys.stderr = original_stderr

    def test_none_stdin_is_replaced_with_null_stream(self) -> None:
        new_stdin, _, _ = self._run_with_none_streams(stdin=None)
        self.assertIsInstance(new_stdin, NullStream)

    def test_none_stdout_is_replaced_with_null_stream(self) -> None:
        _, new_stdout, _ = self._run_with_none_streams(stdout=None)
        self.assertIsInstance(new_stdout, NullStream)

    def test_none_stderr_is_replaced_with_null_stream(self) -> None:
        _, _, new_stderr = self._run_with_none_streams(stderr=None)
        self.assertIsInstance(new_stderr, NullStream)

    def test_non_none_stdin_is_preserved(self) -> None:
        import io
        sentinel = io.StringIO()
        new_stdin, _, _ = self._run_with_none_streams(stdin=sentinel, stdout=None, stderr=None)
        self.assertIs(new_stdin, sentinel)

    def test_non_none_stdout_is_preserved(self) -> None:
        import io
        sentinel = io.StringIO()
        _, new_stdout, _ = self._run_with_none_streams(stdin=None, stdout=sentinel, stderr=None)
        self.assertIs(new_stdout, sentinel)

    def test_non_none_stderr_is_preserved(self) -> None:
        import io
        sentinel = io.StringIO()
        _, _, new_stderr = self._run_with_none_streams(stdin=None, stdout=None, stderr=sentinel)
        self.assertIs(new_stderr, sentinel)

    def test_null_stream_isatty_does_not_raise_after_redirect(self) -> None:
        """isatty() on the installed NullStream must not raise."""
        new_stdin, new_stdout, new_stderr = self._run_with_none_streams()
        for stream in (new_stdin, new_stdout, new_stderr):
            self.assertFalse(stream.isatty())

    def test_all_none_streams_replaced_simultaneously(self) -> None:
        new_stdin, new_stdout, new_stderr = self._run_with_none_streams()
        for stream in (new_stdin, new_stdout, new_stderr):
            self.assertIsInstance(stream, NullStream)


if __name__ == '__main__':
    unittest.main()
