"""
Author:
    Inspyre Softworks

Project:
    PolyFi: Ranked

File:
    scheduler.py

Description:
    Installs a Windows Task Scheduler entry to launch the tray app at logon.

Functions:
    main:
        Command-line entry point.

Constants:
    TASK_NAME:
        Default Windows scheduled task name.

Dependencies:
    subprocess
    sys

Example Usage:
    poetry run polyfi-ranked-install-task
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

from wifi_pref_manager.install_record import default_install_record_path, upsert_install_record
from wifi_pref_manager.paths import AppPaths
from wifi_pref_manager.windows_shell import resolve_runtime_launch_target

TASK_NAME = 'PolyFi Ranked'


class TaskSchedulerInstaller:
    """
    Registers a Windows scheduled task that launches the app at logon.

    Methods:
        install:
            Create or update the scheduled task.
    """

    def __init__(
        self,
        launch_executable: str | Path,
        launch_arguments: list[str] | None = None,
        task_name: str = TASK_NAME,
    ) -> None:
        self.launch_executable = Path(launch_executable)
        self.launch_arguments = list(launch_arguments or [])
        self.task_name = task_name

    @staticmethod
    def _hidden_subprocess_kwargs() -> dict[str, object]:
        """
        Return Windows-specific subprocess flags that suppress console windows.

        Returns:
            Keyword arguments safe to splat into ``subprocess.run``.
        """
        kwargs: dict[str, object] = {}
        create_no_window = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        if create_no_window:
            kwargs['creationflags'] = create_no_window

        startupinfo_type = getattr(subprocess, 'STARTUPINFO', None)
        startf_use_showwindow = getattr(subprocess, 'STARTF_USESHOWWINDOW', 0)
        if startupinfo_type is not None and startf_use_showwindow:
            startupinfo = startupinfo_type()
            startupinfo.dwFlags |= startf_use_showwindow
            startupinfo.wShowWindow = 0
            kwargs['startupinfo'] = startupinfo

        return kwargs

    @classmethod
    def for_current_runtime(cls, task_name: str = TASK_NAME) -> TaskSchedulerInstaller:
        """
        Build an installer that launches the current PolyFi runtime in tray mode.

        Parameters:
            task_name:
                Scheduled task name to create.

        Returns:
            Configured installer.
        """
        executable, base_arguments, _working_directory = resolve_runtime_launch_target(
            prefer_windowless=False
        )
        return cls(
            launch_executable=executable,
            launch_arguments=[*base_arguments, '--tray'],
            task_name=task_name,
        )

    def build_command(self) -> list[str]:
        """
        Build the ``schtasks`` command used to register the logon task.

        Returns:
            Command list for ``subprocess.run``.
        """
        task_command = subprocess.list2cmdline([str(self.launch_executable), *self.launch_arguments])
        return [
            'schtasks',
            '/Create',
            '/F',
            '/SC',
            'ONLOGON',
            '/RL',
            'LIMITED',
            '/TN',
            self.task_name,
            '/TR',
            task_command,
        ]

    def build_uninstall_command(self) -> list[str]:
        """
        Build the ``schtasks`` command used to remove the logon task.

        Returns:
            Command list for ``subprocess.run``.
        """
        return [
            'schtasks',
            '/Delete',
            '/F',
            '/TN',
            self.task_name,
        ]

    def install(self) -> None:
        """
        Create or replace the logon startup task.
        """
        result = subprocess.run(
            self.build_command(),
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            check=False,
            **self._hidden_subprocess_kwargs(),
        )
        if result.returncode != 0:
            details = (result.stderr or result.stdout).strip() or 'Unknown error.'
            raise OSError(f'Could not create scheduled task {self.task_name!r}: {details}')
        print(f'Installed scheduled task: {self.task_name}')

    def uninstall(self) -> bool:
        """
        Remove the logon startup task if it exists.

        Returns:
            ``True`` when the task was removed, otherwise ``False`` when it was
            already absent.
        """
        result = subprocess.run(
            self.build_uninstall_command(),
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            check=False,
            **self._hidden_subprocess_kwargs(),
        )
        if result.returncode == 0:
            return True

        details = (result.stderr or result.stdout).strip() or 'Unknown error.'
        normalized = details.casefold()
        if 'cannot find' in normalized or 'does not exist' in normalized:
            return False
        raise OSError(f'Could not remove scheduled task {self.task_name!r}: {details}')


def build_argument_parser() -> argparse.ArgumentParser:
    """
    Build the CLI parser for the startup-task installer.

    Returns:
        Configured argument parser.
    """
    parser = argparse.ArgumentParser(
        description='Install a Windows Task Scheduler entry that launches PolyFi in tray mode at logon.',
    )
    parser.add_argument(
        '--task-name',
        default=TASK_NAME,
        help='Optional Windows scheduled task name. Defaults to "PolyFi Ranked".',
    )
    parser.add_argument(
        '--uninstall',
        action='store_true',
        help='Remove the scheduled task instead of creating it.',
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """
    CLI entry point for scheduled task installation.

    Parameters:
        argv:
            Optional CLI argument list.

    Returns:
        Process exit code.
    """
    args = build_argument_parser().parse_args(argv)
    installer = TaskSchedulerInstaller.for_current_runtime(task_name=args.task_name)
    app_paths = AppPaths()
    record_path = default_install_record_path(app_paths.app_data_root)
    record_paths = {
        'app_data_root': app_paths.app_data_root,
        'command_dir': Path(sys.executable).parent,
        'command_path': Path(sys.executable),
    }
    try:
        if args.uninstall:
            removed = installer.uninstall()
            upsert_install_record(
                record_path,
                path_updates=record_paths,
                feature_updates={'scheduled_logon_task': False},
            )
            if removed:
                print(f'Removed scheduled task: {args.task_name}')
            else:
                print(f'No scheduled task found: {args.task_name}')
        else:
            installer.install()
            upsert_install_record(
                record_path,
                path_updates=record_paths,
                feature_updates={'scheduled_logon_task': True},
            )
    except OSError as exc:
        print(f'Scheduled task error: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
