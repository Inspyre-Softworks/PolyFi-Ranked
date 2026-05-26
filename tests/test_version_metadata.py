from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import re
import sys
import tomllib
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from wifi_pref_manager import __version__
from wifi_pref_manager.app import Application


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class VersionMetadataTests(unittest.TestCase):
    def test_pyproject_version_matches_package_version(self) -> None:
        pyproject = tomllib.loads((PROJECT_ROOT / 'pyproject.toml').read_text(encoding='utf-8'))

        self.assertEqual(pyproject['tool']['poetry']['version'], __version__)

    def test_changelog_contains_current_release_heading(self) -> None:
        content = (PROJECT_ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
        heading_pattern = re.compile(
            rf'^## \[{re.escape(__version__)}\] - \d{{4}}-\d{{2}}-\d{{2}}$',
            re.MULTILINE,
        )

        self.assertRegex(content, heading_pattern)
        self.assertIn('## [Unreleased]', content)

    def test_bug_report_template_has_version_field_with_example(self) -> None:
        content = (PROJECT_ROOT / '.github' / 'ISSUE_TEMPLATE' / 'bug_report.yml').read_text(encoding='utf-8')

        self.assertIn('id: version', content)
        self.assertRegex(
            content,
            re.compile(
                r'- type: input\s*\n'
                r'\s+id: version\s*\n'
                r'\s+attributes:\s*\n'
                r'(?:\s+.*\n)*?'
                r'\s+placeholder: "e\.g\. \d+\.\d+\.\d+(?:-dev\.\d+)?"',
            ),
        )

    def test_cli_version_flag_prints_current_version(self) -> None:
        with patch('wifi_pref_manager.app.SingleInstanceGuard'):
            app = Application()

        stdout = StringIO()
        with redirect_stdout(stdout), self.assertRaises(SystemExit) as exc_info:
            app.argument_parser.parse_args(['--version'])

        self.assertEqual(exc_info.exception.code, 0)
        self.assertEqual(stdout.getvalue().strip(), f'polyfi-ranked {__version__}')


if __name__ == '__main__':
    unittest.main()
