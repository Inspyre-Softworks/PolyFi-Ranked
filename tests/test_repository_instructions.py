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

    def test_pull_request_template_keeps_test_and_docs_checklist(self) -> None:
        content = (PROJECT_ROOT / '.github' / 'pull_request_template.md').read_text(encoding='utf-8')

        self.assertIn('I ran `poetry run pytest`', content)
        self.assertIn('I updated documentation where applicable', content)


if __name__ == '__main__':
    unittest.main()
