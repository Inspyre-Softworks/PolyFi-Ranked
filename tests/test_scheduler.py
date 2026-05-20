from __future__ import annotations

from pathlib import Path
import os
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from wifi_pref_manager.app import Application, BACKGROUND_TRAY_ENV_VAR, SPLASH_SHOWN_ENV_VAR
from wifi_pref_manager.models import AppConfig, WiFiProfilePreference
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
            unrelated_venv = Path(tmp_dir) / 'unrelated-venv'
            unrelated_scripts = unrelated_venv / 'Scripts'
            unrelated_scripts.mkdir(parents=True)
            (unrelated_scripts / 'python.exe').write_text('', encoding='utf-8')

            with patch.dict(os.environ, {'VIRTUAL_ENV': str(unrelated_venv)}, clear=False):
                with patch.object(sys, 'executable', str(python_executable)):
                    executable, arguments, working_directory = resolve_runtime_launch_target(
                        prefer_windowless=False
                    )

            self.assertEqual(executable, packaged_launcher)
            self.assertEqual(arguments, [])
            self.assertEqual(working_directory, scripts_dir)

    def test_windowless_launch_prefers_virtualenv_pythonw(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            venv_root = Path(tmp_dir) / 'venv'
            scripts_dir = venv_root / 'Scripts'
            scripts_dir.mkdir(parents=True)
            python_executable = scripts_dir / 'python.exe'
            python_executable.write_text('', encoding='utf-8')
            pythonw_executable = scripts_dir / 'pythonw.exe'
            pythonw_executable.write_text('', encoding='utf-8')

            base_python = Path(tmp_dir) / 'base-python' / 'python.exe'
            base_python.parent.mkdir(parents=True)
            base_python.write_text('', encoding='utf-8')

            with patch.dict(os.environ, {'VIRTUAL_ENV': str(venv_root)}, clear=False):
                with patch.object(sys, 'executable', str(base_python)):
                    executable, arguments, working_directory = resolve_runtime_launch_target(
                        prefer_windowless=True
                    )

            self.assertEqual(executable, pythonw_executable)
            self.assertEqual(arguments, ['-m', 'wifi_pref_manager.app'])
            self.assertEqual(working_directory, scripts_dir)

    def test_windowless_launch_prefers_sibling_pythonw_before_virtualenv(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir) / 'base-python'
            base_dir.mkdir(parents=True)
            python_executable = base_dir / 'python.exe'
            python_executable.write_text('', encoding='utf-8')
            sibling_pythonw = base_dir / 'pythonw.exe'
            sibling_pythonw.write_text('', encoding='utf-8')

            venv_root = Path(tmp_dir) / 'venv'
            scripts_dir = venv_root / 'Scripts'
            scripts_dir.mkdir(parents=True)
            (scripts_dir / 'python.exe').write_text('', encoding='utf-8')
            venv_pythonw = scripts_dir / 'pythonw.exe'
            venv_pythonw.write_text('', encoding='utf-8')

            with patch.dict(os.environ, {'VIRTUAL_ENV': str(venv_root)}, clear=False):
                with patch.object(sys, 'executable', str(python_executable)):
                    executable, arguments, working_directory = resolve_runtime_launch_target(
                        prefer_windowless=True
                    )

            self.assertEqual(executable, sibling_pythonw)
            self.assertEqual(arguments, ['-m', 'wifi_pref_manager.app'])
            self.assertEqual(working_directory, sibling_pythonw.parent)

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

    def test_runtime_options_include_no_splash_flag(self) -> None:
        app = Application()
        args = app.argument_parser.parse_args(['run', '--tray', '--no-splash'])

        runtime_args = app.build_runtime_argument_list(args)
        self.assertIn('--no-splash', runtime_args)

    def test_start_menu_runtime_options_force_tray_and_splash(self) -> None:
        app = Application()
        args = app.argument_parser.parse_args(['windows', 'start-menu', 'install'])

        runtime_args = app.build_runtime_argument_list(
            args,
            force_tray=True,
            force_show_splash=True,
        )

        self.assertIn('--tray', runtime_args)
        self.assertIn('--show-splash', runtime_args)

    @patch('wifi_pref_manager.app.subprocess.Popen')
    @patch('wifi_pref_manager.app.resolve_runtime_launch_target')
    def test_launch_detached_tray_process_marks_splash_shown_when_suppressed(
        self,
        mock_resolve_runtime_launch_target: Mock,
        mock_popen: Mock,
    ) -> None:
        app = Application()
        args = app.argument_parser.parse_args(['run', '--tray'])
        mock_resolve_runtime_launch_target.return_value = (
            Path(r'C:\Python312\python.exe'),
            ['-m', 'wifi_pref_manager.app'],
            Path(r'C:\Python312'),
        )
        mock_popen.return_value.pid = 4321

        app.launch_detached_tray_process(args, suppress_splash=True)

        env = mock_popen.call_args.kwargs['env']
        self.assertEqual(env[BACKGROUND_TRAY_ENV_VAR], '1')
        self.assertEqual(env[SPLASH_SHOWN_ENV_VAR], '1')

    def test_cli_rejects_conflicting_splash_flags(self) -> None:
        app = Application()
        args = app.argument_parser.parse_args(['run', '--show-splash', '--no-splash'])

        result = app.apply_cli_overrides_from_args(args)
        self.assertEqual(result, 1)

    @patch('wifi_pref_manager.app.show_startup_splash')
    @patch('wifi_pref_manager.app.resolve_splash_image_path')
    def test_maybe_show_startup_splash_only_runs_once_after_success(
        self,
        mock_resolve_splash_image_path: Mock,
        mock_show_startup_splash: Mock,
    ) -> None:
        app = Application()
        logger = Mock()
        mock_resolve_splash_image_path.return_value = Path(r'C:\splash.png')
        config = AppConfig(preferred_networks=[WiFiProfilePreference('ExampleWiFi')])

        first = app.maybe_show_startup_splash(config, logger)
        second = app.maybe_show_startup_splash(config, logger)

        self.assertTrue(first)
        self.assertFalse(second)
        mock_show_startup_splash.assert_called_once_with(
            Path(r'C:\splash.png'),
            fade_in_ms=280,
            hold_ms=1100,
            fade_out_ms=280,
        )

    @patch.object(Application, 'launch_detached_tray_process')
    @patch.object(Application, 'maybe_show_startup_splash')
    @patch.object(Application, 'release_single_instance_guard')
    @patch.object(Application, 'acquire_single_instance_guard', return_value=False)
    @patch('wifi_pref_manager.app.ConfigLoader.load')
    @patch('wifi_pref_manager.app.ConfigLoader.ensure_default_config')
    def test_duplicate_instance_skips_splash_before_detached_tray_launch(
        self,
        mock_ensure_default_config: Mock,
        mock_load: Mock,
        mock_acquire_single_instance_guard: Mock,
        mock_release_single_instance_guard: Mock,
        mock_maybe_show_startup_splash: Mock,
        mock_launch_detached_tray_process: Mock,
    ) -> None:
        app = Application()
        args = app.argument_parser.parse_args(['run', '--tray', '--show-splash'])
        mock_ensure_default_config.return_value = r'C:\config.toml'
        mock_load.return_value = AppConfig(
            preferred_networks=[WiFiProfilePreference('ExampleWiFi')],
        )

        result = app.handle_run_command(args)

        self.assertEqual(result, 0)
        mock_acquire_single_instance_guard.assert_called_once_with(show_dialog_on_duplicate=True)
        mock_release_single_instance_guard.assert_not_called()
        mock_maybe_show_startup_splash.assert_not_called()
        mock_launch_detached_tray_process.assert_not_called()

    def test_ethernet_action_requires_admin_only_for_disable_adapter_mode(self) -> None:
        base = AppConfig(
            preferred_networks=[WiFiProfilePreference('ExampleWiFi')],
            auto_disable_wifi_on_ethernet=True,
        )
        self.assertFalse(Application._ethernet_action_requires_admin(base))

        base.ethernet_wifi_mode = 'disable_adapter'
        self.assertTrue(Application._ethernet_action_requires_admin(base))

        base.auto_disable_wifi_on_ethernet = False
        self.assertFalse(Application._ethernet_action_requires_admin(base))

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

    def test_wifi_network_changed_notification_includes_signal_reason(self) -> None:
        service = Mock()
        logger = Mock()
        tray = TrayApplication(service=service, logger=logger)
        tray.icon = Mock()

        tray.show_wifi_network_changed_notification(
            'HomeWiFi',
            'BackupWiFi',
            'HomeWiFi fell below its minimum signal (-72 dBm observed, -60 dBm required). '
            'BackupWiFi is available at -65 dBm.',
        )

        tray.icon.notify.assert_called_once_with(
            'Switched from HomeWiFi to BackupWiFi. '
            'HomeWiFi fell below its minimum signal (-72 dBm observed, -60 dBm required). '
            'BackupWiFi is available at -65 dBm.',
            title='Wi-Fi Network Changed',
        )

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


if __name__ == '__main__':
    unittest.main()
