"""
Author:
    Inspyre Softworks

Project:
    PolyFi: Ranked

File:
    app.py

Description:
    Main entry point for running PolyFi: Ranked either in console mode or as a
    system tray application.

Functions:
    main:
        CLI entry point.

Constants:
    None.

Dependencies:
    argparse
    sys
    wifi_pref_manager.config
    wifi_pref_manager.logging_utils
    wifi_pref_manager.netsh_wifi
    wifi_pref_manager.paths
    wifi_pref_manager.service
    wifi_pref_manager.ui.tray

Example Usage:
    poetry run polyfi-ranked
    poetry run polyfi-ranked --tray
"""

from __future__ import annotations

import argparse
import ctypes
from datetime import datetime
import logging
import os
from pathlib import Path
import subprocess
import sys

from wifi_pref_manager.console_output import ConsoleOutputManager
from wifi_pref_manager.config import ConfigError, ConfigLoader
from wifi_pref_manager.logging_utils import configure_logging
from wifi_pref_manager.models import ETHERNET_WIFI_MODE_DISABLE_ADAPTER, ETHERNET_WIFI_MODE_DISCONNECT
from wifi_pref_manager.netsh_wifi import NetshWiFiApi
from wifi_pref_manager.paths import APP_NAME, APP_USER_MODEL_ID, AppPaths
from wifi_pref_manager.service import WiFiPreferenceService
from wifi_pref_manager.single_instance import SingleInstanceGuard
from wifi_pref_manager.ui.dialogs import show_dialog, show_native_message_box
from wifi_pref_manager.ui.splash import resolve_splash_image_path, show_startup_splash
from wifi_pref_manager.ui.tray import TrayApplication
from wifi_pref_manager.wifi_adapter_tasks import WifiAdapterTaskManager
from wifi_pref_manager.windows_shell import StartMenuShortcutManager, resolve_runtime_launch_target


BACKGROUND_TRAY_ENV_VAR = 'POLYFI_BACKGROUND_TRAY'
SPLASH_SHOWN_ENV_VAR = 'POLYFI_SPLASH_ALREADY_SHOWN'


