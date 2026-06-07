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
    'sphinx.ext.viewcode',
]
templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'markdown',
}

master_doc = 'index'
autosectionlabel_prefix_document = True
autoclass_content = 'both'
autodoc_member_order = 'bysource'
autodoc_preserve_defaults = True
autodoc_typehints = 'none'
autodoc_mock_imports = [
    'pystray',
    'tkinter',
    'tkinter.messagebox',
    'tkinter.ttk',
    'PIL.ImageTk',
    'easy_exit_calls',
    'easy_exit_calls.classes',
    'inspy_logger',
    'wifi_pref_manager.single_instance',
]
suppress_warnings = [
    'autosectionlabel',
]
html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
html_js_files = ['copy-code-button.js']
