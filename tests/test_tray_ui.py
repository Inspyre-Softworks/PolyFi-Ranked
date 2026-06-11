from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from wifi_pref_manager.ui.tray import TrayApplication


class FakeTrayIcon:
    def __init__(self) -> None:
        self.visible = False
        self.stopped = False

    def notify(self, *args: object, **kwargs: object) -> None:
        del args, kwargs

    def run(self, setup: Callable[['FakeTrayIcon'], None] | None = None) -> None:
        if setup is not None:
            setup(self)

    def stop(self) -> None:
        self.stopped = True

    def update_menu(self) -> None:
        return


class TrayUiTests(unittest.TestCase):
    @patch('wifi_pref_manager.ui.tray.show_custom_dialog_async')
    def test_about_opens_about_dialog(self, mock_show_custom_dialog_async: Mock) -> None:
        tray = TrayApplication(service=Mock(), logger=Mock())

        tray.on_about(Mock(), Mock())

        mock_show_custom_dialog_async.assert_called_once()
        call_kwargs = mock_show_custom_dialog_async.call_args.kwargs
        self.assertIn('About', call_kwargs['title'])
        self.assertIn('PolyFi: Ranked version', call_kwargs['message'])
        self.assertIn('Python version', call_kwargs['message'])

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

    @patch('wifi_pref_manager.ui.tray.time.sleep')
    @patch('wifi_pref_manager.ui.tray.time.monotonic')
    @patch('wifi_pref_manager.ui.tray.threading.Thread')
    def test_run_retries_after_quick_unexpected_exit(
        self,
        mock_thread_type: Mock,
        mock_monotonic: Mock,
        mock_sleep: Mock,
    ) -> None:
        service = Mock()
        service.config.auto_check_for_updates = False
        logger = Mock()
        tray = TrayApplication(service=service, logger=logger)
        first_icon = FakeTrayIcon()
        second_icon = FakeTrayIcon()
        tray._build_icon = Mock(side_effect=[first_icon, second_icon])
        mock_thread_type.return_value.start.return_value = None
        mock_monotonic.side_effect = [0.0, 0.5, 1.0, 7.0]

        tray.run()

        service.start.assert_called_once_with()
        service.stop.assert_called_once_with()
        self.assertEqual(tray._build_icon.call_count, 2)
        mock_sleep.assert_called_once_with(tray._TRAY_UNEXPECTED_EXIT_RETRY_DELAY)

    @patch('wifi_pref_manager.ui.tray.time.sleep')
    @patch('wifi_pref_manager.ui.tray.time.monotonic')
    @patch('wifi_pref_manager.ui.tray.threading.Thread')
    def test_run_raises_after_repeated_quick_unexpected_exits(
        self,
        mock_thread_type: Mock,
        mock_monotonic: Mock,
        mock_sleep: Mock,
    ) -> None:
        service = Mock()
        service.config.auto_check_for_updates = False
        logger = Mock()
        tray = TrayApplication(service=service, logger=logger)
        tray._TRAY_UNEXPECTED_EXIT_MAX_RETRIES = 1
        first_icon = FakeTrayIcon()
        second_icon = FakeTrayIcon()
        tray._build_icon = Mock(side_effect=[first_icon, second_icon])
        mock_thread_type.return_value.start.return_value = None
        mock_monotonic.side_effect = [0.0, 0.5, 1.0, 1.4]

        with self.assertRaisesRegex(
            RuntimeError,
            'could not keep the system tray icon running',
        ):
            tray.run()

        service.start.assert_called_once_with()
        service.stop.assert_called_once_with()
        self.assertEqual(tray._build_icon.call_count, 2)
        mock_sleep.assert_called_once_with(tray._TRAY_UNEXPECTED_EXIT_RETRY_DELAY)


if __name__ == '__main__':
    unittest.main()
