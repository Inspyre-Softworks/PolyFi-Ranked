from __future__ import annotations

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from wifi_pref_manager.config import ConfigError, ConfigLoader, save_config
from wifi_pref_manager.models import AppConfig, WiFiProfilePreference


class ConfigRoundTripTests(unittest.TestCase):
    def test_save_config_round_trips_special_characters(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / 'config.toml'
            config = AppConfig(
                preferred_networks=[
                    WiFiProfilePreference("O'Reilly WiFi", auto_switch=False, min_db=-70),
                    WiFiProfilePreference(r'Back\Slash', auto_switch=True, min_db=None),
                ],
                interface_name='Wi-Fi',
                scan_interval=5,
                connect_timeout=9,
                sync_profile_order_on_start=False,
                log_level='DEBUG',
                log_file=str(Path(tmp_dir) / 'logs' / 'polyfi.log'),
                start_minimized_to_tray=True,
                auto_disable_wifi_on_ethernet=False,
                show_wifi_disabled_dialog=False,
                enable_speed_tests=True,
                speed_test_on_new_connection=False,
                speed_test_interval=12,
                save_speed_test_history=True,
                speed_test_history_file=str(Path(tmp_dir) / 'history.jsonl'),
            )

            save_config(config, config_path)
            loaded = ConfigLoader(config_path).load()

            self.assertEqual(loaded.preferred_networks, config.preferred_networks)
            self.assertEqual(loaded.interface_name, config.interface_name)
            self.assertEqual(loaded.scan_interval, config.scan_interval)
            self.assertEqual(loaded.connect_timeout, config.connect_timeout)
            self.assertEqual(loaded.sync_profile_order_on_start, config.sync_profile_order_on_start)
            self.assertEqual(loaded.log_level, config.log_level)
            self.assertEqual(loaded.log_file, config.log_file)
            self.assertEqual(loaded.start_minimized_to_tray, config.start_minimized_to_tray)
            self.assertEqual(loaded.auto_disable_wifi_on_ethernet, config.auto_disable_wifi_on_ethernet)
            self.assertEqual(loaded.show_wifi_disabled_dialog, config.show_wifi_disabled_dialog)
            self.assertEqual(loaded.enable_speed_tests, config.enable_speed_tests)
            self.assertEqual(loaded.speed_test_on_new_connection, config.speed_test_on_new_connection)
            self.assertEqual(loaded.speed_test_interval, config.speed_test_interval)
            self.assertEqual(loaded.save_speed_test_history, config.save_speed_test_history)
            self.assertEqual(loaded.speed_test_history_file, config.speed_test_history_file)

    def test_invalid_toml_raises_config_error(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / 'config.toml'
            config_path.write_text("[general]\nscan_interval = [\n", encoding='utf-8')

            with self.assertRaises(ConfigError):
                ConfigLoader(config_path).load()

    def test_string_boolean_values_are_parsed_explicitly(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / 'config.toml'
            config_path.write_text(
                "\n".join(
                    [
                        "[general]",
                        'auto_disable_wifi_on_ethernet = "false"',
                        "",
                        "[[networks]]",
                        'ssid = "Example"',
                        'auto_switch = "true"',
                        "",
                    ]
                ),
                encoding='utf-8',
            )

            loaded = ConfigLoader(config_path).load()

            self.assertFalse(loaded.auto_disable_wifi_on_ethernet)
            self.assertTrue(loaded.preferred_networks[0].auto_switch)


if __name__ == '__main__':
    unittest.main()
