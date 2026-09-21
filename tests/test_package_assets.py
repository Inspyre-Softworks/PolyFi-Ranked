from __future__ import annotations

import json
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
        splash_definition_path = splash_dir / 'splash.json'
        self.assertTrue(splash_definition_path.is_file())

        splash_definition = json.loads(splash_definition_path.read_text(encoding='utf-8'))
        for layer in splash_definition.get('layers', []):
            asset_path = layer.get('path')
            if not isinstance(asset_path, str):
                continue
            self.assertTrue(
                (splash_dir / asset_path).is_file(),
                msg=f'Missing splash asset referenced by splash.json: {asset_path}',
            )

    def test_poetry_includes_assets_in_wheel_and_sdist(self) -> None:
        pyproject = tomllib.loads((PROJECT_ROOT / 'pyproject.toml').read_text(encoding='utf-8'))

        self.assertIn(ASSETS_INCLUDE, pyproject['tool']['poetry'].get('include', []))

    def test_pyinstaller_spec_collects_runtime_assets(self) -> None:
        spec_path = PROJECT_ROOT / 'packaging' / 'pyinstaller' / 'polyfi-ranked.spec'
        spec_content = spec_path.read_text(encoding='utf-8')

        self.assertIn(
            "collect_data_files('wifi_pref_manager', includes=['assets/**/*'])",
            spec_content,
        )


if __name__ == '__main__':
    unittest.main()
