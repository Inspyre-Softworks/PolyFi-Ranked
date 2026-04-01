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

extensions = []
templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
