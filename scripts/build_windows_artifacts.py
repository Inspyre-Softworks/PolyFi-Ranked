from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import time
import tomllib
from typing import Mapping


APP_DIST_DIR_NAME = 'polyfi-ranked'
APP_EXECUTABLE_NAME = 'polyfi-ranked.exe'
CONSOLE_EXECUTABLE_NAME = 'polyfi-ranked-console.exe'
INSTALLER_SCRIPT_NAME = 'polyfi-ranked.iss'
SPEC_FILE_NAME = 'polyfi-ranked.spec'
PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class PackagingPaths:
    project_root: Path
    spec_file: Path
    installer_script: Path
    app_icon_file: Path
    setup_icon_file: Path
    wizard_image_file: Path
    wizard_small_image_file: Path
    pyinstaller_dist_root: Path
    pyinstaller_app_dir: Path
    pyinstaller_work_root: Path
    installer_output_dir: Path


def build_packaging_paths(project_root: Path = PROJECT_ROOT) -> PackagingPaths:
    build_root = project_root / 'build' / 'windows'
    pyinstaller_dist_root = project_root / 'dist' / 'pyinstaller'
    return PackagingPaths(
        project_root=project_root,
        spec_file=project_root / 'packaging' / 'pyinstaller' / SPEC_FILE_NAME,
        installer_script=project_root / 'packaging' / 'inno' / INSTALLER_SCRIPT_NAME,
        app_icon_file=build_root / 'polyfi-ranked.ico',
        setup_icon_file=build_root / 'polyfi-ranked-setup.ico',
        wizard_image_file=build_root / 'polyfi-ranked-wizard.png',
        wizard_small_image_file=build_root / 'polyfi-ranked-wizard-small.png',
        pyinstaller_dist_root=pyinstaller_dist_root,
        pyinstaller_app_dir=pyinstaller_dist_root / APP_DIST_DIR_NAME,
        pyinstaller_work_root=project_root / 'build' / 'pyinstaller',
        installer_output_dir=project_root / 'dist' / 'installer',
    )


def read_project_version(project_root: Path = PROJECT_ROOT) -> str:
    pyproject_path = project_root / 'pyproject.toml'
    pyproject = tomllib.loads(pyproject_path.read_text(encoding='utf-8'))
    return pyproject['tool']['poetry']['version']


def ensure_packaging_art(paths: PackagingPaths, project_root: Path = PROJECT_ROOT) -> dict[str, Path]:
    src_root = project_root / 'src'
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))

    from wifi_pref_manager.icon_assets import write_app_icon_file, write_installer_art_files

    write_app_icon_file(paths.app_icon_file)
    return write_installer_art_files(paths.setup_icon_file.parent)


def _retry_remove_readonly(
    func,
    path: str,
    exc_info,
) -> None:
    del exc_info
    try:
        os.chmod(path, stat.S_IWRITE)
    except OSError:
        pass
    func(path)


def remove_tree(path: Path, *, retries: int = 6, initial_delay_seconds: float = 0.2) -> None:
    if not path.exists():
        return

    last_error: OSError | None = None
    delay_seconds = initial_delay_seconds
    for _attempt in range(retries):
        try:
            shutil.rmtree(path, onerror=_retry_remove_readonly)
            return
        except FileNotFoundError:
            return
        except OSError as exc:
            last_error = exc
            time.sleep(delay_seconds)
            delay_seconds *= 2

    if last_error is not None:
        raise OSError(
            f'Could not remove {path} after {retries} attempts: {last_error}'
        ) from last_error


def prepare_pyinstaller_paths(paths: PackagingPaths, *, clean: bool) -> None:
    paths.pyinstaller_dist_root.mkdir(parents=True, exist_ok=True)
    paths.pyinstaller_work_root.parent.mkdir(parents=True, exist_ok=True)
    if not clean:
        return

    remove_tree(paths.pyinstaller_app_dir)
    remove_tree(paths.pyinstaller_work_root)


def build_pyinstaller_command(paths: PackagingPaths) -> list[str]:
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm']
    command.extend(
        [
            '--distpath',
            str(paths.pyinstaller_dist_root),
            '--workpath',
            str(paths.pyinstaller_work_root),
            str(paths.spec_file),
        ]
    )
    return command


