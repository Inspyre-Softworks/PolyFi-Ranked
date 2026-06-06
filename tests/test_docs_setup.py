from __future__ import annotations

from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DocumentationSetupTests(unittest.TestCase):
    @staticmethod
    def _top_level_block(content: str, key: str) -> list[str]:
        lines = content.splitlines()
        for index, line in enumerate(lines):
            if line == f'{key}:':
                block: list[str] = []
                for child in lines[index + 1:]:
                    if child and not child.startswith(' '):
                        break
                    block.append(child)
                return block
        return []

    def test_pyproject_has_docs_group_dependencies(self) -> None:
        content = (PROJECT_ROOT / 'pyproject.toml').read_text(encoding='utf-8')

        self.assertIn('[tool.poetry.group.docs.dependencies]', content)
        self.assertIn('sphinx = ">=7.4,<9.0"', content)
        self.assertIn('sphinx-rtd-theme = ">=2,<4"', content)
        self.assertIn('myst-parser = ">=3.0,<5.0"', content)

    def test_readthedocs_build_uses_poetry_docs_group(self) -> None:
        content = (PROJECT_ROOT / '.readthedocs.yaml').read_text(encoding='utf-8')

        self.assertIn('poetry install --with docs --no-interaction', content)
        self.assertIn('configuration: docs/conf.py', content)
        self.assertIn('fail_on_warning: true', content)

    def test_sphinx_conf_enables_markdown_and_autodoc(self) -> None:
        content = (PROJECT_ROOT / 'docs' / 'conf.py').read_text(encoding='utf-8')

        self.assertIn("'myst_parser'", content)
        self.assertIn("'sphinx.ext.autodoc'", content)
        self.assertIn("'sphinx.ext.viewcode'", content)
        self.assertIn("'easy_exit_calls'", content)
        self.assertIn("master_doc = 'index'", content)

    def test_ci_builds_docs_with_warnings_as_errors(self) -> None:
        content = (PROJECT_ROOT / '.github' / 'workflows' / 'ci.yml').read_text(encoding='utf-8')

        permissions_block = self._top_level_block(content, 'permissions')
        jobs_block = self._top_level_block(content, 'jobs')

        self.assertIn('  contents: read', permissions_block)
        self.assertIn('  docs:', jobs_block)
        self.assertIn('poetry install', content)
        self.assertIn('--with docs', content)
        self.assertIn('sphinx-build -W', content)

    def test_index_includes_api_reference_page(self) -> None:
        content = (PROJECT_ROOT / 'docs' / 'index.rst').read_text(encoding='utf-8')

        self.assertIn('api-reference', content)

    def test_api_reference_documents_runtime_modules(self) -> None:
        content = (PROJECT_ROOT / 'docs' / 'api-reference.rst').read_text(encoding='utf-8')

        self.assertIn('.. automodule:: wifi_pref_manager.service', content)
        self.assertIn('.. automodule:: wifi_pref_manager.windows_shell', content)
        self.assertIn('.. automodule:: wifi_pref_manager.wifi_adapter_tasks', content)


if __name__ == '__main__':
    unittest.main()
