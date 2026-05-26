from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import subprocess
import unittest
import unittest.mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / 'scripts' / 'check_release_hygiene.py'

_SPEC = spec_from_file_location('check_release_hygiene', SCRIPT_PATH)
if _SPEC is None or _SPEC.loader is None:  # pragma: no cover
    raise RuntimeError(f'Could not load {SCRIPT_PATH}')
check_release_hygiene = module_from_spec(_SPEC)
_SPEC.loader.exec_module(check_release_hygiene)


class ReleaseHygieneTests(unittest.TestCase):
    def test_docs_only_changes_do_not_trigger_release_requirement(self) -> None:
        changed_files = [
            'README.md',
            'docs/configuration.rst',
            '.github/pull_request_template.md',
        ]

        self.assertEqual(check_release_hygiene.release_hygiene_triggers(changed_files), [])

    def test_code_changes_trigger_release_requirement(self) -> None:
        changed_files = [
            'src/wifi_pref_manager/app.py',
            'README.md',
        ]

        self.assertEqual(
            check_release_hygiene.release_hygiene_triggers(changed_files),
            ['src/wifi_pref_manager/app.py'],
        )
        self.assertEqual(
            check_release_hygiene.missing_release_files(changed_files),
            [
                'CHANGELOG.md',
                'pyproject.toml',
                'src/wifi_pref_manager/__init__.py',
            ],
        )

    def test_packaging_changes_trigger_release_requirement(self) -> None:
        changed_files = [
            'scripts/build_windows_artifacts.py',
            'packaging/inno/polyfi-ranked.iss',
        ]

        self.assertEqual(
            check_release_hygiene.release_hygiene_triggers(changed_files),
            changed_files,
        )

    def test_workflow_changes_trigger_release_requirement(self) -> None:
        changed_files = [
            '.github/workflows/ci.yml',
            '.github/workflows/release.yml',
        ]

        self.assertEqual(
            check_release_hygiene.release_hygiene_triggers(changed_files),
            changed_files,
        )

    def test_release_files_satisfy_requirement_for_code_changes(self) -> None:
        changed_files = [
            'src/wifi_pref_manager/app.py',
            'CHANGELOG.md',
            'pyproject.toml',
            'src/wifi_pref_manager/__init__.py',
        ]

        self.assertEqual(check_release_hygiene.missing_release_files(changed_files), [])

    def test_version_bump_requires_both_version_files(self) -> None:
        changed_files = [
            'src/wifi_pref_manager/app.py',
            'CHANGELOG.md',
            'pyproject.toml',
        ]

        self.assertEqual(
            check_release_hygiene.missing_release_files(changed_files),
            ['src/wifi_pref_manager/__init__.py'],
        )

    def test_existing_pr_bump_allows_later_release_sensitive_changes(self) -> None:
        changed_files = [
            '.github/workflows/auto-release.yml',
            'CHANGELOG.md',
            'pyproject.toml',
            'src/wifi_pref_manager/__init__.py',
            'docs/building-windows-installer.rst',
        ]

        self.assertEqual(check_release_hygiene.missing_release_files(changed_files), [])


class VersionActuallyChangedTests(unittest.TestCase):
    _OLD_TOML = '[tool.poetry]\nversion = "1.0.0"\n'
    _NEW_TOML_SAME = '[tool.poetry]\nversion = "1.0.0"\n'
    _NEW_TOML_BUMPED = '[tool.poetry]\nversion = "1.0.1"\n'

    def _mock_git_result(self, stdout: str) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout)

    def test_returns_true_when_git_fails(self) -> None:
        with unittest.mock.patch(
            'subprocess.run',
            side_effect=subprocess.CalledProcessError(128, 'git'),
        ):
            self.assertTrue(check_release_hygiene.version_actually_changed('abc123'))

    def test_returns_true_when_pyproject_missing_at_base(self) -> None:
        # git show returns non-zero (file didn't exist at base ref)
        with unittest.mock.patch(
            'subprocess.run',
            side_effect=subprocess.CalledProcessError(128, 'git show'),
        ):
            self.assertTrue(check_release_hygiene.version_actually_changed('abc123'))

    def test_returns_false_when_version_unchanged(self) -> None:
        with unittest.mock.patch(
            'subprocess.run',
            return_value=self._mock_git_result(self._OLD_TOML),
        ), unittest.mock.patch.object(
            Path, 'read_text', return_value=self._NEW_TOML_SAME
        ):
            self.assertFalse(check_release_hygiene.version_actually_changed('abc123'))

    def test_returns_true_when_version_incremented(self) -> None:
        with unittest.mock.patch(
            'subprocess.run',
            return_value=self._mock_git_result(self._OLD_TOML),
        ), unittest.mock.patch.object(
            Path, 'read_text', return_value=self._NEW_TOML_BUMPED
        ):
            self.assertTrue(check_release_hygiene.version_actually_changed('abc123'))

    def test_returns_true_when_head_pyproject_unreadable(self) -> None:
        with unittest.mock.patch(
            'subprocess.run',
            return_value=self._mock_git_result(self._OLD_TOML),
        ), unittest.mock.patch.object(
            Path, 'read_text', side_effect=OSError('not found')
        ):
            self.assertTrue(check_release_hygiene.version_actually_changed('abc123'))


if __name__ == '__main__':
    unittest.main()
