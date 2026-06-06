from __future__ import annotations

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

import wifi_pref_manager.scheduler as scheduler_module
from wifi_pref_manager.app import Application
from wifi_pref_manager.install_record import load_install_record, remove_install_record, upsert_install_record


class InstallRecordTests(unittest.TestCase):
    def test_upsert_install_record_creates_and_updates_json(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            record_path = Path(tmp_dir) / 'install-record.json'

            upsert_install_record(
                record_path,
                install_mode='pip',
                path_updates={
                    'app_data_root': Path(tmp_dir),
                    'config_path': Path(tmp_dir) / 'config.toml',
                },
                feature_updates={'start_menu': True},
            )
            upsert_install_record(
                record_path,
                feature_updates={
                    'start_menu': False,
                    'wifi_tasks': True,
                },
            )

            record = load_install_record(record_path)

            self.assertIsNotNone(record)
            assert record is not None
            self.assertEqual(record['install_mode'], 'pip')
            self.assertEqual(record['paths']['app_data_root'], str(Path(tmp_dir)))
            self.assertEqual(record['features']['start_menu'], False)
            self.assertEqual(record['features']['wifi_tasks'], True)
            self.assertIn('created_at_utc', record)
            self.assertIn('updated_at_utc', record)

            self.assertTrue(remove_install_record(record_path))
            self.assertIsNone(load_install_record(record_path))

    @patch.object(Application, 'sync_install_record_state')
    @patch('wifi_pref_manager.app.StartMenuShortcutManager')
    def test_start_menu_install_updates_install_record(
        self,
        mock_manager_type: Mock,
        mock_sync_install_record_state: Mock,
    ) -> None:
        app = Application()
        args = app.argument_parser.parse_args(['windows', 'start-menu', 'install', '--force'])
        mock_manager_type.return_value.install.return_value = Path(r'C:\PolyFi\PolyFi-Ranked.lnk')

        result = app.handle_start_menu_install_command(args)

        self.assertEqual(result, 0)
        mock_sync_install_record_state.assert_called_once_with(
            None,
            feature_updates={'start_menu': True},
        )

    @patch.object(Application, 'sync_install_record_state')
    @patch.object(Application, 'update_startup_programs_preference', return_value=None)
    @patch('wifi_pref_manager.app.StartupProgramsShortcutManager')
    def test_startup_remove_updates_install_record(
        self,
        mock_manager_type: Mock,
        mock_update_startup_programs_preference: Mock,
        mock_sync_install_record_state: Mock,
    ) -> None:
        del mock_update_startup_programs_preference
        app = Application()
        args = app.argument_parser.parse_args(['windows', 'startup', 'remove'])
        mock_manager_type.return_value.remove.return_value = True
        mock_manager_type.return_value.get_shortcut_path.return_value = Path(
            r'C:\Users\Example\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\PolyFi-Ranked.lnk'
        )

        result = app.handle_startup_remove_command(args)

        self.assertEqual(result, 0)
        mock_sync_install_record_state.assert_called_once_with(
            None,
            feature_updates={'startup_shortcut': False},
        )

    @patch.object(Application, 'sync_install_record_state')
    @patch.object(Application, 'update_scheduled_logon_task_preference', return_value=None)
    @patch('wifi_pref_manager.app.TaskSchedulerInstaller')
    def test_logon_task_install_updates_install_record(
        self,
        mock_installer_type: Mock,
        mock_update_scheduled_logon_task_preference: Mock,
        mock_sync_install_record_state: Mock,
    ) -> None:
        del mock_update_scheduled_logon_task_preference
        app = Application()
        args = app.argument_parser.parse_args(['windows', 'logon-task', 'install'])

        result = app.handle_logon_task_install_command(args)

        self.assertEqual(result, 0)
        mock_installer_type.for_current_runtime.assert_called_once_with(
            task_name='PolyFi Ranked',
            config_path=None,
        )
        mock_installer_type.for_current_runtime.return_value.install.assert_called_once_with(
            emit_message=False
        )
        mock_sync_install_record_state.assert_called_once_with(
            None,
            feature_updates={'scheduled_logon_task': True},
        )

    @patch('wifi_pref_manager.scheduler.update_scheduled_logon_task_preference')
    @patch('wifi_pref_manager.scheduler.upsert_install_record')
    @patch('wifi_pref_manager.scheduler.AppPaths')
    @patch('wifi_pref_manager.scheduler.TaskSchedulerInstaller.for_current_runtime')
    def test_scheduler_install_updates_install_record(
        self,
        mock_for_current_runtime: Mock,
        mock_app_paths_type: Mock,
        mock_upsert_install_record: Mock,
        mock_update_scheduled_logon_task_preference: Mock,
    ) -> None:
        installer = Mock()
        mock_for_current_runtime.return_value = installer
        mock_app_paths_type.return_value = SimpleNamespace(
            app_data_root=Path(r'C:\PolyFiData'),
            config_file=Path(r'C:\PolyFiData\config.toml'),
        )

        result = scheduler_module.main([])

        self.assertEqual(result, 0)
        mock_for_current_runtime.assert_called_once_with(task_name='PolyFi Ranked', config_path=None)
        installer.install.assert_called_once_with()
        mock_update_scheduled_logon_task_preference.assert_called_once_with(
            None,
            True,
            create_if_missing=True,
        )
        mock_upsert_install_record.assert_called_once()
        self.assertEqual(
            mock_upsert_install_record.call_args.kwargs['feature_updates'],
            {'scheduled_logon_task': True},
        )


if __name__ == '__main__':
    unittest.main()
