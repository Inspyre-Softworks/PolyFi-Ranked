"""
Sphinx configuration for PolyFi: Ranked.
"""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _patch_sphinx_extensions_for_current_sphinx() -> None:
    from sphinx.application import Sphinx
    import sphinx.domains.python as sphinx_python_domain
    import sphinx_autodoc_annotation

    if not hasattr(Sphinx, 'debug2'):
        Sphinx.debug2 = lambda self, *args, **kwargs: None

    original_python_domain_warning = sphinx_python_domain.logger.warning

    def python_domain_warning(message, *args, **kwargs):
        if 'duplicate object description of %s' in str(message):
            return
        original_python_domain_warning(message, *args, **kwargs)

    sphinx_python_domain.logger.warning = python_domain_warning

    def add_annotation_content(app, what, name, obj, options, lines):
        if what in {'function', 'method'}:
            sphinx_autodoc_annotation.add_annotation_content(obj, lines)

    def setup(app):
        app.connect('autodoc-process-docstring', add_annotation_content)
        return {'parallel_read_safe': True, 'parallel_write_safe': True}

    sphinx_autodoc_annotation.setup = setup


_patch_sphinx_extensions_for_current_sphinx()

project = 'PolyFi: Ranked'
author = 'Inspyre Softworks'
copyright = '2026, Inspyre Softworks'

extensions = [
    'myst_parser',
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.coverage',
    'sphinx_rtd_theme',
    'sphinx.ext.autosectionlabel',
    'sphinx.ext.autosummary',
    'sphinx.ext.viewcode',
    'sphinxcontrib.argdoc',
    'autoclasstoc',
    'sphinx_autodoc_annotation',
]
autosummary_generate = True
templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'markdown',
}

master_doc = 'index'
autosectionlabel_prefix_document = True
argdoc_main_func = '_polyfi_ranked_argdoc_entrypoint'
autoclass_content = 'both'
autodoc_member_order = 'bysource'
autodoc_preserve_defaults = True
autodoc_typehints = 'none'
autodoc_default_options = {
    'members': True,
    'special-members': True,
    'undoc-members': True,
    'inherited-members': True,
    'exclude-members': '__weakref__',
    'private-members': True,
}
autodoc_mock_imports = [
    'pystray',
    'tkinter',
    'tkinter.messagebox',
    'tkinter.ttk',
    'PIL.ImageTk',
    'wifi_pref_manager.single_instance',
]
suppress_warnings = [
    'autosectionlabel',
]
html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
