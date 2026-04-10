from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from wifi_pref_manager.icon_assets import create_app_icon_image


class IconAssetTests(unittest.TestCase):
    def test_tray_icon_uses_transparent_background(self) -> None:
        image = create_app_icon_image(64)

        self.assertEqual(image.getpixel((0, 0))[3], 0)

    def test_tray_icon_has_visible_colored_body(self) -> None:
        image = create_app_icon_image(64)

        center_pixel = image.getpixel((16, 16))
        self.assertGreater(center_pixel[3], 0)
        self.assertNotEqual(center_pixel[:3], (0, 0, 0))


if __name__ == '__main__':
    unittest.main()
