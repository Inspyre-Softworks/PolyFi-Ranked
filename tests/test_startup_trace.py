from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from wifi_pref_manager.startup_trace import append_startup_trace_line


class AppendStartupTraceLineTests(unittest.TestCase):
    """Tests for :func:`~wifi_pref_manager.startup_trace.append_startup_trace_line`."""

    def test_creates_parent_directory_when_absent(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            trace_path = Path(tmp_dir) / 'nested' / 'sub' / 'trace.log'

            self.assertFalse(trace_path.parent.exists())
            append_startup_trace_line(trace_path, 'hello')
            self.assertTrue(trace_path.parent.exists())

    def test_creates_trace_file_with_one_line(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            trace_path = Path(tmp_dir) / 'trace.log'

            append_startup_trace_line(trace_path, 'startup complete')

            lines = trace_path.read_text(encoding='utf-8').splitlines()
            self.assertEqual(len(lines), 1)

    def test_line_contains_message(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            trace_path = Path(tmp_dir) / 'trace.log'

            append_startup_trace_line(trace_path, 'my-message')

            content = trace_path.read_text(encoding='utf-8')
            self.assertIn('my-message', content)

    def test_line_contains_iso_timestamp(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            trace_path = Path(tmp_dir) / 'trace.log'
            before = datetime.now().isoformat(timespec='seconds')

            append_startup_trace_line(trace_path, 'ts-check')

            content = trace_path.read_text(encoding='utf-8')
            # The line must start with a bracketed ISO timestamp
            self.assertRegex(content, r'^\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\]')

    def test_successive_appends_produce_multiple_lines(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            trace_path = Path(tmp_dir) / 'trace.log'

            append_startup_trace_line(trace_path, 'first')
            append_startup_trace_line(trace_path, 'second')
            append_startup_trace_line(trace_path, 'third')

            lines = trace_path.read_text(encoding='utf-8').splitlines()
            self.assertEqual(len(lines), 3)
            self.assertIn('first', lines[0])
            self.assertIn('second', lines[1])
            self.assertIn('third', lines[2])

    def test_file_is_utf8_encoded(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            trace_path = Path(tmp_dir) / 'trace.log'

            append_startup_trace_line(trace_path, 'caf\u00e9')  # café

            content = trace_path.read_text(encoding='utf-8')
            self.assertIn('café', content)

    def test_raises_oserror_on_unwritable_path(self) -> None:
        # A path whose parent cannot be created (e.g. rooted under a file)
        with TemporaryDirectory() as tmp_dir:
            # Create a *file* at the location that would need to be a directory
            blocker = Path(tmp_dir) / 'blocker'
            blocker.write_text('x', encoding='utf-8')
            trace_path = blocker / 'trace.log'

            with self.assertRaises(OSError):
                append_startup_trace_line(trace_path, 'should fail')


if __name__ == '__main__':
    unittest.main()
