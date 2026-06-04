from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

import wifi_pref_manager.app as app_module
from wifi_pref_manager.app import Application, BACKGROUND_TRAY_ENV_VAR, SPLASH_SHOWN_ENV_VAR
from wifi_pref_manager.models import AppConfig, WiFiProfilePreference
from wifi_pref_manager.scheduler import TaskSchedulerInstaller
from wifi_pref_manager.ui.tray import TrayApplication
from wifi_pref_manager.windows_shell import StartupProgramsShortcutManager, resolve_runtime_launch_target


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

    def test_non_windowless_launch_uses_sibling_python_when_running_under_pythonw(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir) / 'base-python'
            base_dir.mkdir(parents=True)
            pythonw_executable = base_dir / 'pythonw.exe'
            pythonw_executable.write_text('', encoding='utf-8')
            sibling_python = base_dir / 'python.exe'
            sibling_python.write_text('', encoding='utf-8')

            with patch.object(sys, 'executable', str(pythonw_executable)):
                executable, arguments, working_directory = resolve_runtime_launch_target(
                    prefer_windowless=False
                )

            self.assertEqual(executable, sibling_python)
            self.assertEqual(arguments, ['-m', 'wifi_pref_manager.app'])
            self.assertEqual(working_directory, sibling_python.parent)

    def test_non_windowless_launch_prefers_scripts_console_launcher(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir) / 'base-python'
            base_dir.mkdir(parents=True)
            python_executable = base_dir / 'python.exe'
            python_executable.write_text('', encoding='utf-8')
            scripts_dir = base_dir / 'Scripts'
            scripts_dir.mkdir()
            scripts_launcher = scripts_dir / 'polyfi-ranked.exe'
            scripts_launcher.write_text('', encoding='utf-8')

            with patch.object(sys, 'executable', str(python_executable)):
                executable, arguments, working_directory = resolve_runtime_launch_target(
                    prefer_windowless=False
                )

            self.assertEqual(executable, scripts_launcher)
            self.assertEqual(arguments, [])
            self.assertEqual(working_directory, scripts_dir)

    @patch('wifi_pref_manager.windows_shell.resolve_runtime_launch_target')
    def test_startup_programs_shortcut_avoids_windowless_launcher(
        self,
        mock_resolve_runtime_launch_target: Mock,
    ) -> None:
        manager = StartupProgramsShortcutManager(
            paths=SimpleNamespace(
                shortcut_icon_file=Path(r'C:\PolyFi\polyfi.ico'),
                startup_programs_shortcut_file=Path(r'C:\PolyFi\Startup\PolyFi-Ranked.lnk'),
            )
        )
        mock_resolve_runtime_launch_target.return_value = (
            Path(r'C:\Python312\python.exe'),
            ['-m', 'wifi_pref_manager.app'],
            Path(r'C:\Python312'),
        )

        spec = manager._build_shortcut_spec(['--tray'])

        mock_resolve_runtime_launch_target.assert_called_once_with(prefer_windowless=False)
        self.assertEqual(spec.target_path, Path(r'C:\Python312\python.exe'))
        self.assertEqual(
            spec.arguments,
            ['-m', 'wifi_pref_manager.app', '--tray'],
        )

    @patch('wifi_pref_manager.scheduler.resolve_runtime_launch_target')
    def test_scheduler_current_runtime_uses_console_launch(
        self,
        mock_resolve_runtime_launch_target: Mock,
    ) -> None:
        mock_resolve_runtime_launch_target.return_value = (
            Path(r'C:\Python312\python.exe'),
            ['-m', 'wifi_pref_manager.app'],
            Path(r'C:\Python312'),
        )

        installer = TaskSchedulerInstaller.for_current_runtime(task_name='PolyFi Ranked')

        mock_resolve_runtime_launch_target.assert_called_once_with(prefer_windowless=False)
        self.assertEqual(installer.launch_executable, Path(r'C:\Python312\python.exe'))
        self.assertEqual(
            installer.launch_arguments,
            ['-m', 'wifi_pref_manager.app', '--tray'],
        )

    @patch('wifi_pref_manager.scheduler.resolve_runtime_launch_target')
    def test_scheduler_current_runtime_can_include_config_path(
        self,
        mock_resolve_runtime_launch_target: Mock,
    ) -> None:
        mock_resolve_runtime_launch_target.return_value = (
            Path(r'C:\Python312\python.exe'),
            ['-m', 'wifi_pref_manager.app'],
            Path(r'C:\Python312'),
        )

        installer = TaskSchedulerInstaller.for_current_runtime(
            task_name='PolyFi Ranked',
            config_path='custom.toml',
        )

        self.assertEqual(
            installer.launch_arguments,
            ['-m', 'wifi_pref_manager.app', '--config', 'custom.toml', '--tray'],
        )

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

    def test_scheduler_build_uninstall_command_targets_named_task(self) -> None:
        installer = TaskSchedulerInstaller(
            launch_executable=Path(r'C:\Python312\pythonw.exe'),
            task_name='PolyFi Custom Startup',
        )

        command = installer.build_uninstall_command()

        self.assertEqual(
            command,
            ['schtasks', '/Delete', '/F', '/TN', 'PolyFi Custom Startup'],
        )

    @patch('wifi_pref_manager.scheduler.subprocess.run')
    def test_scheduler_uninstall_returns_false_when_task_missing(self, mock_run: Mock) -> None:
        installer = TaskSchedulerInstaller(
            launch_executable=Path(r'C:\Python312\pythonw.exe'),
        )
        mock_run.return_value.returncode = 1
        mock_run.return_value.stdout = ''
        mock_run.return_value.stderr = 'ERROR: The system cannot find the file specified.'

        removed = installer.uninstall()

        self.assertFalse(removed)

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
        self.assertNotIn('--direct-tray', runtime_args)
        self.assertIn('--show-splash', runtime_args)

    def test_startup_shortcut_arguments_include_config_and_tray(self) -> None:
        app = Application()

        runtime_args = app.build_startup_shortcut_argument_list('custom.toml')

        self.assertEqual(runtime_args, ['--config', 'custom.toml', '--tray'])

    @patch('wifi_pref_manager.app.StartupProgramsShortcutManager')
    def test_sync_startup_programs_preference_installs_shortcut_when_enabled(
        self,
        mock_manager_type: Mock,
    ) -> None:
        app = Application()
        app.active_config_path = Path('custom.toml')
        logger = Mock()
        shortcut_path = Mock()
        shortcut_path.exists.return_value = False
        manager = mock_manager_type.return_value
        manager.get_shortcut_path.return_value = shortcut_path
        config = AppConfig(
            preferred_networks=[WiFiProfilePreference('ExampleWiFi')],
            add_to_startup_programs=True,
        )

        app.sync_startup_programs_preference(config, logger)

        manager.install.assert_called_once_with(
            ['--config', 'custom.toml', '--tray'],
            overwrite=False,
        )

    @patch('wifi_pref_manager.app.StartupProgramsShortcutManager')
    def test_sync_startup_programs_preference_removes_shortcut_when_disabled(
        self,
        mock_manager_type: Mock,
    ) -> None:
        app = Application()
        logger = Mock()
        shortcut_path = Mock()
        manager = mock_manager_type.return_value
        manager.get_shortcut_path.return_value = shortcut_path
        manager.remove.return_value = True
        config = AppConfig(
            preferred_networks=[WiFiProfilePreference('ExampleWiFi')],
            add_to_startup_programs=False,
        )

        app.sync_startup_programs_preference(config, logger)

        manager.remove.assert_called_once_with()

    @patch('wifi_pref_manager.app.TaskSchedulerInstaller')
    def test_sync_scheduled_logon_task_installs_when_enabled(
        self,
        mock_installer_type: Mock,
    ) -> None:
        app = Application()
        app.active_config_path = Path('custom.toml')
        logger = Mock()
        config = AppConfig(
            preferred_networks=[WiFiProfilePreference('ExampleWiFi')],
            add_scheduled_logon_task=True,
        )

        app.sync_scheduled_logon_task_preference(config, logger)

        mock_installer_type.for_current_runtime.assert_called_once_with(
            task_name='PolyFi Ranked',
            config_path=Path('custom.toml'),
        )
        mock_installer_type.for_current_runtime.return_value.install.assert_called_once_with(
            emit_message=False
        )

    @patch('wifi_pref_manager.app.TaskSchedulerInstaller')
    def test_sync_scheduled_logon_task_skips_missing_config_key(
        self,
        mock_installer_type: Mock,
    ) -> None:
        app = Application()
        logger = Mock()
        config = AppConfig(
            preferred_networks=[WiFiProfilePreference('ExampleWiFi')],
            add_scheduled_logon_task=None,
        )

        app.sync_scheduled_logon_task_preference(config, logger)

        mock_installer_type.assert_not_called()

    @patch('wifi_pref_manager.app.TaskSchedulerInstaller')
    def test_sync_scheduled_logon_task_removes_when_disabled(
        self,
        mock_installer_type: Mock,
    ) -> None:
        app = Application()
        logger = Mock()
        installer = mock_installer_type.return_value
        installer.uninstall.return_value = True
        config = AppConfig(
            preferred_networks=[WiFiProfilePreference('ExampleWiFi')],
            add_scheduled_logon_task=False,
        )

        app.sync_scheduled_logon_task_preference(config, logger)

        mock_installer_type.assert_called_once_with(
            launch_executable=Path(sys.executable),
            task_name='PolyFi Ranked',
        )
        installer.uninstall.assert_called_once_with()

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
        mock_resolve_runtime_launch_target.assert_called_once_with(prefer_windowless=True)

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

    @patch.object(Application, 'launch_detached_tray_process', return_value=4321)
    @patch.object(Application, 'maybe_show_startup_splash', return_value=True)
    @patch.object(Application, 'release_single_instance_guard')
    @patch.object(Application, 'acquire_single_instance_guard', return_value=True)
    @patch('wifi_pref_manager.app.ConfigLoader.load')
    @patch('wifi_pref_manager.app.ConfigLoader.ensure_default_config')
    def test_handle_run_command_tray_shortcut_relaunches_detached_process(
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
        mock_release_single_instance_guard.assert_called_once_with()
        mock_maybe_show_startup_splash.assert_called_once()
        mock_launch_detached_tray_process.assert_called_once_with(args, suppress_splash=True)

    @patch('wifi_pref_manager.app.TrayApplication')
    @patch('wifi_pref_manager.app.WiFiPreferenceService')
    @patch('wifi_pref_manager.app.configure_logging')
    @patch('wifi_pref_manager.app.ConsoleOutputManager')
    @patch.object(Application, 'launch_detached_tray_process')
    @patch.object(Application, 'maybe_show_startup_splash')
    @patch.object(Application, 'release_single_instance_guard')
    @patch.object(Application, 'acquire_single_instance_guard', return_value=True)
    @patch.object(Application, 'handle_startup_admin_requirements')
    @patch.object(Application, 'sync_startup_programs_preference')
    @patch.object(Application, 'set_windows_app_user_model_id')
    @patch('wifi_pref_manager.app.ConfigLoader.load')
    @patch('wifi_pref_manager.app.ConfigLoader.ensure_default_config')
    def test_handle_run_command_direct_tray_skips_detached_relaunch(
        self,
        mock_ensure_default_config: Mock,
        mock_load: Mock,
        mock_set_windows_app_user_model_id: Mock,
        mock_sync_startup_programs_preference: Mock,
        mock_handle_startup_admin_requirements: Mock,
        mock_acquire_single_instance_guard: Mock,
        mock_release_single_instance_guard: Mock,
        mock_maybe_show_startup_splash: Mock,
        mock_launch_detached_tray_process: Mock,
        mock_console_output_manager_type: Mock,
        mock_configure_logging: Mock,
        mock_wifi_preference_service_type: Mock,
        mock_tray_application_type: Mock,
    ) -> None:
        del (
            mock_set_windows_app_user_model_id,
            mock_sync_startup_programs_preference,
            mock_handle_startup_admin_requirements,
            mock_maybe_show_startup_splash,
            mock_wifi_preference_service_type,
        )
        app = Application()
        args = app.argument_parser.parse_args(['run', '--direct-tray'])
        mock_ensure_default_config.return_value = r'C:\config.toml'
        mock_load.return_value = AppConfig(
            preferred_networks=[WiFiProfilePreference('ExampleWiFi')],
        )
        mock_configure_logging.return_value = Mock()

        result = app.handle_run_command(args)

        self.assertEqual(result, 0)
        mock_launch_detached_tray_process.assert_not_called()
        mock_acquire_single_instance_guard.assert_called_once_with(show_dialog_on_duplicate=True)
        mock_release_single_instance_guard.assert_called_once_with()
        mock_console_output_manager_type.return_value.hide_console.assert_called_once_with()
        mock_tray_application_type.return_value.run.assert_called_once_with()

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
        self.assertIs(mock_popen.call_args.kwargs['stdin'], subprocess.DEVNULL)
        self.assertIs(mock_popen.call_args.kwargs['stdout'], subprocess.DEVNULL)
        self.assertIs(mock_popen.call_args.kwargs['stderr'], subprocess.DEVNULL)
        mock_resolve_runtime_launch_target.assert_called_once_with(prefer_windowless=True)

    @patch('wifi_pref_manager.app.subprocess.Popen')
    @patch('wifi_pref_manager.app.resolve_runtime_launch_target')
    def test_launch_detached_tray_process_sets_windows_detach_flags(
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

        with patch.object(app_module.subprocess, 'DETACHED_PROCESS', 0x00000008, create=True):
            with patch.object(app_module.subprocess, 'CREATE_NEW_PROCESS_GROUP', 0x00000200, create=True):
                app.launch_detached_tray_process(args)

        self.assertEqual(
            mock_popen.call_args.kwargs['creationflags'],
            0x00000008 | 0x00000200,
        )

    @patch('wifi_pref_manager.app.ConfigLoader')
    def test_purge_application_data_removes_custom_files_and_app_dirs(
        self,
        mock_config_loader_type: Mock,
    ) -> None:
        app = Application()

        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config_dir = root / 'ConfigRoot' / 'PolyFi-Ranked'
            local_data_dir = root / 'DataRoot' / 'PolyFi-Ranked'
            legacy_config_dir = root / 'LegacyConfigRoot' / 'polyfi_ranked'
            legacy_local_dir = root / 'LegacyDataRoot' / 'polyfi_ranked'
            for directory in (config_dir, local_data_dir, legacy_config_dir, legacy_local_dir):
                directory.mkdir(parents=True)

            (config_dir / 'config.toml').write_text('config', encoding='utf-8')
            (config_dir / 'config.example.toml').write_text('example', encoding='utf-8')
            (local_data_dir / 'polyfi.log').write_text('log', encoding='utf-8')
            (local_data_dir / 'speedtest_history.jsonl').write_text('history', encoding='utf-8')
            (legacy_config_dir / 'old.toml').write_text('legacy-config', encoding='utf-8')
            (legacy_local_dir / 'old.log').write_text('legacy-log', encoding='utf-8')

            custom_dir = root / 'CustomFiles'
            custom_dir.mkdir()
            custom_config = custom_dir / 'polyfi-config.toml'
            custom_config.write_text('custom-config', encoding='utf-8')
            custom_log = custom_dir / 'polyfi.log'
            custom_log.write_text('custom-log', encoding='utf-8')
            custom_history = custom_dir / 'history.jsonl'
            custom_history.write_text('custom-history', encoding='utf-8')

            app.paths = SimpleNamespace(
                config_file=config_dir / 'config.toml',
                example_config_file=config_dir / 'config.example.toml',
                log_file=local_data_dir / 'polyfi.log',
                speed_test_history_file=local_data_dir / 'speedtest_history.jsonl',
                config_dir=config_dir,
                local_data_dir=local_data_dir,
                legacy_config_dir=legacy_config_dir,
                legacy_local_dir=legacy_local_dir,
            )

            mock_config_loader_type.return_value.load.return_value = SimpleNamespace(
                log_file=str(custom_log),
                speed_test_history_file=str(custom_history),
            )

            app.purge_application_data(str(custom_config))

            self.assertFalse(config_dir.exists())
            self.assertFalse(local_data_dir.exists())
            self.assertFalse(legacy_config_dir.exists())
            self.assertFalse(legacy_local_dir.exists())
            self.assertFalse(custom_config.exists())
            self.assertFalse(custom_log.exists())
            self.assertFalse(custom_history.exists())

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
