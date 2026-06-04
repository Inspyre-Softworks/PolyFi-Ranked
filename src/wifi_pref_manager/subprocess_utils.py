"""
Author:
    Inspyre Softworks

Project:
    PolyFi: Ranked

File:
    subprocess_utils.py

Description:
    Shared subprocess utility helpers for Windows-specific process creation.

Functions:
    hidden_subprocess_kwargs:
        Return Windows subprocess kwargs that suppress console windows.

Dependencies:
    subprocess
"""

from __future__ import annotations

import subprocess


def hidden_subprocess_kwargs() -> dict[str, object]:
    """
    Return Windows-specific subprocess flags that suppress console windows.

    On platforms where the relevant ``subprocess`` attributes are not present
    (e.g. Linux/macOS), an empty dict is returned so callers remain
    cross-platform.

    Returns:
        Keyword arguments safe to splat into ``subprocess.run`` or
        ``subprocess.Popen``.
    """
    kwargs: dict[str, object] = {}

    create_no_window = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    if create_no_window:
        kwargs['creationflags'] = create_no_window

    startupinfo_type = getattr(subprocess, 'STARTUPINFO', None)
    startf_use_showwindow = getattr(subprocess, 'STARTF_USESHOWWINDOW', 0)
    if startupinfo_type is not None and startf_use_showwindow:
        startupinfo = startupinfo_type()
        startupinfo.dwFlags |= startf_use_showwindow
        startupinfo.wShowWindow = 0
        kwargs['startupinfo'] = startupinfo

    return kwargs
