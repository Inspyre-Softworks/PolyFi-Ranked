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
from pathlib import Path
import subprocess
import sys
import time

from wifi_pref_manager.console_output import ConsoleOutputManager
from wifi_pref_manager.config import ConfigError, ConfigLoader, save_config
from wifi_pref_manager.logging_utils import configure_logging
from wifi_pref_manager.managed_interface_state import ManagedInterfaceStateStore
from wifi_pref_manager.netsh_wifi import NetshWiFiApi
from wifi_pref_manager.paths import APP_USER_MODEL_ID, AppPaths
from wifi_pref_manager.service import WiFiPreferenceService
from wifi_pref_manager.single_instance import SingleInstanceGuard
from wifi_pref_manager.ui.dialogs import show_custom_dialog, show_dialog, show_native_message_box
from wifi_pref_manager.ui.tray import TrayApplication
from wifi_pref_manager.wifi_adapter_tasks import WifiAdapterTaskManager
from wifi_pref_manager.windows_shell import StartMenuShortcutManager


class Application:
    """
    Application bootstrapper.

    Methods:
        run:
            Start the application in console or tray mode.
    """

    _ELEVATED_INSTANCE_TIMEOUT: float = 2.0
    _ELEVATED_INSTANCE_POLL_INITIAL: float = 0.05
    _ELEVATED_INSTANCE_POLL_MAX: float = 0.4

    def __init__(self) -> None:
        self.paths = AppPaths()
        self.argument_parser = self.build_argument_parser()
        self.log_level_override: str | None = None
        self.save_speed_test_history_override: bool | None = None
        self.speed_test_history_file_override: str | None = None
        self.original_argv: list[str] = list(sys.argv)
        self.single_instance_guard = SingleInstanceGuard(f'Local\\{APP_USER_MODEL_ID}')
        self.console_output_manager: ConsoleOutputManager | None = None
        self._run_in_tray_context = False
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
            self.startup_trace_file.open('a', encoding='utf-8').write(
                f'[{timestamp}] pid={Path(sys.executable).name}:{message}\n'
            )
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
            default=None,
            help='Optional path to the TOML configuration file. Defaults to the platform app-data config path.',
        )
        if include_tray:
            parser.add_argument(
                '--tray',
                action='store_true',
                help='Run as a system tray application.',
            )
        parser.add_argument(
            '-l',
            '--log-level',
            default=None,
            help='Override the configured log level for this run, for example DEBUG or INFO.',
        )
        parser.add_argument(
            '--save-speed-test-history',
            action='store_true',
            help='Enable saving completed speed-test results for this run.',
        )
        parser.add_argument(
            '--no-save-speed-test-history',
            action='store_true',
            help='Disable saving completed speed-test results for this run.',
        )
        parser.add_argument(
            '--speed-test-history-file',
            default=None,
            help='Override the speed-test history file path for this run.',
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

    def build_runtime_argument_list(self, args: argparse.Namespace, *, force_tray: bool = False) -> list[str]:
        """
        Build runtime CLI arguments from parsed values.

        Parameters:
            args:
                Parsed argument namespace.
            force_tray:
                Whether to force tray mode on.

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
        return runtime_args

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

    def restart_as_administrator(self) -> bool:
        """
        Relaunch the current process with Windows administrator privileges.

        Returns:
            True when the elevation request was launched successfully.

        Raises:
            OSError:
                If Windows could not start the elevated process.
        """
        executable = self._resolve_relaunch_executable(windowed=self._run_in_tray_context)
        parameters = subprocess.list2cmdline(self._build_relaunch_arguments())
        released_guard = self.release_single_instance_guard()
        try:
            result = ctypes.windll.shell32.ShellExecuteW(
                None,
                'runas',
                str(executable),
                parameters,
                None,
                1,
            )
        except Exception:
            if released_guard:
                self.acquire_single_instance_guard(show_dialog_on_duplicate=False)
            raise
        if result <= 32:
            if released_guard:
                self.acquire_single_instance_guard(show_dialog_on_duplicate=False)
            if result == 1223:
                return False
            raise OSError(f'Windows elevation request failed with ShellExecuteW code {result}.')
        return True

    def _resolve_relaunch_executable(self, *, windowed: bool) -> Path:
        """
        Resolve the Python executable used to relaunch the current app.

        Parameters:
            windowed:
                Whether to prefer ``pythonw.exe`` over ``python.exe``.

        Returns:
            Executable path.
        """
        executable = Path(sys.executable).resolve()
        if not windowed:
            return executable
        pythonw = executable.with_name('pythonw.exe')
        return pythonw if pythonw.exists() else executable

    def _build_relaunch_arguments(self) -> list[str]:
        """
        Build arguments that relaunch this application with the current runtime parameters.

        Returns:
            Relaunch argument list.
        """
        return ['-m', 'wifi_pref_manager.app', *self.original_argv[1:]]

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

    def _permanently_disable_ethernet_feature(self, config, loader, logger) -> None:
        """
        Permanently disable auto_disable_wifi_on_ethernet in config and save to disk.

        Parameters:
            config:
                Runtime configuration object to mutate.
            loader:
                ConfigLoader used to resolve the config file path.
            logger:
                Application logger.
        """
        config.auto_disable_wifi_on_ethernet = False
        if loader is None:
            self.append_startup_trace('auto_disable_wifi_on_ethernet disabled for session (no loader to save)')
            logger.warning(
                'Disabling automatic Wi-Fi disable on Ethernet for this running instance '
                '(no config loader available to persist the change).'
            )
            return
        try:
            save_config(config, loader.config_path)
            self.append_startup_trace('auto_disable_wifi_on_ethernet permanently disabled in config')
            logger.info(
                'Permanently disabled auto_disable_wifi_on_ethernet in config: %s',
                loader.config_path,
            )
        except OSError as exc:
            self.append_startup_trace(f'failed to save config after disabling ethernet feature: {exc}')
            logger.warning('Could not save config after disabling ethernet feature: %s', exc)

    def handle_startup_admin_requirements(
        self,
        config,
        logger,
        *,
        config_loader=None,
        interface_name: str | None = None,
    ) -> int | None:
        """
        Proactively resolve admin-only startup requirements before the service begins.

        When the process is not elevated and ``auto_disable_wifi_on_ethernet`` is
        enabled, the method attempts to satisfy the privilege requirement without
        requiring the Python interpreter to restart elevated:

        1. If scheduled tasks are already installed for ``interface_name``, no
           elevation is needed — the tasks run ``netsh`` as SYSTEM.
        2. Otherwise, attempt one-time task installation by elevating
           ``powershell.exe`` (a signed system binary unlikely to be covered by
           an AppLocker rule targeting ``python.exe``).
        3. If task installation is unavailable (no interface name, elevation
           blocked for PowerShell too, or user cancelled), fall back to the
           traditional ``restart_as_administrator`` approach.

        Parameters:
            config:
                Loaded runtime configuration.
            logger:
                Application logger.
            config_loader:
                Optional ConfigLoader used to permanently persist config changes.
            interface_name:
                Detected Wi-Fi interface name for task validation and setup.
                When ``None``, the task-based path is skipped entirely.

        Returns:
            ``None`` when startup should continue, or a process exit code when the
            current instance should stop after launching a replacement.
        """
        if not config.auto_disable_wifi_on_ethernet or self.is_running_as_administrator():
            return None

        self.append_startup_trace(
            f'admin-requirements run_in_tray={self._run_in_tray_context} admin={self.is_running_as_administrator()}'
        )
        logger.warning(
            'auto_disable_wifi_on_ethernet is enabled, but this process is not running as administrator. '
            'Checking whether scheduled tasks can satisfy the requirement.'
        )

        # ── Task-based path ─────────────────────────────────────────────────────
        # When the interface is known, check if scheduled tasks are already
        # configured.  If they are, no elevation is needed at all — the
        # NetshWiFiApi will trigger them at runtime via schtasks /run.
        if interface_name is not None:
            task_manager = WifiAdapterTaskManager()

            if task_manager.are_installed(interface_name):
                self.append_startup_trace(
                    f'wifi-tasks already installed for {interface_name!r}; no elevation needed'
                )
                logger.info(
                    'Scheduled tasks are installed for Wi-Fi interface %r. '
                    'No elevation needed for auto Ethernet feature.',
                    interface_name,
                )
                return None

            # Tasks not installed — attempt one-time setup.
            self.append_startup_trace(
                f'wifi-tasks not installed for {interface_name!r}; attempting task setup'
            )
            logger.warning(
                'Scheduled tasks not found for interface %r. '
                'Attempting one-time task setup via elevated PowerShell.',
                interface_name,
            )

            if self._run_in_tray_context:
                # Tray mode: attempt task setup silently via elevated PowerShell.
                # If the user cancels the UAC prompt for powershell.exe, fall
                # through to the traditional restart-as-admin path.
                logger.warning(
                    'Tray mode: attempting silent scheduled-task installation for %r.',
                    interface_name,
                )
                try:
                    installed = task_manager.install_and_wait(interface_name)
                except OSError as exc:
                    self.append_startup_trace(f'tray-task-install failed (OSError): {exc}')
                    logger.warning(
                        'Scheduled-task installation raised an error: %s. '
                        'Falling back to administrator restart.',
                        exc,
                    )
                    installed = False

                if installed:
                    self.append_startup_trace('tray-task-install: tasks confirmed installed')
                    logger.info(
                        'Scheduled tasks installed successfully for %r. '
                        'No elevation needed.',
                        interface_name,
                    )
                    return None

                self.append_startup_trace(
                    'tray-task-install: failed or cancelled; falling back to admin restart'
                )
                # Fall through to the traditional restart-as-admin path below.
            else:
                # Console mode: show a dialog offering task setup as the
                # primary option alongside the traditional admin restart.
                return self._handle_console_admin_requirements_with_tasks(
                    config,
                    logger,
                    config_loader=config_loader,
                    interface_name=interface_name,
                    task_manager=task_manager,
                )

        # ── Traditional restart-as-admin path ────────────────────────────────
        # Used when:
        #   • interface_name is None (WiFi not detected before service start), OR
        #   • tray mode task installation failed/was cancelled.
        logger.warning(
            'Falling back to administrator restart for auto Ethernet feature.'
        )

        if self._run_in_tray_context:
            logger.warning(
                'Tray launch is not elevated while auto Ethernet disable is enabled. '
                'Attempting automatic administrator restart.'
            )
            try:
                launched = self.restart_as_administrator()
            except OSError as exc:
                # Elevation failed (e.g. access denied, code ≤ 32).  In tray mode we
                # must NOT show a blocking dialog here — MessageBoxW may appear behind
                # other windows with no foreground focus, permanently preventing the
                # tray icon from starting.  Permanently disable the feature so subsequent
                # launches do not attempt elevation again (and do not trigger the UAC dialog).
                self.append_startup_trace(f'tray-admin-restart failed: {exc}')
                logger.warning(
                    'Could not restart as administrator (tray mode): %s. '
                    'Permanently disabling automatic Wi-Fi disable on Ethernet.',
                    exc,
                )
                self._permanently_disable_ethernet_feature(config, config_loader, logger)
                return None
            else:
                if not launched:
                    # ShellExecuteW returned a non-success code other than a policy block.
                    # Permanently disable so subsequent launches do not prompt again.
                    self.append_startup_trace('tray-admin-restart cancelled by user')
                    logger.warning(
                        'Administrator restart was cancelled. '
                        'Permanently disabling automatic Wi-Fi disable on Ethernet.'
                    )
                    self._permanently_disable_ethernet_feature(config, config_loader, logger)
                    return None
                self.append_startup_trace('tray-admin-restart apparently launched, verifying elevated instance started')
                # ShellExecuteW can return a success code (> 32) even when the elevated
                # process is immediately killed by an administrator policy such as
                # AppLocker or a Software Restriction Policy.  Poll the single-instance
                # mutex for up to 2 seconds to confirm the elevated instance actually
                # started before giving up the current process.
                elevated_confirmed = False
                deadline = time.monotonic() + self._ELEVATED_INSTANCE_TIMEOUT
                poll_interval = self._ELEVATED_INSTANCE_POLL_INITIAL
                while time.monotonic() < deadline:
                    time.sleep(poll_interval)
                    poll_interval = min(poll_interval * 2, self._ELEVATED_INSTANCE_POLL_MAX)
                    try:
                        acquired = self.single_instance_guard.acquire()
                    except OSError as mutex_exc:
                        self.append_startup_trace(f'tray-admin-restart: mutex check error: {mutex_exc}')
                        logger.debug('Mutex check during elevated-instance verification failed: %s', mutex_exc)
                        break
                    if acquired:
                        # Mutex is still free; elevated process hasn't acquired it yet.
                        self.single_instance_guard.release()
                    else:
                        # Another process now holds the mutex — elevated instance running.
                        elevated_confirmed = True
                        break
                if elevated_confirmed:
                    self.append_startup_trace('tray-admin-restart: elevated instance confirmed running')
                    logger.info('Administrator restart launched automatically for tray startup. Exiting current instance.')
                    return 0
                # The elevated process never acquired the mutex.  It was most likely
                # blocked by an administrator policy after ShellExecuteW returned success.
                # Permanently disable so subsequent launches skip the elevation attempt.
                self.append_startup_trace(
                    'tray-admin-restart: elevated instance did not start within 2s, permanently disabling ethernet feature'
                )
                logger.warning(
                    'Elevated process did not acquire the instance guard within 2 seconds. '
                    'It was probably blocked by an administrator policy. '
                    'Permanently disabling automatic Wi-Fi disable on Ethernet.'
                )
                self._permanently_disable_ethernet_feature(config, config_loader, logger)
                return None

        # Console mode without task support: show the traditional restart dialog.
        return self._handle_console_admin_requirements_restart_only(
            config, logger, config_loader=config_loader
        )

    def _handle_console_admin_requirements_with_tasks(
        self,
        config,
        logger,
        *,
        config_loader,
        interface_name: str,
        task_manager: WifiAdapterTaskManager,
    ) -> int | None:
        """
        Console-mode admin requirement dialog that offers task setup as the
        primary option alongside the traditional administrator restart.

        Parameters:
            config:
                Loaded runtime configuration.
            logger:
                Application logger.
            config_loader:
                Optional ConfigLoader.
            interface_name:
                Wi-Fi interface name for task setup.
            task_manager:
                WifiAdapterTaskManager instance to use.

        Returns:
            ``None`` to continue, or exit code 0 when an elevated instance was
            launched.
        """
        choice: list[str] = ['session']

        def _on_setup_tasks() -> None:
            choice[0] = 'task'

        def _on_restart_admin() -> None:
            choice[0] = 'restart'

        def _on_disable_permanently() -> None:
            choice[0] = 'permanent'

        show_custom_dialog(
            'Administrator Required',
            'The "disable Wi-Fi when Ethernet is connected" feature needs administrator '
            'privileges to control the wireless adapter.\n\n'
            'Choose how to proceed:\n\n'
            '• Set Up Task Helper — installs a one-time Windows Task Scheduler helper '
            '(requires accepting a UAC prompt for Windows PowerShell).\n\n'
            '• Restart as Administrator — relaunches PolyFi elevated '
            '(may be blocked by a system policy on this PC).\n\n'
            '• Disable Permanently — saves the setting as disabled so this prompt '
            'does not appear again.\n\n'
            '• This Session Only — disables the feature until PolyFi is restarted.',
            buttons=[
                ('Set Up Task Helper', _on_setup_tasks),
                ('Restart as Administrator', _on_restart_admin),
                ('Disable Permanently', _on_disable_permanently),
                ('This Session Only', None),
            ],
        )

        if choice[0] == 'task':
            self.append_startup_trace('console: user chose task setup')
            try:
                installed = task_manager.install_and_wait(interface_name)
            except OSError as exc:
                self.append_startup_trace(f'console-task-install failed: {exc}')
                logger.error('Scheduled-task installation failed: %s', exc)
                show_dialog(
                    'error',
                    'Task Setup Failed',
                    f'PolyFi could not install the scheduled task helper:\n\n{exc}\n\n'
                    'Disabling automatic Ethernet Wi-Fi control for this session.',
                )
                installed = False

            if installed:
                self.append_startup_trace('console-task-install: tasks confirmed installed')
                logger.info(
                    'Scheduled tasks installed for %r. Feature will work without elevation.',
                    interface_name,
                )
                return None

            # Installation was not confirmed (user cancelled UAC or PowerShell also blocked).
            self.append_startup_trace('console-task-install: not confirmed within timeout')
            logger.warning(
                'Task setup was not confirmed for %r. '
                'Disabling automatic Ethernet Wi-Fi control for this session.',
                interface_name,
            )
            config.auto_disable_wifi_on_ethernet = False
            return None

        if choice[0] == 'restart':
            self.append_startup_trace('console: user chose restart as admin')
            try:
                launched = self.restart_as_administrator()
            except OSError as exc:
                self.append_startup_trace(f'admin-restart failed: {exc}')
                logger.error('Failed to restart with administrator privileges during startup: %s', exc)
                disable_permanently: list[bool] = [False]

                def _on_perm() -> None:
                    disable_permanently[0] = True

                show_custom_dialog(
                    'Restart Failed',
                    f'PolyFi could not restart as administrator:\n\n{exc}\n\n'
                    'You can disable this feature permanently so PolyFi does not ask again, '
                    'or continue with it turned off for this session only.',
                    buttons=[
                        ('Disable Permanently', _on_perm),
                        ('This Session Only', None),
                    ],
                )
                if disable_permanently[0]:
                    self._permanently_disable_ethernet_feature(config, config_loader, logger)
                else:
                    config.auto_disable_wifi_on_ethernet = False
                return None
            else:
                if launched:
                    self.append_startup_trace('admin-restart launched successfully')
                    logger.info('Administrator restart launched during startup. Exiting current instance.')
                    return 0
                self.append_startup_trace('admin-restart cancelled')
                logger.warning('Administrator restart was cancelled during startup.')

        if choice[0] == 'permanent':
            self.append_startup_trace('console: user chose disable permanently')
            self._permanently_disable_ethernet_feature(config, config_loader, logger)
            return None

        # 'session' or fall-through from cancelled restart.
        config.auto_disable_wifi_on_ethernet = False
        logger.warning(
            'Disabled automatic Wi-Fi disable on Ethernet for this running instance.'
        )
        return None

    def _handle_console_admin_requirements_restart_only(
        self,
        config,
        logger,
        *,
        config_loader,
    ) -> int | None:
        """
        Console-mode admin requirement dialog when task-based setup is
        unavailable (no interface name detected before service startup).

        Parameters:
            config:
                Loaded runtime configuration.
            logger:
                Application logger.
            config_loader:
                Optional ConfigLoader.

        Returns:
            ``None`` to continue, or exit code 0 when an elevated instance was
            launched.
        """
        restart_requested = show_dialog(
            'warning',
            'Administrator Required',
            'The "disable Wi-Fi when Ethernet is connected" feature needs administrator privileges.\n\n'
            'PolyFi detected that this setting is enabled, but the app was not started as administrator. '
            'You can restart it elevated now, or continue with that feature disabled for this session.',
            action_label='Restart as Administrator',
            action_callback=lambda: None,
            continue_label='Continue Without Auto Ethernet',
        )

        if restart_requested:
            try:
                launched = self.restart_as_administrator()
            except OSError as exc:
                self.append_startup_trace(f'admin-restart failed: {exc}')
                logger.error('Failed to restart with administrator privileges during startup: %s', exc)
                disable_permanently: list[bool] = [False]

                def _on_disable_permanently() -> None:
                    disable_permanently[0] = True

                show_custom_dialog(
                    'Restart Failed',
                    f'PolyFi could not restart as administrator:\n\n{exc}\n\n'
                    'You can disable this feature permanently so PolyFi does not ask again, '
                    'or continue with it turned off for this session only.',
                    buttons=[
                        ('Disable Permanently', _on_disable_permanently),
                        ('This Session Only', None),
                    ],
                )
                if disable_permanently[0]:
                    self._permanently_disable_ethernet_feature(config, config_loader, logger)
                else:
                    config.auto_disable_wifi_on_ethernet = False
                    logger.warning(
                        'Disabled automatic Wi-Fi disable on Ethernet for this running instance.'
                    )
                return None
            else:
                if launched:
                    self.append_startup_trace('admin-restart launched successfully')
                    logger.info('Administrator restart launched during startup. Exiting current instance.')
                    return 0
                self.append_startup_trace('admin-restart cancelled')
                logger.warning('Administrator restart was cancelled during startup.')

        config.auto_disable_wifi_on_ethernet = False
        logger.warning(
            'Disabled automatic Wi-Fi disable on Ethernet for this running instance because the process is not elevated.'
        )
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
                'PolyFi is already running. Close the existing instance before starting another one.',
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
                self.build_runtime_argument_list(args, force_tray=True),
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
        if args.print_paths:
            return self.print_paths()

        self.append_startup_trace(f'handle_run_command argv={argv if (argv := list(sys.argv[1:])) else []}')
        override_result = self.apply_cli_overrides_from_args(args)
        if override_result != 0:
            self.append_startup_trace(f'cli override validation failed code={override_result}')
            return override_result

        loader = ConfigLoader(config_path=args.config)
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
        running_consoleless = sys.stdout is None
        run_in_tray = args.tray or config.start_minimized_to_tray or running_consoleless
        self._run_in_tray_context = run_in_tray
        self.append_startup_trace(
            f'config loaded run_in_tray={run_in_tray} admin={self.is_running_as_administrator()} '
            f'auto_disable_wifi_on_ethernet={config.auto_disable_wifi_on_ethernet}'
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

        # ── Early interface detection ────────────────────────────────────────
        # Detect the Wi-Fi interface name before handle_startup_admin_requirements
        # so the task-based elevation path can check/install scheduled tasks with
        # the correct interface name.  The service will re-detect (and persist)
        # the name during its own initialisation; this is a best-effort preview.
        early_wifi_interface: str | None = config.interface_name.strip() if config.interface_name else None
        if not early_wifi_interface and config.auto_disable_wifi_on_ethernet and not self.is_running_as_administrator():
            try:
                early_wifi_interface = NetshWiFiApi(logger=logger).detect_wifi_interface()
            except Exception:
                # Interface not detected — fall back to persisted state if available.
                saved = ManagedInterfaceStateStore(self.paths.managed_interface_file).load()
                if saved:
                    early_wifi_interface = saved.interface_name

        startup_admin_result = self.handle_startup_admin_requirements(
            config,
            logger,
            config_loader=loader,
            interface_name=early_wifi_interface,
        )
        if startup_admin_result is not None:
            self.append_startup_trace(f'startup admin requirements returned code={startup_admin_result}')
            return startup_admin_result

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

        # ── Build task manager if tasks are installed ──────────────────────
        # When scheduled tasks are present for the detected interface, wire the
        # task manager into NetshWiFiApi so disable/enable calls go through
        # schtasks /run (no elevation needed).
        task_manager: WifiAdapterTaskManager | None = None
        if (
            config.auto_disable_wifi_on_ethernet
            and not self.is_running_as_administrator()
            and early_wifi_interface is not None
        ):
            candidate = WifiAdapterTaskManager()
            if candidate.are_installed(early_wifi_interface):
                task_manager = candidate
                logger.info(
                    'Using scheduled tasks for Wi-Fi adapter control on interface %r.',
                    early_wifi_interface,
                )

        wifi_api = NetshWiFiApi(logger=logger, task_manager=task_manager)
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
                    restart_as_admin_callback=self.restart_as_administrator,
                    show_output_console_callback=(
                        self.console_output_manager.show_console_with_history
                        if self.console_output_manager is not None
                        else None
                    ),
                )
                tray_app.run()
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
