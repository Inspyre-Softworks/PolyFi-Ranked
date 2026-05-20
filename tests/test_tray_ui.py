from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from wifi_pref_manager.ui.tray import TrayApplication


class TrayUiTests(unittest.TestCase):
    @patch('wifi_pref_manager.ui.tray.threading.Thread')
    def test_manage_networks_uses_existing_settings_window_directly(
        self,
        mock_thread: Mock,
    ) -> None:
        tray = TrayApplication(service=Mock(), logger=Mock())
        tray._settings_window = Mock()

        tray.on_manage_networks(Mock(), Mock())

        tray._settings_window.open.assert_called_once_with()
        mock_thread.assert_not_called()


if __name__ == '__main__':
    unittest.main()