class Application:
    """
    Application bootstrapper.

    Methods:
        run:
            Start the application in console or tray mode.
    """

    def __init__(self) -> None:
        self.paths = AppPaths()
        self.argument_parser = self.build_argument_parser()
        self.log_level_override: str | None = None
        self.save_speed_test_history_override: bool | None = None
        self.speed_test_history_file_override: str | None = None
        self.show_startup_splash_override: bool | None = None
        self.original_argv: list[str] = list(sys.argv)
        self.single_instance_guard = SingleInstanceGuard(f'Local\\{APP_USER_MODEL_ID}')
        self.console_output_manager: ConsoleOutputManager | None = None
        self._run_in_tray_context = False
        self._startup_splash_shown = False
        self.startup_trace_file = self.paths.local_data_dir / 'startup_trace.log'

    def append_startup_trace(self, message: str) -> None:
        """
        Append an early-startup trace line that survives windowless launches.

        Parameters:
            message:
                Trace message to append.
        """
        try:
            self.paths.local_data_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().isoformat(timespec='seconds')
            with self.startup_trace_file.open('a', encoding='utf-8') as handle:
                handle.write(f'[{timestamp}] pid={Path(sys.executable).name}:{message}\n')
        except OSError:
            return

    def add_runtime_arguments(self, parser: argparse.ArgumentParser, *, include_tray: bool = True) -> None:
        """
        Add arguments used when launching the runtime service.

        Parameters:
            parser:
                Parser to extend.
            include_tray:
                Whether to expose the tray-mode switch on this parser.
        """
        parser.add_argument(
            '--config',
            default=argparse.SUPPRESS,
            help='Optional path to the TOML configuration file. Defaults to the platform app-data config path.',
        )
        if include_tray:
            parser.add_argument(
                '--tray',
                action='store_true',
                default=argparse.SUPPRESS,
                help='Run as a system tray application.',
            )
        parser.add_argument(
            '-l',
            '--log-level',
            default=argparse.SUPPRESS,
            help='Override the configured log level for this run, for example DEBUG or INFO.',
        )
        parser.add_argument(
            '--save-speed-test-history',
            action='store_true',
            default=argparse.SUPPRESS,
            help='Enable saving completed speed-test results for this run.',
        )
        parser.add_argument(
            '--no-save-speed-test-history',
            action='store_true',
            default=argparse.SUPPRESS,
            help='Disable saving completed speed-test results for this run.',
        )
        parser.add_argument(
            '--speed-test-history-file',
            default=argparse.SUPPRESS,
            help='Override the speed-test history file path for this run.',
        )
        parser.add_argument(
            '--show-splash',
            action='store_true',
            default=argparse.SUPPRESS,
            help='Force-enable the startup splash for this run.',
        )
        parser.add_argument(
            '--no-splash',
            action='store_true',
            default=argparse.SUPPRESS,
            help='Disable the startup splash for this run.',
        )

    def build_argument_parser(self) -> argparse.ArgumentParser:
        """
        Build the application CLI parser.

        Returns:
            Configured ArgumentParser.
        """
        parser = argparse.ArgumentParser(description='PolyFi: Ranked for Windows.')
        self.add_runtime_arguments(parser)
        parser.add_argument(
            '--print-paths',
            action='store_true',
            help='Print the default config and data paths, then exit.',
        )
        parser.set_defaults(handler=self.handle_run_command)

        subparsers = parser.add_subparsers(dest='command')

        run_parser = subparsers.add_parser('run', help='Run the PolyFi service.')
        self.add_runtime_arguments(run_parser)
        run_parser.set_defaults(handler=self.handle_run_command)

        paths_parser = subparsers.add_parser('paths', help='Print the default config and data paths.')
        paths_parser.set_defaults(handler=self.handle_paths_command)

        windows_parser = subparsers.add_parser('windows', help='Windows shell integration commands.')
        windows_subparsers = windows_parser.add_subparsers(dest='windows_command')
        windows_subparsers.required = True

        start_menu_parser = windows_subparsers.add_parser('start-menu', help='Manage the Start Menu shortcut.')
        start_menu_subparsers = start_menu_parser.add_subparsers(dest='start_menu_command')
        start_menu_subparsers.required = True

        start_menu_install_parser = start_menu_subparsers.add_parser(
            'install',
            help='Install a Start Menu shortcut that launches PolyFi in tray mode.',
        )
        self.add_runtime_arguments(start_menu_install_parser, include_tray=False)
        start_menu_install_parser.add_argument(
            '--force',
            action='store_true',
            help='Overwrite the existing Start Menu shortcut if present.',
        )
        start_menu_install_parser.set_defaults(handler=self.handle_start_menu_install_command)

        start_menu_remove_parser = start_menu_subparsers.add_parser(
            'remove',
            help='Remove the PolyFi Start Menu shortcut.',
        )
        start_menu_remove_parser.set_defaults(handler=self.handle_start_menu_remove_command)

        start_menu_path_parser = start_menu_subparsers.add_parser(
            'path',
            help='Print the Start Menu shortcut path.',
        )
        start_menu_path_parser.set_defaults(handler=self.handle_start_menu_path_command)

        wifi_tasks_parser = windows_subparsers.add_parser(
            'wifi-tasks',
            help='Manage scheduled tasks for Wi-Fi adapter control.',
        )
        wifi_tasks_subparsers = wifi_tasks_parser.add_subparsers(dest='wifi_tasks_command')
        wifi_tasks_subparsers.required = True

        wifi_tasks_install_parser = wifi_tasks_subparsers.add_parser(
            'install',
            help=(
                'Create SYSTEM scheduled tasks that let PolyFi disable/enable the '
                'Wi-Fi adapter without requiring the Python interpreter to run elevated.'
            ),
        )
        wifi_tasks_install_parser.add_argument(
            '--interface',
            default=None,
            metavar='NAME',
            help='Wi-Fi interface name to embed in the tasks.  Auto-detected if omitted.',
        )
        wifi_tasks_install_parser.set_defaults(handler=self.handle_wifi_tasks_install_command)

        wifi_tasks_uninstall_parser = wifi_tasks_subparsers.add_parser(
            'uninstall',
            help='Remove the PolyFi Wi-Fi adapter control scheduled tasks.',
        )
        wifi_tasks_uninstall_parser.set_defaults(handler=self.handle_wifi_tasks_uninstall_command)

        config_parser = subparsers.add_parser('config', help='Work with configuration files.')
        config_subparsers = config_parser.add_subparsers(dest='config_command')
        config_subparsers.required = True
        config_init_parser = config_subparsers.add_parser(
            'init',
            help='Write a full default configuration file and exit.',
        )
        config_init_parser.add_argument(
            '--config',
            default=None,
            help='Optional destination path for the generated TOML config file.',
        )
        config_init_parser.add_argument(
            '--force',
            action='store_true',
            help='Overwrite an existing config file.',
        )
        config_init_parser.set_defaults(handler=self.handle_config_init_command)
        return parser

    def apply_cli_overrides_from_args(self, args: argparse.Namespace) -> int:
        """
        Capture one-run CLI overrides from parsed arguments.

        Parameters:
            args:
                Parsed argument namespace.

        Returns:
            Process exit code when validation fails, otherwise 0.
        """
        self.log_level_override = getattr(args, 'log_level', None)
        save_speed_test_history = bool(getattr(args, 'save_speed_test_history', False))
        disable_speed_test_history = bool(getattr(args, 'no_save_speed_test_history', False))
        if save_speed_test_history and disable_speed_test_history:
            print('Cannot use --save-speed-test-history and --no-save-speed-test-history together.', file=sys.stderr)
            return 1
        if save_speed_test_history:
            self.save_speed_test_history_override = True
        elif disable_speed_test_history:
            self.save_speed_test_history_override = False
        else:
            self.save_speed_test_history_override = None
        self.speed_test_history_file_override = getattr(args, 'speed_test_history_file', None)
        show_splash = bool(getattr(args, 'show_splash', False))
        no_splash = bool(getattr(args, 'no_splash', False))
        if show_splash and no_splash:
            print('Cannot use --show-splash and --no-splash together.', file=sys.stderr)
            return 1
        if show_splash:
            self.show_startup_splash_override = True
        elif no_splash:
            self.show_startup_splash_override = False
        else:
            self.show_startup_splash_override = None
        return 0

    def resolve_log_level(self, configured_log_level: str) -> str:
        """
        Resolve the effective log level, honoring any CLI override.

        Parameters:
            configured_log_level:
                Log level loaded from configuration.

        Returns:
            Effective log level for this process.
        """
        return (self.log_level_override or configured_log_level).upper()

    def on_config_reloaded(self, config) -> object:
        """
        Reconfigure logging when the config changes.

        Parameters:
            config:
                Newly loaded application config.

        Returns:
            Refreshed logger instance.
        """
        self.apply_runtime_overrides(config)
        logger = configure_logging(self.resolve_log_level(config.log_level), config.log_file)
        if self.console_output_manager is not None:
            self.console_output_manager.attach_logger(logger)
        return logger

    def apply_runtime_overrides(self, config) -> None:
        """
        Apply CLI overrides to a loaded config object.

        Parameters:
            config:
                Mutable runtime config.
        """
        config.log_level = self.resolve_log_level(config.log_level)
        if self.save_speed_test_history_override is not None:
            config.save_speed_test_history = self.save_speed_test_history_override
        if self.speed_test_history_file_override:
            config.speed_test_history_file = self.speed_test_history_file_override
        if self.show_startup_splash_override is not None:
            config.show_startup_splash = self.show_startup_splash_override

    def print_paths(self) -> int:
        """
        Print the default config and data paths, then exit.

        Returns:
            Process exit code.
        """
        print(f'Config file: {self.paths.config_file}')
        print(f'Example config: {self.paths.example_config_file}')
        print(f'Log file: {self.paths.log_file}')
        print(f'Managed interface file: {self.paths.managed_interface_file}')
        print(f'Speed test history file: {self.paths.speed_test_history_file}')
        print(f'Start Menu shortcut: {self.paths.start_menu_shortcut_file}')
        print(f'Start Menu icon: {self.paths.start_menu_icon_file}')
        return 0

    def build_runtime_argument_list(
        self,
        args: argparse.Namespace,
        *,
        force_tray: bool = False,
        force_show_splash: bool = False,
    ) -> list[str]:
        """
        Build runtime CLI arguments from parsed values.

        Parameters:
            args:
                Parsed argument namespace.
            force_tray:
                Whether to force tray mode on.
            force_show_splash:
                Whether to force the startup splash on unless explicitly disabled.

        Returns:
            Runtime argument list.
        """
        runtime_args: list[str] = []
        config_path = getattr(args, 'config', None)
        if config_path:
            runtime_args.extend(['--config', config_path])
        if force_tray or getattr(args, 'tray', False):
            runtime_args.append('--tray')
        log_level = getattr(args, 'log_level', None)
        if log_level:
            runtime_args.extend(['--log-level', log_level])
        if bool(getattr(args, 'save_speed_test_history', False)):
            runtime_args.append('--save-speed-test-history')
        if bool(getattr(args, 'no_save_speed_test_history', False)):
            runtime_args.append('--no-save-speed-test-history')
        speed_test_history_file = getattr(args, 'speed_test_history_file', None)
        if speed_test_history_file:
            runtime_args.extend(['--speed-test-history-file', speed_test_history_file])
        show_splash = bool(getattr(args, 'show_splash', False))
        no_splash = bool(getattr(args, 'no_splash', False))
        if force_show_splash and not no_splash:
            runtime_args.append('--show-splash')
        elif show_splash:
            runtime_args.append('--show-splash')
        if no_splash:
            runtime_args.append('--no-splash')
        return runtime_args

    def maybe_show_startup_splash(self, config, logger) -> bool:
        """
        Show the configured startup splash if enabled and available.

        Parameters:
            config:
                Runtime configuration object.
            logger:
                Application logger.

        Returns:
            True when the splash was shown, otherwise False.
        """
        if os.environ.get(SPLASH_SHOWN_ENV_VAR) == '1' or self._startup_splash_shown:
            return False

        if not getattr(config, 'show_startup_splash', True):
            return False

        splash_path = resolve_splash_image_path(
            getattr(config, 'splash_image_path', ''),
            self.paths,
        )
        if splash_path is None:
            logger.debug(
                'Startup splash is enabled, but no splash image was found. '
                'Looked for config path, app-data splash, and Pictures defaults.'
            )
            return False

        try:
            logger.info('Showing startup splash from: %s', splash_path)
            show_startup_splash(
                splash_path,
                fade_in_ms=max(0, int(getattr(config, 'splash_fade_in_ms', 280))),
                hold_ms=max(0, int(getattr(config, 'splash_hold_ms', 1100))),
                fade_out_ms=max(0, int(getattr(config, 'splash_fade_out_ms', 280))),
            )
            self._startup_splash_shown = True
            logger.debug('Startup splash completed.')
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning('Startup splash failed and will be skipped for this launch: %s', exc)
            return False

    def write_default_config_file(self, config_path: str | None, overwrite: bool) -> int:
        """
        Write the default configuration template and exit.

        Parameters:
            config_path:
                Optional destination path.
            overwrite:
                Whether an existing file may be replaced.

        Returns:
            Process exit code.
        """
        loader = ConfigLoader(config_path=config_path)
        try:
            written_path = loader.write_default_config(overwrite=overwrite)
        except ConfigError as exc:
            print(f'Configuration error: {exc}', file=sys.stderr)
            return 1

        print(f'Wrote default config file: {written_path}')
        return 0

    def launch_detached_tray_process(self, args: argparse.Namespace, *, suppress_splash: bool = False) -> int:
        """
        Launch the tray runtime in a detached background process.

        Parameters:
            args:
                Parsed runtime arguments to preserve.

        Returns:
            Background child process identifier.

        Raises:
            OSError:
                If the tray process could not be started.
        """
        # Use the standard runtime here instead of ``pythonw.exe`` because the
        # background child still detaches its own console once tray startup
        # begins, and the regular interpreter is more reliable for inheriting
        # the active Poetry environment than a direct ``pythonw.exe`` launch.
        executable, base_args, _working_directory = resolve_runtime_launch_target(prefer_windowless=False)
        command = [
            str(executable),
            *base_args,
            *self.build_runtime_argument_list(args, force_tray=True),
        ]
        environment = os.environ.copy()
        environment[BACKGROUND_TRAY_ENV_VAR] = '1'
        if suppress_splash:
            environment[SPLASH_SHOWN_ENV_VAR] = '1'
        process = subprocess.Popen(  # noqa: S603
            command,
            close_fds=True,
            env=environment,
        )
        return process.pid

    def set_windows_app_user_model_id(self) -> None:
        """
        Set the Windows AppUserModelID so tray notifications identify as PolyFi.
        """
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                APP_USER_MODEL_ID
            )
        except (AttributeError, OSError):
            return

    def is_running_as_administrator(self) -> bool:
        """
        Determine whether the current process is elevated on Windows.

        Returns:
            True when the process has administrator privileges.
        """
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except (AttributeError, OSError):
            return False

    @staticmethod
    def _ethernet_action_requires_admin(config) -> bool:
        """
        Return whether the selected Ethernet Wi-Fi mode needs adapter control.
        """
        if not getattr(config, 'auto_disable_wifi_on_ethernet', False):
            return False
        mode = getattr(config, 'ethernet_wifi_mode', ETHERNET_WIFI_MODE_DISCONNECT)
        return mode == ETHERNET_WIFI_MODE_DISABLE_ADAPTER

    def handle_startup_admin_requirements(self, config, logger) -> int | None:
        """
        Warn when the Ethernet auto-disable feature needs administrator rights.

        When the process is not elevated and ``auto_disable_wifi_on_ethernet`` is
        enabled with ``ethernet_wifi_mode = "disable_adapter"``, the feature is
        disabled for the session and a warning is logged telling the user to
        restart as administrator if they want it.

        Parameters:
            config:
                Loaded runtime configuration.
            logger:
                Application logger.

        Returns:
            Always ``None``; startup continues after showing the warning.
        """
        if not self._ethernet_action_requires_admin(config) or self.is_running_as_administrator():
            return None

        self.append_startup_trace('admin-requirements: not admin, disabling ethernet feature for session')
        logger.warning(
            'Ethernet mode "disable_adapter" is enabled but this process is not running as administrator. '
            'The feature will be disabled for this session. Restart PolyFi as administrator to use it.'
        )
        config.auto_disable_wifi_on_ethernet = False
        return None

    def handle_paths_command(self, args: argparse.Namespace) -> int:
        """
        Handle path-printing CLI requests.

        Parameters:
            args:
                Parsed argument namespace.

        Returns:
            Process exit code.
        """
        del args
        return self.print_paths()

    def acquire_single_instance_guard(self, *, show_dialog_on_duplicate: bool) -> bool:
        """
        Acquire the runtime single-instance guard.

        Parameters:
            show_dialog_on_duplicate:
                Whether to show a user-facing dialog when another instance is already running.

        Returns:
            True when startup may continue.
        """
        try:
            acquired = self.single_instance_guard.acquire()
        except OSError as exc:
            raise OSError(f'Could not acquire the PolyFi single-instance guard: {exc}') from exc

        if acquired:
            return True

        if show_dialog_on_duplicate:
            show_native_message_box(
                'info',
                'PolyFi Already Running',
                'PolyFi is already running in the background.\n\n'
                'Look for the PolyFi icon in the notification area near the clock on your '
                'taskbar. You may need to click the \u25b2 (chevron) arrow to expand '
                'hidden system tray icons.',
            )
        return False

    def release_single_instance_guard(self) -> bool:
        """
        Release the runtime single-instance guard if held.

        Returns:
            True when a held guard was released.
        """
        was_held = self.single_instance_guard._handle is not None
        self.single_instance_guard.release()
        return was_held

    def handle_config_init_command(self, args: argparse.Namespace) -> int:
        """
        Handle config generation CLI requests.

        Parameters:
            args:
                Parsed argument namespace.

        Returns:
            Process exit code.
        """
        return self.write_default_config_file(args.config, overwrite=args.force)

    def handle_start_menu_install_command(self, args: argparse.Namespace) -> int:
        """
        Install the user's PolyFi Start Menu shortcut.

        Parameters:
            args:
                Parsed argument namespace.

        Returns:
            Process exit code.
        """
        validation_result = self.apply_cli_overrides_from_args(args)
        if validation_result != 0:
            return validation_result

        manager = StartMenuShortcutManager(paths=self.paths)
        try:
            shortcut_path = manager.install(
                self.build_runtime_argument_list(args, force_tray=True, force_show_splash=True),
                overwrite=args.force,
            )
        except (FileExistsError, OSError) as exc:
            print(f'Start Menu shortcut error: {exc}', file=sys.stderr)
            return 1

        print(f'Installed Start Menu shortcut: {shortcut_path}')
        return 0

    def handle_start_menu_remove_command(self, args: argparse.Namespace) -> int:
        """
        Remove the user's PolyFi Start Menu shortcut.

        Parameters:
            args:
                Parsed argument namespace.

        Returns:
            Process exit code.
        """
        del args
        manager = StartMenuShortcutManager(paths=self.paths)
        if manager.remove():
            print(f'Removed Start Menu shortcut: {manager.get_shortcut_path()}')
        else:
            print(f'No Start Menu shortcut found at: {manager.get_shortcut_path()}')
        return 0

    def handle_start_menu_path_command(self, args: argparse.Namespace) -> int:
        """
        Print the Start Menu shortcut path.

        Parameters:
            args:
                Parsed argument namespace.

        Returns:
            Process exit code.
        """
        del args
        print(self.paths.start_menu_shortcut_file)
        return 0

    def handle_wifi_tasks_install_command(self, args: argparse.Namespace) -> int:
        """
        Install the SYSTEM scheduled tasks for Wi-Fi adapter control.

        Parameters:
            args:
                Parsed argument namespace.

        Returns:
            Process exit code.
        """
        interface_name: str | None = getattr(args, 'interface', None)
        if not interface_name:
            try:
                interface_name = NetshWiFiApi().detect_wifi_interface()
            except Exception as exc:
                print(f'Could not auto-detect Wi-Fi interface: {exc}', file=sys.stderr)
                print('Use --interface NAME to specify the interface manually.', file=sys.stderr)
                return 1

        task_manager = WifiAdapterTaskManager()
        print(f'Installing Wi-Fi adapter control tasks for interface {interface_name!r}...')
        print('A UAC prompt for Windows PowerShell will appear. Accept it to continue.')
        try:
            installed = task_manager.install_and_wait(interface_name)
        except OSError as exc:
            print(f'Task installation failed: {exc}', file=sys.stderr)
            return 1

        if installed:
            print(
                f'Successfully installed tasks:\n'
                f'  PolyFi-DisableWiFi\n'
                f'  PolyFi-EnableWiFi\n'
                f'PolyFi can now control {interface_name!r} without running as administrator.'
            )
            return 0
        print(
            'Task installation could not be confirmed within the timeout.\n'
            'The UAC prompt may have been cancelled, or PowerShell is also blocked on this machine.',
            file=sys.stderr,
        )
        return 1

    def handle_wifi_tasks_uninstall_command(self, args: argparse.Namespace) -> int:
        """
        Remove the SYSTEM scheduled tasks for Wi-Fi adapter control.

        Parameters:
            args:
                Parsed argument namespace.

        Returns:
            Process exit code.
        """
        del args
        task_manager = WifiAdapterTaskManager()
        task_manager.uninstall()
        print('Removed PolyFi Wi-Fi adapter control tasks (if they existed).')
        return 0

    def handle_run_command(self, args: argparse.Namespace) -> int:
        """
        Handle normal application execution.

        Parameters:
            args:
                Parsed argument namespace.

        Returns:
            Process exit code.
        """
        if getattr(args, 'print_paths', False):
            return self.print_paths()

        self.append_startup_trace(f'handle_run_command argv={argv if (argv := list(sys.argv[1:])) else []}')
        override_result = self.apply_cli_overrides_from_args(args)
        if override_result != 0:
            self.append_startup_trace(f'cli override validation failed code={override_result}')
            return override_result

        loader = ConfigLoader(config_path=getattr(args, 'config', None))
        config_path = loader.ensure_default_config()

        try:
            config = loader.load()
        except ConfigError as exc:
            self.append_startup_trace(f'config load failed: {exc}')
            print(f'Configuration error: {exc}', file=sys.stderr)
            print(f'Config path: {config_path}', file=sys.stderr)
            return 1

        self.apply_runtime_overrides(config)
        # pythonw.exe (and other consoleless launchers) redirect stdout to None
        # because there is no console window attached.  Use this as the canonical
        # indicator rather than inspecting the executable name, which may not always
        # end in 'pythonw.exe' (e.g. packaged launchers, pyenv shims).
        # Named `running_consoleless` to reflect that stdout=None is the specific
        # condition we care about (tray mode needs to hide console / redirect I/O).
        running_consoleless = sys.stdout is None
        run_in_tray = getattr(args, 'tray', False) or config.start_minimized_to_tray or running_consoleless
        should_background_tray = (
            run_in_tray
            and not running_consoleless
            and os.environ.get(BACKGROUND_TRAY_ENV_VAR) != '1'
        )
        if should_background_tray:
            try:
                can_launch = self.acquire_single_instance_guard(show_dialog_on_duplicate=True)
            except OSError as exc:
                self.append_startup_trace(f'single instance preflight failure: {exc}')
                print(str(exc), file=sys.stderr)
                return 1
            if not can_launch:
                self.append_startup_trace('duplicate instance detected before detached tray launch')
                return 0
            self.release_single_instance_guard()
            self.append_startup_trace('launching detached tray background process')
            bootstrap_logger = logging.getLogger('polyfi_ranked.bootstrap')
            showed_splash = self.maybe_show_startup_splash(config, bootstrap_logger)
            try:
                child_pid = self.launch_detached_tray_process(args, suppress_splash=showed_splash)
            except OSError as exc:
                self.append_startup_trace(f'detached tray launch failed: {exc}')
                print(
                    f'Could not launch PolyFi in background tray mode automatically: {exc}',
                    file=sys.stderr,
                )
                print('Continuing in attached tray mode instead.', file=sys.stderr)
            else:
                self.append_startup_trace(f'detached tray background process started pid={child_pid}')
                print(
                    'PolyFi is starting in tray mode. Look for the icon in the notification area near the clock.',
                )
                return 0
        self._run_in_tray_context = run_in_tray
        self.append_startup_trace(
            f'config loaded run_in_tray={run_in_tray} admin={self.is_running_as_administrator()} '
            f'auto_disable_wifi_on_ethernet={config.auto_disable_wifi_on_ethernet} '
            f'ethernet_wifi_mode={getattr(config, "ethernet_wifi_mode", ETHERNET_WIFI_MODE_DISCONNECT)}'
        )
        if run_in_tray:
            self.console_output_manager = ConsoleOutputManager(
                self.paths.local_data_dir / 'polyfi_ranked_output_console.log'
            )
            self.console_output_manager.install_stream_proxies()
            self.console_output_manager.hide_console()
        else:
            self.console_output_manager = None
        effective_log_level = self.resolve_log_level(config.log_level)
        logger = configure_logging(effective_log_level, config.log_file)
        if self.console_output_manager is not None:
            self.console_output_manager.attach_logger(logger)
        self.set_windows_app_user_model_id()
        logger.info('Using config file: %s', config_path)
        logger.info('Effective log level: %s', effective_log_level)

        # Check whether admin is needed before handle_startup_admin_requirements
        # modifies the config, so we can show a persistent warning afterwards.
        needs_admin_notification = (
            self._ethernet_action_requires_admin(config) and not self.is_running_as_administrator()
        )

        self.handle_startup_admin_requirements(config, logger)

        if needs_admin_notification and not run_in_tray:
            print(
                'Warning: The "disable Wi-Fi when Ethernet is connected" feature requires '
                'administrator privileges. Restart PolyFi as administrator to use this feature. '
                'The feature is disabled for this session.',
                file=sys.stderr,
            )

        try:
            acquired = self.acquire_single_instance_guard(show_dialog_on_duplicate=True)
        except OSError as exc:
            self.append_startup_trace(f'single instance guard failure: {exc}')
            logger.error('%s', exc)
            show_dialog('error', 'Startup Failed', str(exc))
            return 1
        if not acquired:
            self.append_startup_trace('duplicate instance detected')
            logger.info('Another PolyFi instance is already running. Exiting duplicate launch.')
            return 0

        self.maybe_show_startup_splash(config, logger)

        wifi_api = NetshWiFiApi(logger=logger)
        service = WiFiPreferenceService(
            config=config,
            wifi_api=wifi_api,
            logger=logger,
            config_loader=loader,
            on_config_reloaded=self.on_config_reloaded,
        )

        try:
            if run_in_tray:
                self.append_startup_trace('starting tray application')
                tray_app = TrayApplication(
                    service=service,
                    logger=logger,
                    config_loader=loader,
                    needs_admin_notification=needs_admin_notification,
                    show_output_console_callback=(
                        self.console_output_manager.show_console_with_history
                        if self.console_output_manager is not None
                        else None
                    ),
                    startup_marker_path=self.paths.first_tray_start_marker_file,
                    startup_trace_path=self.startup_trace_file,
                )
                try:
                    tray_app.run()
                except Exception as exc:  # noqa: BLE001
                    self.append_startup_trace(f'tray application crashed: {exc!r}')
                    logger.exception('Tray application crashed: %s', exc)
                    show_native_message_box(
                        'error',
                        'PolyFi Startup Failed',
                        f'PolyFi encountered an unexpected error while starting '
                        f'the system tray icon:\n\n{exc}\n\n'
                        f'Diagnostic log:\n{self.startup_trace_file}',
                    )
                    return 1
                self.append_startup_trace('tray application exited normally')
                return 0

            try:
                self.append_startup_trace('starting foreground service loop')
                service.run_forever()
            except KeyboardInterrupt:
                self.append_startup_trace('foreground service loop interrupted')
                logger.info('Keyboard interrupt received. Stopping service.')
                service.stop()

            return 0
        finally:
            self.append_startup_trace('releasing single instance guard')
            self.release_single_instance_guard()

    def run(self, argv: list[str] | None = None) -> int:
        """
        Run the application.

        Parameters:
            argv:
                Optional CLI argument list.

        Returns:
            Process exit code.
        """
        self.original_argv = list(sys.argv if argv is None else [self.original_argv[0], *argv])
        args = self.argument_parser.parse_args(argv)
        handler = getattr(args, 'handler', self.handle_run_command)
        return handler(args)


def main() -> int:
    """
    CLI entry point.

    Returns:
        Process exit code.
    """
    app = Application()
    try:
        return app.run()
    except Exception as exc:  # noqa: BLE001
        app.append_startup_trace(f'unhandled exception: {exc!r}')
        raise


if __name__ == '__main__':
    raise SystemExit(main())
