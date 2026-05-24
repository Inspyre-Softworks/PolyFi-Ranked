from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import unittest


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


if __name__ == '__main__':
    unittest.main()
