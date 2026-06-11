from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / 'scripts' / 'build_windows_artifacts.py'

_SPEC = spec_from_file_location('build_windows_artifacts', SCRIPT_PATH)
if _SPEC is None or _SPEC.loader is None:  # pragma: no cover
    raise RuntimeError(f'Could not load {SCRIPT_PATH}')
build_windows_artifacts = module_from_spec(_SPEC)
sys.modules[_SPEC.name] = build_windows_artifacts
_SPEC.loader.exec_module(build_windows_artifacts)

sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from wifi_pref_manager import __version__


class WindowsPackagingTests(unittest.TestCase):
    def test_project_version_matches_package_version(self) -> None:
        self.assertEqual(build_windows_artifacts.read_project_version(PROJECT_ROOT), __version__)

    def test_build_pyinstaller_command_targets_repo_spec_and_output_dirs(self) -> None:
        paths = build_windows_artifacts.build_packaging_paths(PROJECT_ROOT)

        command = build_windows_artifacts.build_pyinstaller_command(paths)

        self.assertEqual(command[:4], [sys.executable, '-m', 'PyInstaller', '--noconfirm'])
        self.assertNotIn('--clean', command)
        self.assertIn(str(paths.spec_file), command)
        self.assertIn(str(paths.pyinstaller_dist_root), command)
        self.assertIn(str(paths.pyinstaller_work_root), command)

    @patch.object(build_windows_artifacts.shutil, 'which')
    def test_candidate_iscc_paths_honor_override_and_deduplicate(
        self,
        mock_which: Mock,
    ) -> None:
        mock_which.side_effect = [r'C:\Tools\ISCC.exe', r'C:\Tools\ISCC.exe']
        env = {
            'ISCC_EXE': r'C:\Tools\ISCC.exe',
            'ProgramFiles(x86)': r'C:\Program Files (x86)',
            'ProgramFiles': r'C:\Program Files',
        }

        candidates = build_windows_artifacts.candidate_iscc_paths(env)

        self.assertEqual(candidates[0], Path(r'C:\Tools\ISCC.exe'))
        self.assertEqual(candidates.count(Path(r'C:\Tools\ISCC.exe')), 1)
        self.assertIn(Path(r'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'), candidates)
        self.assertIn(Path(r'C:\Program Files\Inno Setup 6\ISCC.exe'), candidates)

    def test_resolve_iscc_path_accepts_explicit_existing_file(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            iscc_path = Path(tmp_dir) / 'ISCC.exe'
            iscc_path.write_text('', encoding='utf-8')

            resolved = build_windows_artifacts.resolve_iscc_path(str(iscc_path))

        self.assertEqual(resolved, iscc_path)

    def test_build_iscc_command_passes_dynamic_define_values(self) -> None:
        paths = build_windows_artifacts.build_packaging_paths(PROJECT_ROOT)
        version = build_windows_artifacts.read_project_version(PROJECT_ROOT)
        iscc_path = Path(r'C:\Program Files (x86)\Inno Setup 6\ISCC.exe')

        command = build_windows_artifacts.build_iscc_command(iscc_path, paths, version)

        self.assertEqual(command[0], str(iscc_path))
        self.assertIn(f'/DMyAppVersion={version}', command)
        self.assertIn(f'/DMyAppDistDir={paths.pyinstaller_app_dir}', command)
        self.assertIn(f'/DMyInstallerOutputDir={paths.installer_output_dir}', command)
        self.assertEqual(command[-1], str(paths.installer_script))

    def test_build_packaging_paths_include_installer_art_outputs(self) -> None:
        paths = build_windows_artifacts.build_packaging_paths(PROJECT_ROOT)

        self.assertEqual(paths.app_icon_file.name, 'polyfi-ranked.ico')
        self.assertEqual(paths.setup_icon_file.name, 'polyfi-ranked-setup.ico')
        self.assertEqual(paths.wizard_image_file.name, 'polyfi-ranked-wizard.png')
        self.assertEqual(paths.wizard_small_image_file.name, 'polyfi-ranked-wizard-small.png')

    def test_pyinstaller_spec_collects_inspy_logger_version_data(self) -> None:
        spec_content = (
            PROJECT_ROOT / 'packaging' / 'pyinstaller' / 'polyfi-ranked.spec'
        ).read_text(encoding='utf-8')

        self.assertIn("collect_data_files('inspy_logger'", spec_content)
        self.assertIn("version/VERSION.txt", spec_content)

    def test_pyinstaller_spec_builds_windowed_app_and_console_launcher(self) -> None:
        spec_content = (
            PROJECT_ROOT / 'packaging' / 'pyinstaller' / 'polyfi-ranked.spec'
        ).read_text(encoding='utf-8')

        self.assertIn("name='polyfi-ranked'", spec_content)
        self.assertIn('console=False', spec_content)
        self.assertIn("name='polyfi-ranked-console'", spec_content)
        self.assertIn('console=True', spec_content)

    def test_inno_script_uses_branded_art_and_installer_tasks(self) -> None:
        script_content = (
            PROJECT_ROOT / 'packaging' / 'inno' / 'polyfi-ranked.iss'
        ).read_text(encoding='utf-8')

        self.assertIn('WizardImageFile', script_content)
        self.assertIn('WizardSmallImageFile', script_content)
        self.assertIn('polyfi-ranked-wizard.png', script_content)
        self.assertIn('polyfi-ranked-wizard-small.png', script_content)
        self.assertIn('ChangesEnvironment=yes', script_content)
        self.assertIn('Name: "startmenuicons"', script_content)
        self.assertIn('Name: "addtopath"', script_content)
        self.assertIn('Name: "startupshortcut"', script_content)
        self.assertIn('Name: "logontask"', script_content)
        self.assertIn('Name: "wifitasks"', script_content)
        self.assertIn('DefaultGroupName=PolyFi Ranked', script_content)
        self.assertIn('#define MyConsoleExeName "polyfi-ranked-console.exe"', script_content)
        self.assertIn('Name: "{group}\\PolyFi Ranked"', script_content)
        self.assertIn('Name: "{group}\\PolyFi Ranked Console"; Filename: "{app}\\{#MyConsoleExeName}"', script_content)
        self.assertIn('Name: "{group}\\Uninstall Wi-Fi Helper Tasks"', script_content)
        self.assertIn('manage_install_record.ps1', script_content)
        self.assertIn('GetInstallRecordParameters', script_content)
        self.assertIn('manage_windows_path.ps1', script_content)
        self.assertIn('-Mode Add -InstallDir', script_content)
        self.assertIn('Tasks: startmenuicons', script_content)
        self.assertIn('windows startup install --force', script_content)
        self.assertIn('windows logon-task install', script_content)
        self.assertIn('windows wifi-tasks install', script_content)
        self.assertIn('-ScheduledLogonTask \' + BoolToLower(WizardIsTaskSelected(\'logontask\'))', script_content)
        self.assertIn('--tray --show-splash', script_content)
        self.assertNotIn('--tray --direct-tray', script_content)
        self.assertIn('Filename: "{group}\\PolyFi Ranked"; Description: "Launch PolyFi in the system tray"; Flags: nowait postinstall shellexec skipifsilent unchecked; Tasks: startmenuicons', script_content)
        self.assertIn('Filename: "{app}\\{#MyAppExeName}"; Parameters: "--tray --show-splash"; Description: "Launch PolyFi in the system tray"; Flags: nowait postinstall skipifsilent unchecked; Tasks: not startmenuicons', script_content)
        self.assertIn('[UninstallRun]', script_content)
        self.assertIn('windows uninstall', script_content)
        self.assertIn('-Mode Remove -InstallDir', script_content)

    @patch.object(build_windows_artifacts, 'remove_tree')
    def test_prepare_pyinstaller_paths_cleans_work_and_app_dirs_when_requested(
        self,
        mock_remove_tree: Mock,
    ) -> None:
        paths = build_windows_artifacts.build_packaging_paths(PROJECT_ROOT)

        build_windows_artifacts.prepare_pyinstaller_paths(paths, clean=True)

        mock_remove_tree.assert_any_call(paths.pyinstaller_app_dir)
        mock_remove_tree.assert_any_call(paths.pyinstaller_work_root)

    @patch.object(build_windows_artifacts, 'remove_tree')
    def test_prepare_pyinstaller_paths_skips_cleanup_when_not_requested(
        self,
        mock_remove_tree: Mock,
    ) -> None:
        paths = build_windows_artifacts.build_packaging_paths(PROJECT_ROOT)

        build_windows_artifacts.prepare_pyinstaller_paths(paths, clean=False)

        mock_remove_tree.assert_not_called()

    @patch.object(build_windows_artifacts, 'ensure_packaging_art')
    @patch.object(build_windows_artifacts, 'prepare_pyinstaller_paths')
    @patch.object(build_windows_artifacts, 'run_command')
    @patch.object(build_windows_artifacts, 'read_project_version', return_value='1.0.0-dev.6')
    @patch.object(build_windows_artifacts, 'build_packaging_paths')
    def test_main_builds_packaging_art_before_pyinstaller(
        self,
        mock_build_packaging_paths: Mock,
        mock_read_project_version: Mock,
        mock_run_command: Mock,
        mock_prepare_pyinstaller_paths: Mock,
        mock_ensure_packaging_art: Mock,
    ) -> None:
        del mock_read_project_version
        with TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            build_root = project_root / 'build' / 'windows'
            pyinstaller_dist_root = project_root / 'dist' / 'pyinstaller'
            paths = build_windows_artifacts.PackagingPaths(
                project_root=project_root,
                spec_file=project_root / 'packaging' / 'pyinstaller' / 'polyfi-ranked.spec',
                installer_script=project_root / 'packaging' / 'inno' / 'polyfi-ranked.iss',
                app_icon_file=build_root / 'polyfi-ranked.ico',
                setup_icon_file=build_root / 'polyfi-ranked-setup.ico',
                wizard_image_file=build_root / 'polyfi-ranked-wizard.png',
                wizard_small_image_file=build_root / 'polyfi-ranked-wizard-small.png',
                pyinstaller_dist_root=pyinstaller_dist_root,
                pyinstaller_app_dir=pyinstaller_dist_root / 'polyfi-ranked',
                pyinstaller_work_root=project_root / 'build' / 'pyinstaller',
                installer_output_dir=project_root / 'dist' / 'installer',
            )
            mock_build_packaging_paths.return_value = paths

            def create_bundled_executables(command: list[str], *, cwd: Path) -> None:
                del command, cwd
                paths.pyinstaller_app_dir.mkdir(parents=True)
                (paths.pyinstaller_app_dir / 'polyfi-ranked.exe').write_text('', encoding='utf-8')
                (paths.pyinstaller_app_dir / 'polyfi-ranked-console.exe').write_text('', encoding='utf-8')

            mock_run_command.side_effect = create_bundled_executables

            result = build_windows_artifacts.main(['--skip-installer'])

        self.assertEqual(result, 0)
        mock_ensure_packaging_art.assert_called_once_with(paths, paths.project_root)
        mock_prepare_pyinstaller_paths.assert_called_once_with(paths, clean=True)
        mock_run_command.assert_called_once_with(
            build_windows_artifacts.build_pyinstaller_command(paths),
            cwd=paths.project_root,
        )

    @patch.object(build_windows_artifacts, 'ensure_packaging_art')
    @patch.object(build_windows_artifacts, 'prepare_pyinstaller_paths')
    @patch.object(build_windows_artifacts, 'run_command')
    @patch.object(build_windows_artifacts, 'read_project_version', return_value='1.0.0-dev.6')
    @patch.object(build_windows_artifacts, 'build_packaging_paths')
    def test_main_fails_when_console_executable_is_missing(
        self,
        mock_build_packaging_paths: Mock,
        mock_read_project_version: Mock,
        mock_run_command: Mock,
        mock_prepare_pyinstaller_paths: Mock,
        mock_ensure_packaging_art: Mock,
    ) -> None:
        del mock_read_project_version, mock_prepare_pyinstaller_paths, mock_ensure_packaging_art
        with TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            pyinstaller_dist_root = project_root / 'dist' / 'pyinstaller'
            paths = build_windows_artifacts.PackagingPaths(
                project_root=project_root,
                spec_file=project_root / 'packaging' / 'pyinstaller' / 'polyfi-ranked.spec',
                installer_script=project_root / 'packaging' / 'inno' / 'polyfi-ranked.iss',
                app_icon_file=project_root / 'build' / 'windows' / 'polyfi-ranked.ico',
                setup_icon_file=project_root / 'build' / 'windows' / 'polyfi-ranked-setup.ico',
                wizard_image_file=project_root / 'build' / 'windows' / 'polyfi-ranked-wizard.png',
                wizard_small_image_file=project_root / 'build' / 'windows' / 'polyfi-ranked-wizard-small.png',
                pyinstaller_dist_root=pyinstaller_dist_root,
                pyinstaller_app_dir=pyinstaller_dist_root / 'polyfi-ranked',
                pyinstaller_work_root=project_root / 'build' / 'pyinstaller',
                installer_output_dir=project_root / 'dist' / 'installer',
            )
            mock_build_packaging_paths.return_value = paths

            def create_app_executable_only(command: list[str], *, cwd: Path) -> None:
                del command, cwd
                paths.pyinstaller_app_dir.mkdir(parents=True)
                (paths.pyinstaller_app_dir / 'polyfi-ranked.exe').write_text('', encoding='utf-8')
                # console exe is intentionally absent

            mock_run_command.side_effect = create_app_executable_only

            result = build_windows_artifacts.main(['--skip-installer'])

        self.assertEqual(result, 1)


if __name__ == '__main__':
    unittest.main()
