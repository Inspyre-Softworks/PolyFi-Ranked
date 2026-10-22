"""Exercise the release CLI against real Git history."""

from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/check_release_hygiene.py'
RELEASE_FILES = ['CHANGELOG.md', 'pyproject.toml', 'src/wifi_pref_manager/__init__.py']


class ReleaseValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Release Tests')
        self.git('config', 'user.email', 'release-tests@example.invalid')
        self.write_release('1.0.0-rc.1')
        self.write('src/wifi_pref_manager/app.py', '# original\n')
        self.commit()
        self.base = self.git('rev-parse', 'HEAD').strip()

    def tearDown(self) -> None:
        self.directory.cleanup()

    def git(self, *args: str) -> str:
        return subprocess.run(
            ['git', *args], cwd=self.root, check=True, capture_output=True, text=True,
        ).stdout

    def write(self, path: str, text: str) -> None:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding='utf-8')

    def write_release(self, version: str) -> None:
        self.write('pyproject.toml', f'[tool.poetry]\nversion = "{version}"\n')
        self.write('src/wifi_pref_manager/__init__.py', f"__version__ = '{version}'\n")
        self.write('CHANGELOG.md', f'## [Unreleased]\n\n## [{version}] - 2026-10-22\n\n### Fixed\n\n- A real fix.\n')

    def commit(self) -> None:
        self.git('add', '.')
        self.git('commit', '-qm', 'test change')

    def check(self, expected: int, *args: str) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), *args], cwd=self.root,
            input='', capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)

    def test_existing_bump_covers_followup_and_validates_committed_head(self) -> None:
        self.write_release('1.0.0-rc.2')
        self.commit()
        self.write('src/wifi_pref_manager/app.py', '# followup\n')
        self.commit()
        self.write('src/wifi_pref_manager/__init__.py', 'broken python =\n')
        self.check(0, '--base', self.base, '--head', 'HEAD')

    def test_source_edit_or_deletion_without_release_files_fails(self) -> None:
        self.write('src/wifi_pref_manager/app.py', '# edited\n')
        self.commit()
        self.check(1, '--base', self.base, '--head', 'HEAD')
        (self.root / 'src/wifi_pref_manager/app.py').unlink()
        self.commit()
        self.check(1, '--base', self.base, '--head', 'HEAD')

    def test_test_only_changes_need_no_bump(self) -> None:
        self.write('tests/test_example.py', '# regression\n')
        self.commit()
        self.check(0, '--base', self.base, '--head', 'HEAD')

    def test_unchanged_downgraded_and_equivalent_versions_fail(self) -> None:
        for version in ('1.0.0-rc.1', '1.0.0-dev.99', '1.0.0rc1'):
            with self.subTest(version=version):
                self.write_release(version)
                self.check(1, '--base', self.base, *RELEASE_FILES)

    def test_prerelease_to_stable_is_an_increase(self) -> None:
        self.write_release('1.0.0')
        self.check(0, '--base', self.base, *RELEASE_FILES)

    def test_missing_refs_fail_closed(self) -> None:
        self.write_release('1.0.0-rc.2')
        self.check(1, '--base', 'missing-base', *RELEASE_FILES)
        self.check(1, '--base', self.base, '--head', 'missing-head')

    def test_mismatched_versions_fail(self) -> None:
        self.write('src/wifi_pref_manager/__init__.py', "__version__ = '1.0.0'\n")
        self.check(1, '--metadata-only')

    def test_invalid_missing_empty_and_duplicate_changelog_releases_fail(self) -> None:
        for content in (
            '## [Unreleased]\n',
            '## [Unreleased]\n## [1.0.0-rc.1] - 2026-02-30\n- Fix\n',
            '## [Unreleased]\n## [1.0.0-rc.1] - 2026-10-22\n### Fixed\n',
            '## [Unreleased]\n## [1.0.0-rc.1] - 2026-10-22\n- Fix\n## [1.0.0-rc.1] - 2026-10-21\n- Duplicate\n',
        ):
            with self.subTest(content=content):
                self.write('CHANGELOG.md', content)
                self.check(1, '--metadata-only')

    def test_metadata_only_change_still_requires_release_files(self) -> None:
        self.write_release('1.0.0-rc.2')
        self.check(1, '--base', self.base, 'pyproject.toml')

    def test_tag_validation_and_exact_notes(self) -> None:
        self.check(1, '--metadata-only', '--tag', 'v1.0.0')
        self.check(0, '--metadata-only', '--tag', 'v1.0.0-rc.1', '--notes', 'notes.md')
        self.assertEqual((self.root / 'notes.md').read_text(encoding='utf-8'), '### Fixed\n\n- A real fix.\n')

    def test_invalid_public_versions_fail(self) -> None:
        for version in ('garbage', '1.0.0+local', '1!1.0.0'):
            with self.subTest(version=version):
                self.write_release(version)
                self.check(1, '--metadata-only')
