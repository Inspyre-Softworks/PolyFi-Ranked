from __future__ import annotations

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from wifi_pref_manager.app import Application, BACKGROUND_TRAY_ENV_VAR
from wifi_pref_manager.ui.tray import TrayApplication
from wifi_pref_manager.scheduler import TaskSchedulerInstaller
from wifi_pref_manager.windows_shell import resolve_runtime_launch_target


class RuntimeLaunchTargetTests(unittest.TestCase):
    def test_packaged_launcher_is_resolved_from_python_directory(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            scripts_dir = Path(tmp_dir) / 'Scripts'
            scripts_dir.mkdir(parents=True)
            python_executable = scripts_dir / 'python.exe'
            python_executable.write_text('', encoding='utf-8')
            packaged_launcher = scripts_dir / 'polyfi-ranked.exe'
            packaged_launcher.write_text('', encoding='utf-8')

            with patch.object(sys, 'executable', str(python_executable)):
                executable, arguments, working_directory = resolve_runtime_launch_target(
                    prefer_windowless=False
                )

            self.assertEqual(executable, packaged_launcher)
            self.assertEqual(arguments, [])
            self.assertEqual(working_directory, scripts_dir)

    def test_scheduler_build_command_uses_compact_launch_string(self) -> None:
        installer = TaskSchedulerInstaller(
            launch_executable=Path(r'C:\Python312\pythonw.exe'),
            launch_arguments=['-m', 'wifi_pref_manager.app', '--tray'],
            task_name='PolyFi Ranked',
        )

        command = installer.build_command()

        self.assertEqual(command[:10], ['schtasks', '/Create', '/F', '/SC', 'ONLOGON', '/RL', 'LIMITED', '/TN', 'PolyFi Ranked', '/TR'])
        self.assertEqual(
            command[10],
            'C:\\Python312\\pythonw.exe -m wifi_pref_manager.app --tray',
        )

    def test_root_runtime_options_survive_subcommand_parsing(self) -> None:
        app = Application()
        args = app.argument_parser.parse_args(['--config', 'custom.toml', '--tray', 'run'])

        self.assertEqual(args.config, 'custom.toml')
        self.assertTrue(args.tray)

    @patch('wifi_pref_manager.app.subprocess.Popen')
    @patch('wifi_pref_manager.app.resolve_runtime_launch_target')
    def test_launch_detached_tray_process_preserves_runtime_arguments(
        self,
        mock_resolve_runtime_launch_target: Mock,
        mock_popen: Mock,
    ) -> None:
        app = Application()
        args = app.argument_parser.parse_args(
            ['run', '--tray', '--config', 'custom.toml', '--log-level', 'DEBUG']
        )
        mock_resolve_runtime_launch_target.return_value = (
            Path(r'C:\Python312\python.exe'),
            ['-m', 'wifi_pref_manager.app'],
            Path(r'C:\Python312'),
        )
        mock_popen.return_value.pid = 4321

        pid = app.launch_detached_tray_process(args)

        self.assertEqual(pid, 4321)
        mock_popen.assert_called_once()
        command = mock_popen.call_args.args[0]
        self.assertEqual(
            command,
            [
                r'C:\Python312\python.exe',
                '-m',
                'wifi_pref_manager.app',
                '--config',
                'custom.toml',
                '--tray',
                '--log-level',
                'DEBUG',
            ],
        )
        self.assertEqual(
            mock_popen.call_args.kwargs['env'][BACKGROUND_TRAY_ENV_VAR],
            '1',
        )
        self.assertTrue(mock_popen.call_args.kwargs['close_fds'])

    def test_tray_setup_callback_marks_icon_visible(self) -> None:
        service = Mock()
        logger = Mock()
        icon = Mock()
        icon.visible = False
        tray = TrayApplication(service=service, logger=logger)

        tray._on_icon_ready(icon)

        self.assertTrue(icon.visible)

    @patch('wifi_pref_manager.ui.tray.show_dialog_async')
    def test_tray_task_helper_warning_does_not_offer_restart(
        self,
        mock_show_dialog_async: Mock,
    ) -> None:
        service = Mock()
        logger = Mock()
        tray = TrayApplication(
            service=service,
            logger=logger,
            restart_as_admin_callback=Mock(),
        )

        tray.show_runtime_warning(
            'Wi-Fi Task Helper Needs Reinstall',
            'Reinstall the helper tasks.',
        )

        mock_show_dialog_async.assert_called_once_with(
            'warning',
            'Wi-Fi Task Helper Needs Reinstall',
            'Reinstall the helper tasks.',
        )

    @patch.object(Application, 'release_single_instance_guard', return_value=False)
    @patch('wifi_pref_manager.app.ctypes.windll.shell32.ShellExecuteW', return_value=5)
    def test_restart_as_administrator_access_denied_mentions_task_helper(
        self,
        _mock_shell_execute: Mock,
        _mock_release_guard: Mock,
    ) -> None:
        app = Application()

        with self.assertRaisesRegex(OSError, 'install the helper tasks instead'):
            app.restart_as_administrator()


if __name__ == '__main__':
    unittest.main()
