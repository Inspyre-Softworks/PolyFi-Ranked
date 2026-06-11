from __future__ import annotations

from contextlib import AbstractContextManager
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

import wifi_pref_manager.subprocess_utils as subprocess_utils_module
from wifi_pref_manager.subprocess_utils import hidden_subprocess_kwargs


class HiddenSubprocessKwargsTests(unittest.TestCase):
    """Tests for :func:`~wifi_pref_manager.subprocess_utils.hidden_subprocess_kwargs`."""

    def _patch_subprocess(
        self,
        *,
        create_no_window: int = 0,
        startupinfo_type: type[object] | None = None,
        startf_flag: int = 0,
    ) -> tuple[AbstractContextManager[object], AbstractContextManager[object], AbstractContextManager[object]]:
        """Return a context manager stack that patches the subprocess attrs used by the helper."""
        return (
            patch.object(subprocess_utils_module.subprocess, 'CREATE_NO_WINDOW', create_no_window, create=True),
            patch.object(subprocess_utils_module.subprocess, 'STARTUPINFO', startupinfo_type, create=True),
            patch.object(subprocess_utils_module.subprocess, 'STARTF_USESHOWWINDOW', startf_flag, create=True),
        )

    def test_returns_empty_dict_on_non_windows_platform(self) -> None:
        """All attributes absent/zero → empty kwargs dict."""
        cnw, si, sfw = self._patch_subprocess(create_no_window=0, startupinfo_type=None, startf_flag=0)
        with cnw, si, sfw:
            result = hidden_subprocess_kwargs()

        self.assertEqual(result, {})

    def test_includes_creationflags_when_create_no_window_nonzero(self) -> None:
        cnw, si, sfw = self._patch_subprocess(create_no_window=0x08000000, startupinfo_type=None, startf_flag=0)
        with cnw, si, sfw:
            result = hidden_subprocess_kwargs()

        self.assertIn('creationflags', result)
        self.assertEqual(result['creationflags'], 0x08000000)
        self.assertNotIn('startupinfo', result)

    def test_includes_startupinfo_when_both_attributes_present(self) -> None:
        class _FakeStartupInfo:
            def __init__(self) -> None:
                self.dwFlags = 0
                self.wShowWindow = 1

        cnw, si, sfw = self._patch_subprocess(
            create_no_window=0x08000000,
            startupinfo_type=_FakeStartupInfo,
            startf_flag=0x01,
        )
        with cnw, si, sfw:
            result = hidden_subprocess_kwargs()

        self.assertIn('startupinfo', result)
        startupinfo = result['startupinfo']
        self.assertIsInstance(startupinfo, _FakeStartupInfo)
        # dwFlags should have STARTF_USESHOWWINDOW ORed in
        self.assertEqual(startupinfo.dwFlags, 0x01)
        # wShowWindow should be set to 0 (hidden)
        self.assertEqual(startupinfo.wShowWindow, 0)

    def test_omits_startupinfo_when_startf_flag_is_zero(self) -> None:
        class _FakeStartupInfo:
            def __init__(self) -> None:
                self.dwFlags = 0
                self.wShowWindow = 1

        cnw, si, sfw = self._patch_subprocess(
            create_no_window=0x08000000,
            startupinfo_type=_FakeStartupInfo,
            startf_flag=0,
        )
        with cnw, si, sfw:
            result = hidden_subprocess_kwargs()

        self.assertNotIn('startupinfo', result)
        self.assertIn('creationflags', result)

    def test_omits_startupinfo_when_startupinfo_type_is_none(self) -> None:
        cnw, si, sfw = self._patch_subprocess(
            create_no_window=0x08000000,
            startupinfo_type=None,
            startf_flag=0x01,
        )
        with cnw, si, sfw:
            result = hidden_subprocess_kwargs()

        self.assertNotIn('startupinfo', result)
        self.assertIn('creationflags', result)

    def test_result_is_a_dict(self) -> None:
        result = hidden_subprocess_kwargs()
        self.assertIsInstance(result, dict)


if __name__ == '__main__':
    unittest.main()
