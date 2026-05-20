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
    'sphinx.ext.viewcode',
]
templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'markdown',
}

master_doc = 'index'
autoclass_content = 'both'
autodoc_member_order = 'bysource'
autodoc_preserve_defaults = True
autodoc_typehints = 'description'
autodoc_mock_imports = [
    'pystray',
    'tkinter',
    'tkinter.messagebox',
    'tkinter.ttk',
    'PIL.ImageTk',
    'wifi_pref_manager.single_instance',
]

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
