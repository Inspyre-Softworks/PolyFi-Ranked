from __future__ import annotations

from pathlib import Path
import tomllib
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSETS_INCLUDE = {
    'path': 'src/wifi_pref_manager/assets/**/*',
    'format': ['sdist', 'wheel'],
}


class PackageAssetsTests(unittest.TestCase):
    def test_assets_directory_exists_for_runtime_package_data(self) -> None:
        assets_dir = PROJECT_ROOT / 'src' / 'wifi_pref_manager' / 'assets'
        splash_dir = assets_dir / 'splashes' / 'intro'

        self.assertTrue(assets_dir.is_dir())
        self.assertTrue((assets_dir / 'README.md').is_file())
        self.assertTrue((splash_dir / 'splash.json').is_file())
        self.assertTrue((splash_dir / 'transparent_splash.webp').is_file())
        self.assertTrue((splash_dir / 'glow.png').is_file())

    def test_poetry_includes_assets_in_wheel_and_sdist(self) -> None:
        pyproject = tomllib.loads((PROJECT_ROOT / 'pyproject.toml').read_text(encoding='utf-8'))

        self.assertIn(ASSETS_INCLUDE, pyproject['tool']['poetry'].get('include', []))


if __name__ == '__main__':
    unittest.main()
