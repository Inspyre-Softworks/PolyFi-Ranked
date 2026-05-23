from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from wifi_pref_manager.icon_assets import (
    INSTALLER_SMALL_IMAGE_SIZE,
    INSTALLER_WIZARD_IMAGE_SIZE,
    create_app_icon_image,
    create_installer_small_image,
    create_installer_wizard_image,
)


class IconAssetTests(unittest.TestCase):
    def test_tray_icon_uses_transparent_background(self) -> None:
        image = create_app_icon_image(64)

        self.assertEqual(image.getpixel((0, 0))[3], 0)

    def test_tray_icon_has_visible_colored_body(self) -> None:
        image = create_app_icon_image(64)

        center_pixel = image.getpixel((16, 16))
        self.assertGreater(center_pixel[3], 0)
        self.assertNotEqual(center_pixel[:3], (0, 0, 0))

    def test_installer_wizard_image_uses_expected_size(self) -> None:
        image = create_installer_wizard_image()

        self.assertEqual(image.size, INSTALLER_WIZARD_IMAGE_SIZE)

    def test_installer_small_image_uses_expected_size(self) -> None:
        image = create_installer_small_image()

        self.assertEqual(image.size, INSTALLER_SMALL_IMAGE_SIZE)

    def test_installer_art_uses_visible_project_branding(self) -> None:
        image = create_installer_wizard_image()

        sample_pixel = image.getpixel((image.size[0] // 2, 72))
        self.assertGreater(sample_pixel[3], 0)
        self.assertNotEqual(sample_pixel[:3], (255, 255, 255))


if __name__ == '__main__':
    unittest.main()
