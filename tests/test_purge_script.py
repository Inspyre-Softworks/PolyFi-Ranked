from __future__ import annotations

from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class PurgeScriptTests(unittest.TestCase):
    def test_purge_script_reuses_record_and_cleanup_helpers(self) -> None:
        content = (PROJECT_ROOT / 'scripts' / 'purge_polyfi.ps1').read_text(encoding='utf-8')

        self.assertIn('install-record.json', content)
        self.assertIn('uninstall_polyfi.ps1', content)
        self.assertIn('manage_windows_path.ps1', content)
        self.assertIn('POLYFI_APPDATA_ROOT', content)
        self.assertIn('PolyFi-DisableWiFi', content)
        self.assertIn('Remove-InstallDirectorySafely', content)

    def test_readme_documents_purge_script(self) -> None:
        content = (PROJECT_ROOT / 'README.md').read_text(encoding='utf-8')

        self.assertIn('purge_polyfi.ps1', content)
        self.assertIn('install-record.json', content)


if __name__ == '__main__':
    unittest.main()
