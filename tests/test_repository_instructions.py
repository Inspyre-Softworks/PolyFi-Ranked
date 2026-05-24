from __future__ import annotations

from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class RepositoryInstructionTests(unittest.TestCase):
    def test_contributing_documents_poetry_dev_install_and_pytest(self) -> None:
        content = (PROJECT_ROOT / 'CONTRIBUTING.md').read_text(encoding='utf-8')

        self.assertIn('poetry install --with dev --no-interaction', content)
        self.assertIn('poetry run pytest', content)

    def test_ai_instruction_files_require_poetry_workflow(self) -> None:
        instruction_files = [
            PROJECT_ROOT / 'AGENTS.md',
            PROJECT_ROOT / '.github' / 'copilot-instructions.md',
            PROJECT_ROOT / '.zencoder' / 'rules' / 'repo.md',
        ]

        for path in instruction_files:
            content = path.read_text(encoding='utf-8')
            self.assertIn('poetry install --with dev --no-interaction', content, msg=str(path))
            self.assertIn('poetry run pytest', content, msg=str(path))

    def test_release_hygiene_rule_is_documented_across_repo_workflow_files(self) -> None:
        instruction_files = [
            PROJECT_ROOT / 'CONTRIBUTING.md',
            PROJECT_ROOT / 'AGENTS.md',
            PROJECT_ROOT / '.github' / 'copilot-instructions.md',
            PROJECT_ROOT / '.zencoder' / 'rules' / 'repo.md',
            PROJECT_ROOT / '.github' / 'pull_request_template.md',
        ]

        for path in instruction_files:
            content = path.read_text(encoding='utf-8')
            self.assertIn('CHANGELOG.md', content, msg=str(path))
            self.assertIn('pyproject.toml', content, msg=str(path))
            self.assertIn('src/wifi_pref_manager/__init__.py', content, msg=str(path))

    def test_windows_packaging_workflow_is_documented_for_contributors_and_agents(self) -> None:
        instruction_files = [
            PROJECT_ROOT / 'CONTRIBUTING.md',
            PROJECT_ROOT / 'AGENTS.md',
            PROJECT_ROOT / '.github' / 'copilot-instructions.md',
            PROJECT_ROOT / '.zencoder' / 'rules' / 'repo.md',
        ]

        for path in instruction_files:
            content = path.read_text(encoding='utf-8')
            self.assertIn('poetry install --with packaging --no-interaction', content, msg=str(path))
            self.assertIn('build_windows_installer.ps1', content, msg=str(path))

    def test_pull_request_template_keeps_test_and_docs_checklist(self) -> None:
        content = (PROJECT_ROOT / '.github' / 'pull_request_template.md').read_text(encoding='utf-8')

        self.assertIn('I ran `poetry run pytest`', content)
        self.assertIn('I updated documentation where applicable', content)
        self.assertIn('I updated `CHANGELOG.md` and bumped the version', content)

    def test_release_hygiene_workflows_exist(self) -> None:
        workflow_dir = PROJECT_ROOT / '.github' / 'workflows'

        self.assertTrue((workflow_dir / 'ci.yml').exists())
        self.assertTrue((workflow_dir / 'release-hygiene.yml').exists())
        self.assertTrue((workflow_dir / 'release.yml').exists())
        self.assertIn(
            'actions/upload-artifact',
            (workflow_dir / 'ci.yml').read_text(encoding='utf-8'),
        )
        self.assertIn(
            'scripts/check_release_hygiene.py',
            (workflow_dir / 'release-hygiene.yml').read_text(encoding='utf-8'),
        )
        release_content = (workflow_dir / 'release.yml').read_text(encoding='utf-8')
        self.assertIn('pypa/gh-action-pypi-publish', release_content)
        self.assertIn('https://test.pypi.org/legacy/', release_content)
        self.assertIn('softprops/action-gh-release', release_content)

    def test_auto_release_workflow_exists_and_is_well_formed(self) -> None:
        workflow_dir = PROJECT_ROOT / '.github' / 'workflows'
        auto_release = workflow_dir / 'auto-release.yml'

        self.assertTrue(auto_release.exists(), 'auto-release.yml is missing')
        content = auto_release.read_text(encoding='utf-8')

        # Must be triggered by push to main.
        self.assertIn('branches:', content)
        self.assertIn('- main', content)

        # Must detect version bumps by reading pyproject.toml.
        self.assertIn('pyproject.toml', content)

        # Must guard against duplicate tags.
        self.assertIn('ls-remote', content)

        # Must publish to both TestPyPI and PyPI.
        self.assertIn('pypa/gh-action-pypi-publish', content)
        self.assertIn('https://test.pypi.org/legacy/', content)

        # Must create the GitHub Release.
        self.assertIn('softprops/action-gh-release', content)

        # Must also build and attach Windows release artifacts.
        self.assertIn('build-windows-artifacts', content)
        self.assertIn('build_windows_installer.ps1', content)
        self.assertIn('dist/installer/*.exe', content)
        self.assertIn('dist/installer/*.zip', content)
        self.assertIn('merge-multiple: true', content)

    def test_release_automation_is_documented_for_contributors_and_agents(self) -> None:
        instruction_files = [
            PROJECT_ROOT / 'README.md',
            PROJECT_ROOT / 'CONTRIBUTING.md',
            PROJECT_ROOT / 'AGENTS.md',
            PROJECT_ROOT / '.github' / 'copilot-instructions.md',
            PROJECT_ROOT / '.zencoder' / 'rules' / 'repo.md',
        ]

        for path in instruction_files:
            content = path.read_text(encoding='utf-8')
            self.assertIn('GitHub Release', content, msg=str(path))
            self.assertIn('TestPyPI', content, msg=str(path))
            self.assertIn('PyPI', content, msg=str(path))


if __name__ == '__main__':
    unittest.main()
