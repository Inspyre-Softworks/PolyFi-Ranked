from __future__ import annotations

from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DocumentationSetupTests(unittest.TestCase):
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
        self.assertIn("master_doc = 'index'", content)

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