def candidate_iscc_paths(env: Mapping[str, str] | None = None) -> list[Path]:
    environment = dict(os.environ if env is None else env)
    candidates: list[Path] = []
    override = environment.get('ISCC_EXE', '').strip()
    if override:
        candidates.append(Path(override))

    for executable in ('ISCC.exe', 'iscc'):
        resolved = shutil.which(executable)
        if resolved:
            candidates.append(Path(resolved))

    for variable_name in ('ProgramFiles(x86)', 'ProgramFiles'):
        base_dir = environment.get(variable_name, '').strip()
        if base_dir:
            candidates.append(Path(base_dir) / 'Inno Setup 6' / 'ISCC.exe')
            candidates.append(Path(base_dir) / 'Inno Setup 5' / 'ISCC.exe')

    unique_candidates: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).casefold()
        if key in seen:
            continue
        seen.add(key)
        unique_candidates.append(candidate)
    return unique_candidates


def resolve_iscc_path(explicit_path: str | None = None) -> Path | None:
    if explicit_path:
        candidate = Path(explicit_path)
        if candidate.exists():
            return candidate
        return None

    for candidate in candidate_iscc_paths():
        if candidate.exists():
            return candidate
    return None


def build_iscc_command(
    iscc_path: Path,
    paths: PackagingPaths,
    version: str,
) -> list[str]:
    return [
        str(iscc_path),
        f'/DMyAppVersion={version}',
        f'/DMyAppDistDir={paths.pyinstaller_app_dir}',
        f'/DMyInstallerOutputDir={paths.installer_output_dir}',
        str(paths.installer_script),
    ]


def installer_output_path(paths: PackagingPaths, version: str) -> Path:
    return paths.installer_output_dir / f'polyfi-ranked-setup-{version}.exe'


def run_command(command: list[str], *, cwd: Path) -> None:
    print('>>', subprocess.list2cmdline(command))
    result = subprocess.run(command, cwd=cwd, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            'Build the PolyFi PyInstaller app folder and, when Inno Setup is '
            'available, compile a Windows installer executable.'
        )
    )
    parser.add_argument(
        '--skip-pyinstaller',
        action='store_true',
        help='Skip rebuilding the PyInstaller onedir app bundle.',
    )
    parser.add_argument(
        '--skip-installer',
        action='store_true',
        help='Skip compiling the Inno Setup installer.',
    )
    parser.add_argument(
        '--no-clean',
        action='store_true',
        help='Reuse the existing PyInstaller work directory instead of cleaning it first.',
    )
    parser.add_argument(
        '--iscc',
        default=None,
        help='Optional path to ISCC.exe when Inno Setup is not on PATH.',
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    paths = build_packaging_paths()
    version = read_project_version(paths.project_root)

    if not args.skip_pyinstaller:
        ensure_packaging_art(paths, paths.project_root)
        prepare_pyinstaller_paths(paths, clean=not args.no_clean)
        run_command(
            build_pyinstaller_command(paths),
            cwd=paths.project_root,
        )
    elif not paths.pyinstaller_app_dir.exists():
        print(
            f'PyInstaller output was skipped, but {paths.pyinstaller_app_dir} does not exist.',
            file=sys.stderr,
        )
        return 1

    app_executable = paths.pyinstaller_app_dir / APP_EXECUTABLE_NAME
    if not app_executable.exists():
        print(f'Expected bundled executable was not found: {app_executable}', file=sys.stderr)
        return 1
    console_executable = paths.pyinstaller_app_dir / CONSOLE_EXECUTABLE_NAME
    if not console_executable.exists():
        print(f'Expected console executable was not found: {console_executable}', file=sys.stderr)
        return 1

    print(f'PyInstaller app bundle: {app_executable}')

    if args.skip_installer:
        return 0

    iscc_path = resolve_iscc_path(args.iscc)
    if iscc_path is None:
        checked = [Path(args.iscc)] if args.iscc else candidate_iscc_paths()
        print(
            'Could not find ISCC.exe. Install Inno Setup 6 or pass --iscc with the full path.',
            file=sys.stderr,
        )
        if checked:
            print('Checked these locations:', file=sys.stderr)
            for candidate in checked:
                print(f'  - {candidate}', file=sys.stderr)
        return 1

    paths.installer_output_dir.mkdir(parents=True, exist_ok=True)
    run_command(build_iscc_command(iscc_path, paths, version), cwd=paths.project_root)
    print(f'Windows installer: {installer_output_path(paths, version)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
