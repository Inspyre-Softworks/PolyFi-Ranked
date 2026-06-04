from __future__ import annotations

from io import BytesIO
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from wifi_pref_manager.updates import (
    UpdateAsset,
    UpdateInfo,
    UpdateManager,
    choose_latest_update,
    is_newer_version,
    select_windows_installer_asset,
)


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._stream = BytesIO(payload)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)


class UpdateTests(unittest.TestCase):
    def test_version_comparison_handles_dev_versions(self) -> None:
        self.assertTrue(is_newer_version('1.0.0-dev.18', '1.0.0-dev.17'))
        self.assertTrue(is_newer_version('1.0.0', '1.0.0-dev.18'))
        self.assertFalse(is_newer_version('1.0.0-dev.17', '1.0.0-dev.17'))

    def test_select_windows_installer_prefers_setup_exe(self) -> None:
        asset = select_windows_installer_asset(
            [
                {
                    'name': 'polyfi-ranked-app-1.0.0-windows-x64.zip',
                    'browser_download_url': 'https://example.invalid/app.zip',
                },
                {
                    'name': 'polyfi-ranked-setup-1.0.0.exe',
                    'browser_download_url': 'https://example.invalid/setup.exe',
                },
            ]
        )

        self.assertIsNotNone(asset)
        assert asset is not None
        self.assertEqual(asset.name, 'polyfi-ranked-setup-1.0.0.exe')

    def test_choose_latest_update_ignores_drafts_and_requires_newer_version(self) -> None:
        update = choose_latest_update(
            [
                {'tag_name': 'v9.9.9', 'draft': True},
                {
                    'tag_name': 'v1.0.0-dev.18',
                    'html_url': 'https://example.invalid/releases/v1.0.0-dev.18',
                    'assets': [],
                },
                {
                    'tag_name': 'v1.0.0-dev.17',
                    'html_url': 'https://example.invalid/releases/v1.0.0-dev.17',
                    'assets': [],
                },
            ],
            '1.0.0-dev.17',
        )

        self.assertIsNotNone(update)
        assert update is not None
        self.assertEqual(update.version, '1.0.0-dev.18')

    @patch('wifi_pref_manager.updates.urlopen')
    def test_download_installer_writes_update_file(self, mock_urlopen: Mock) -> None:
        with TemporaryDirectory() as tmp_dir:
            paths = Mock()
            paths.local_data_dir = Path(tmp_dir)
            paths.ensure_directories.return_value = None
            mock_urlopen.return_value = _FakeResponse(b'installer-bytes')
            manager = UpdateManager(paths=paths)
            update = UpdateInfo(
                version='1.0.0-dev.18',
                tag_name='v1.0.0-dev.18',
                release_url='https://example.invalid/release',
                installer_asset=UpdateAsset(
                    name='polyfi-ranked-setup-1.0.0-dev.18.exe',
                    download_url='https://example.invalid/setup.exe',
                ),
            )

            destination = manager.download_installer(update)

            self.assertEqual(destination.read_bytes(), b'installer-bytes')
            self.assertEqual(destination.name, 'polyfi-ranked-setup-1.0.0-dev.18.exe')

    @patch('wifi_pref_manager.updates.subprocess.Popen')
    def test_launch_installer_uses_downloaded_file(self, mock_popen: Mock) -> None:
        with TemporaryDirectory() as tmp_dir:
            installer_path = Path(tmp_dir) / 'polyfi-ranked-setup.exe'
            installer_path.write_text('', encoding='utf-8')

            UpdateManager.launch_installer(installer_path)

            mock_popen.assert_called_once_with(
                [str(installer_path)],
                cwd=str(installer_path.parent),
                close_fds=True,
            )


if __name__ == '__main__':
    unittest.main()
