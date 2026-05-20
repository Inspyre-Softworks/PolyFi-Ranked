from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from wifi_pref_manager.ui import dialogs


class DialogDispatchTests(unittest.TestCase):
    @patch('wifi_pref_manager.ui.dialogs._show_dialog', return_value=True)
    @patch('wifi_pref_manager.ui.dialogs.run_on_ui_thread', return_value=True)
    def test_show_dialog_dispatches_to_ui_thread_and_returns_result(
        self,
        mock_run_on_ui_thread: Mock,
        mock_show_dialog: Mock,
    ) -> None:
        result = dialogs.show_dialog('info', 'Title', 'Message')

        self.assertTrue(result)
        callback = mock_run_on_ui_thread.call_args.args[0]
        self.assertTrue(mock_run_on_ui_thread.call_args.kwargs['wait'])

        fake_root = object()
        callback(fake_root)
        mock_show_dialog.assert_called_once_with(
            fake_root,
            kind='info',
            title='Title',
            message='Message',
            action_label=None,
            action_callback=None,
            continue_label='OK',
        )

    @patch('wifi_pref_manager.ui.dialogs._show_dialog')
    @patch('wifi_pref_manager.ui.dialogs.run_on_ui_thread')
    def test_show_dialog_async_dispatches_without_waiting(
        self,
        mock_run_on_ui_thread: Mock,
        mock_show_dialog: Mock,
    ) -> None:
        dialogs.show_dialog_async('warning', 'Heads up', 'Message')

        callback = mock_run_on_ui_thread.call_args.args[0]
        self.assertFalse(mock_run_on_ui_thread.call_args.kwargs['wait'])

        fake_root = object()
        callback(fake_root)
        mock_show_dialog.assert_called_once_with(
            fake_root,
            kind='warning',
            title='Heads up',
            message='Message',
            action_label=None,
            action_callback=None,
            continue_label='OK',
        )

    @patch('wifi_pref_manager.ui.dialogs._show_custom_dialog')
    @patch('wifi_pref_manager.ui.dialogs.run_on_ui_thread')
    def test_show_custom_dialog_dispatches_to_ui_thread(
        self,
        mock_run_on_ui_thread: Mock,
        mock_show_custom_dialog: Mock,
    ) -> None:
        buttons = [('OK', None)]

        dialogs.show_custom_dialog('Title', 'Body', buttons)

        callback = mock_run_on_ui_thread.call_args.args[0]
        self.assertTrue(mock_run_on_ui_thread.call_args.kwargs['wait'])

        fake_root = object()
        callback(fake_root)
        mock_show_custom_dialog.assert_called_once_with(
            fake_root,
            title='Title',
            message='Body',
            buttons=buttons,
            checkbox_label=None,
            on_checkbox_checked=None,
        )

    @patch('wifi_pref_manager.ui.dialogs._show_custom_dialog')
    @patch('wifi_pref_manager.ui.dialogs.run_on_ui_thread')
    def test_show_custom_dialog_async_dispatches_without_waiting(
        self,
        mock_run_on_ui_thread: Mock,
        mock_show_custom_dialog: Mock,
    ) -> None:
        buttons = [('OK', None)]

        dialogs.show_custom_dialog_async('Title', 'Body', buttons)

        callback = mock_run_on_ui_thread.call_args.args[0]
        self.assertFalse(mock_run_on_ui_thread.call_args.kwargs['wait'])

        fake_root = object()
        callback(fake_root)
        mock_show_custom_dialog.assert_called_once_with(
            fake_root,
            title='Title',
            message='Body',
            buttons=buttons,
            checkbox_label=None,
            on_checkbox_checked=None,
        )


if __name__ == '__main__':
    unittest.main()
