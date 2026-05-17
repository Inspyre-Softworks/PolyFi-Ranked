from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from wifi_pref_manager.ui.settings import SettingsWindow


class SettingsWindowThreadingTests(unittest.TestCase):
    @patch('wifi_pref_manager.ui.settings.run_on_ui_thread')
    def test_open_schedules_window_build_on_ui_thread(self, mock_run_on_ui_thread: Mock) -> None:
        service = Mock()
        service.config = Mock()
        window = SettingsWindow(service=service, config_loader=Mock(), logger=Mock())

        with patch.object(window, '_build_window') as mock_build_window:
            window.open()

            callback = mock_run_on_ui_thread.call_args.args[0]
            self.assertFalse(mock_run_on_ui_thread.call_args.kwargs['wait'])

            fake_root = object()
            callback(fake_root)
            mock_build_window.assert_called_once_with(fake_root)

    @patch('wifi_pref_manager.ui.settings.run_on_ui_thread')
    def test_open_reuses_existing_window(self, mock_run_on_ui_thread: Mock) -> None:
        service = Mock()
        service.config = Mock()
        window = SettingsWindow(service=service, config_loader=Mock(), logger=Mock())
        existing = Mock()
        existing.winfo_exists.return_value = True
        window._window = existing

        with patch.object(window, '_build_window') as mock_build_window:
            window.open()

        callback = mock_run_on_ui_thread.call_args.args[0]
        callback(object())

        existing.lift.assert_called_once()
        existing.focus_force.assert_called_once()
        mock_build_window.assert_not_called()


if __name__ == '__main__':
    unittest.main()
