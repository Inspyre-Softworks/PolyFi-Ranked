from __future__ import annotations

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from wifi_pref_manager.wifi_adapter_tasks import WifiAdapterTaskManager


class WifiAdapterTaskManagerTests(unittest.TestCase):
    def test_are_installed_uses_marker_when_present(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            marker_path = Path(tmp_dir) / 'wifi_adapter_tasks.json'
            marker_path.write_text(
                '{"marker_version":2,"interface_name":"Wi-Fi","installed_by":"PolyFi","status":"installed"}',
                encoding='utf-8',
            )
            manager = WifiAdapterTaskManager(marker_path=marker_path)

            self.assertTrue(manager.are_installed('Wi-Fi'))
            self.assertFalse(manager.are_installed('Ethernet'))

    def test_are_installed_rejects_legacy_marker_without_version(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            marker_path = Path(tmp_dir) / 'wifi_adapter_tasks.json'
            marker_path.write_text(
                '{"interface_name":"Wi-Fi","installed_by":"PolyFi","status":"installed"}',
                encoding='utf-8',
            )
            manager = WifiAdapterTaskManager(marker_path=marker_path)

            self.assertFalse(manager.are_installed('Wi-Fi'))

    def test_are_installed_accepts_utf8_bom_marker(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            marker_path = Path(tmp_dir) / 'wifi_adapter_tasks.json'
            marker_path.write_text(
                '{"marker_version":2,"interface_name":"Wi-Fi","installed_by":"PolyFi","status":"installed"}',
                encoding='utf-8-sig',
            )
            manager = WifiAdapterTaskManager(marker_path=marker_path)

            self.assertTrue(manager.are_installed('Wi-Fi'))

    def test_install_and_wait_succeeds_when_marker_is_written(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            marker_path = Path(tmp_dir) / 'wifi_adapter_tasks.json'
            manager = WifiAdapterTaskManager(marker_path=marker_path)

            def _write_marker() -> None:
                time.sleep(0.2)
                marker_path.write_text(
                    '{"marker_version":2,"interface_name":"Wi-Fi","installed_by":"PolyFi","status":"installed"}',
                    encoding='utf-8',
                )

            with patch.object(manager, 'install', return_value=True):
                writer = threading.Thread(target=_write_marker, daemon=True)
                writer.start()
                self.assertTrue(manager.install_and_wait('Wi-Fi', timeout=2.0))
                writer.join(timeout=1.0)

    def test_uninstall_removes_marker(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            marker_path = Path(tmp_dir) / 'wifi_adapter_tasks.json'
            marker_path.write_text(
                '{"marker_version":2,"interface_name":"Wi-Fi","installed_by":"PolyFi","status":"installed"}',
                encoding='utf-8',
            )
            manager = WifiAdapterTaskManager(marker_path=marker_path)

            with patch.object(manager, '_run_schtasks'):
                manager.uninstall()

            self.assertFalse(marker_path.exists())

    def test_install_script_uses_interactive_highest_principal(self) -> None:
        manager = WifiAdapterTaskManager(marker_path=Path('C:/Temp/wifi_adapter_tasks.json'))

        script = manager._build_install_script_text('Wi-Fi')

        self.assertIn('-LogonType Interactive -RunLevel Highest', script)
        self.assertIn('marker_version = 2', script)
        self.assertIn('principal_mode = "interactive-highest"', script)


if __name__ == '__main__':
    unittest.main()
