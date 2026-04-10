"""
Author:
    Inspyre Softworks

Project:
    PolyFi: Ranked

File:
    windows_shell.py

Description:
    Windows shell integration helpers such as Start Menu shortcut management.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys

from wifi_pref_manager.icon_assets import write_app_icon_file
from wifi_pref_manager.paths import APP_NAME, AppPaths


def resolve_runtime_launch_target(*, prefer_windowless: bool) -> tuple[Path, list[str], Path]:
    """
    Resolve the preferred executable and base arguments for launching PolyFi.

    Parameters:
        prefer_windowless:
            Whether to prefer ``pythonw.exe`` when available.

    Returns:
        ``(executable, arguments, working_directory)``.
    """
    executable = Path(sys.executable).resolve()
    if prefer_windowless:
        pythonw = executable.with_name('pythonw.exe')
        if pythonw.exists():
            return pythonw, ['-m', 'wifi_pref_manager.app'], pythonw.parent

    packaged_launcher = executable.parent / 'polyfi-ranked.exe'
    if packaged_launcher.exists():
        return packaged_launcher, [], packaged_launcher.parent

    return executable, ['-m', 'wifi_pref_manager.app'], executable.parent


@dataclass(frozen=True)
class ShortcutSpec:
    """
    Specification for a Windows shortcut.
    """

    shortcut_path: Path
    target_path: Path
    arguments: list[str]
    working_directory: Path
    icon_path: Path
    description: str


class StartMenuShortcutManager:
    """
    Manage the user's PolyFi Start Menu shortcut.
    """

    def __init__(self, paths: AppPaths | None = None) -> None:
        self.paths = paths or AppPaths()

    def get_shortcut_path(self) -> Path:
        """
        Return the shortcut path used for the Start Menu entry.
        """
        return self.paths.start_menu_shortcut_file

    def install(self, launch_arguments: list[str], overwrite: bool = False) -> Path:
        """
        Create the Start Menu shortcut and its icon file.

        Parameters:
            launch_arguments:
                Command-line arguments passed to the runtime launcher.
            overwrite:
                Whether an existing shortcut may be replaced.

        Returns:
            Shortcut path.
        """
        shortcut_path = self.get_shortcut_path()
        if shortcut_path.exists():
            if not overwrite:
                raise FileExistsError(f'Start Menu shortcut already exists: {shortcut_path}')
            shortcut_path.unlink()

        spec = self._build_shortcut_spec(launch_arguments)
        write_app_icon_file(spec.icon_path)
        spec.shortcut_path.parent.mkdir(parents=True, exist_ok=True)
        self._create_shortcut(spec)
        return spec.shortcut_path

    def remove(self) -> bool:
        """
        Remove the Start Menu shortcut if it exists.

        Returns:
            True when the shortcut was removed.
        """
        shortcut_path = self.get_shortcut_path()
        if not shortcut_path.exists():
            return False
        shortcut_path.unlink()
        return True

    def _build_shortcut_spec(self, launch_arguments: list[str]) -> ShortcutSpec:
        executable, base_args, working_directory = self._resolve_runtime_launch_target()
        return ShortcutSpec(
            shortcut_path=self.get_shortcut_path(),
            target_path=executable,
            arguments=[*base_args, *launch_arguments],
            working_directory=working_directory,
            icon_path=self.paths.start_menu_icon_file,
            description=f'Launch {APP_NAME} in the system tray.',
        )

    def _resolve_runtime_launch_target(self) -> tuple[Path, list[str], Path]:
        """
        Resolve the preferred executable and base arguments for a Start Menu launch.
        """
        return resolve_runtime_launch_target(prefer_windowless=True)

    def _create_shortcut(self, spec: ShortcutSpec) -> None:
        """
        Create a Windows .lnk file through the WScript.Shell COM API.
        """

        def ps_quote(value: str) -> str:
            return "'" + value.replace("'", "''") + "'"

        arguments = subprocess.list2cmdline(spec.arguments)
        script = f"""
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut({ps_quote(str(spec.shortcut_path))})
$shortcut.TargetPath = {ps_quote(str(spec.target_path))}
$shortcut.Arguments = {ps_quote(arguments)}
$shortcut.WorkingDirectory = {ps_quote(str(spec.working_directory))}
$shortcut.Description = {ps_quote(spec.description)}
$shortcut.IconLocation = {ps_quote(str(spec.icon_path))}
$shortcut.Save()
"""
        result = subprocess.run(
            ['powershell', '-NoProfile', '-NonInteractive', '-Command', script],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise OSError(
                'Could not create the Start Menu shortcut.\n'
                f'stdout:\n{result.stdout}\n'
                f'stderr:\n{result.stderr}'
            )
