from __future__ import annotations

import argparse
import ctypes
import subprocess
import sys
from pathlib import Path

from wifi_pref_manager.scheduler import TaskSchedulerInstaller

APP_NAME = 'PolyFi: Ranked'
START_MENU_FOLDER = 'PolyFi Ranked'


class StartupManager:
    def __init__(self) -> None:
        self.python_executable = Path(sys.executable)

    @property
    def pythonw_executable(self) -> Path:
        candidate = self.python_executable.with_name('pythonw.exe')
        return candidate if candidate.exists() else self.python_executable

    def create_start_menu_shortcuts(self) -> None:
        command = (
            "$shell = New-Object -ComObject WScript.Shell;"
            '$folder = Join-Path $env:APPDATA "Microsoft\\Windows\\Start Menu\\Programs\\' + START_MENU_FOLDER + '";'
            'New-Item -ItemType Directory -Path $folder -Force | Out-Null;'
            '$shortcuts = @('
            f"@{{Name='{APP_NAME}';Args='-m wifi_pref_manager.app --tray --require-admin';Target='{self.pythonw_executable}'}},"
            f"@{{Name='Uninstall {APP_NAME}';Args='-m wifi_pref_manager.startup uninstall';Target='{self.python_executable}'}},"
            f"@{{Name='Enable Start with Windows';Args='-m wifi_pref_manager.startup enable-autostart';Target='{self.python_executable}'}}"
            ');'
            'foreach ($entry in $shortcuts) {'
            '$path = Join-Path $folder ($entry.Name + ".lnk");'
            '$shortcut = $shell.CreateShortcut($path);'
            '$shortcut.TargetPath = $entry.Target;'
            '$shortcut.Arguments = $entry.Args;'
            '$shortcut.WorkingDirectory = [System.IO.Path]::GetDirectoryName($entry.Target);'
            '$shortcut.Save();'
            '}'
        )
        self._run_powershell(command)

    def remove_start_menu_shortcuts(self) -> None:
        command = (
            '$folder = Join-Path $env:APPDATA "Microsoft\\Windows\\Start Menu\\Programs\\' + START_MENU_FOLDER + '";'
            'if (Test-Path $folder) { Remove-Item -Path $folder -Recurse -Force }'
        )
        self._run_powershell(command)

    def _run_powershell(self, command: str) -> None:
        subprocess.run(
            ['powershell', '-NoProfile', '-NonInteractive', '-Command', command],
            check=True,
            capture_output=True,
            text=True,
        )


def is_running_as_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:  # noqa: BLE001
        return False


def relaunch_as_admin(argv: list[str]) -> bool:
    params = ' '.join(f'"{arg}"' for arg in argv)
    try:
        result = ctypes.windll.shell32.ShellExecuteW(None, 'runas', sys.executable, params, None, 1)
    except Exception:  # noqa: BLE001
        return False
    return int(result) > 32


def main() -> int:
    parser = argparse.ArgumentParser(description='Manage PolyFi start-menu and startup behavior.')
    parser.add_argument('command', choices=['install-shortcuts', 'remove-shortcuts', 'enable-autostart', 'disable-autostart', 'uninstall'])
    args = parser.parse_args()

    startup_manager = StartupManager()
    task_installer = TaskSchedulerInstaller(python_executable=str(startup_manager.pythonw_executable))

    if args.command == 'install-shortcuts':
        startup_manager.create_start_menu_shortcuts()
        print('Installed start-menu shortcuts.')
        return 0
    if args.command == 'remove-shortcuts':
        startup_manager.remove_start_menu_shortcuts()
        print('Removed start-menu shortcuts.')
        return 0
    if args.command == 'enable-autostart':
        task_installer.install()
        print('Enabled start with Windows.')
        return 0
    if args.command == 'disable-autostart':
        task_installer.uninstall()
        print('Disabled start with Windows.')
        return 0

    task_installer.uninstall()
    startup_manager.remove_start_menu_shortcuts()
    print('PolyFi startup artifacts removed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
