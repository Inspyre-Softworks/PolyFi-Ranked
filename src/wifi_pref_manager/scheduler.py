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

import subprocess
import sys


TASK_NAME = 'PolyFi Ranked'


class TaskSchedulerInstaller:
    """
    Registers a Windows scheduled task that launches the app at logon.

    Methods:
        install:
            Create or update the scheduled task.
    """

    def __init__(self, python_executable: str) -> None:
        self.python_executable = python_executable

    def install(self) -> None:
        """
        Create or replace the logon startup task.
        """
        app_module = 'wifi_pref_manager.app'
        task_command = f'"{self.python_executable}" -m {app_module} --tray'

        command = [
            'schtasks',
            '/Create',
            '/F',
            '/SC',
            'ONLOGON',
            '/RL',
            'LIMITED',
            '/TN',
            TASK_NAME,
            '/TR',
            task_command,
        ]

        subprocess.run(command, check=True)
        print(f'Installed scheduled task: {TASK_NAME}')

    def uninstall(self) -> None:
        """Delete the scheduled task if it exists."""
        command = [
            'schtasks',
            '/Delete',
            '/F',
            '/TN',
            TASK_NAME,
        ]
        subprocess.run(command, check=False)
        print(f'Removed scheduled task: {TASK_NAME}')


def main() -> int:
    """
    CLI entry point for scheduled task installation.

    Returns:
        Process exit code.
    """
    installer = TaskSchedulerInstaller(python_executable=sys.executable)
    installer.install()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
