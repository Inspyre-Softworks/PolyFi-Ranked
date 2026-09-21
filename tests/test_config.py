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
                connect_preferred_after_ethernet_disconnect=False,
                ethernet_wifi_mode='disable_adapter',
                show_wifi_disabled_dialog=False,
                add_to_startup_programs=True,
                add_scheduled_logon_task=True,
                show_startup_splash=False,
                splash_image_path=str(Path(tmp_dir) / 'polyfi_ranked_splash.png'),
                splash_fade_in_ms=123,
                splash_hold_ms=456,
                splash_fade_out_ms=789,
                enable_speed_tests=True,
                speed_test_on_new_connection=False,
                speed_test_interval=12,
                save_speed_test_history=True,
                speed_test_history_file=str(Path(tmp_dir) / 'history.jsonl'),
                auto_check_for_updates=False,
                allow_prerelease_updates=True,
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
            self.assertEqual(
                loaded.connect_preferred_after_ethernet_disconnect,
                config.connect_preferred_after_ethernet_disconnect,
            )
            self.assertEqual(loaded.ethernet_wifi_mode, config.ethernet_wifi_mode)
            self.assertEqual(loaded.show_wifi_disabled_dialog, config.show_wifi_disabled_dialog)
            self.assertEqual(loaded.add_to_startup_programs, config.add_to_startup_programs)
            self.assertEqual(loaded.add_scheduled_logon_task, config.add_scheduled_logon_task)
            self.assertEqual(loaded.show_startup_splash, config.show_startup_splash)
            self.assertEqual(loaded.splash_image_path, config.splash_image_path)
            self.assertEqual(loaded.splash_fade_in_ms, config.splash_fade_in_ms)
            self.assertEqual(loaded.splash_hold_ms, config.splash_hold_ms)
            self.assertEqual(loaded.splash_fade_out_ms, config.splash_fade_out_ms)
            self.assertEqual(loaded.enable_speed_tests, config.enable_speed_tests)
            self.assertEqual(loaded.speed_test_on_new_connection, config.speed_test_on_new_connection)
            self.assertEqual(loaded.speed_test_interval, config.speed_test_interval)
            self.assertEqual(loaded.save_speed_test_history, config.save_speed_test_history)
            self.assertEqual(loaded.speed_test_history_file, config.speed_test_history_file)
            self.assertEqual(loaded.auto_check_for_updates, config.auto_check_for_updates)
            self.assertEqual(loaded.allow_prerelease_updates, config.allow_prerelease_updates)
            self.assertIn('[global]', config_path.read_text(encoding='utf-8'))
            self.assertNotIn('[general]', config_path.read_text(encoding='utf-8'))

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

    def test_ethernet_wifi_mode_defaults_when_missing(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / 'config.toml'
            config_path.write_text(
                "\n".join(
                    [
                        "[general]",
                        "",
                        "[[networks]]",
                        'ssid = "Example"',
                        'auto_switch = true',
                        "",
                    ]
                ),
                encoding='utf-8',
            )

            loaded = ConfigLoader(config_path).load()
            self.assertEqual(loaded.ethernet_wifi_mode, 'disconnect_and_disable_autoconnect')

    def test_missing_scheduled_logon_task_setting_is_unmanaged(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / 'config.toml'
            config_path.write_text(
                "\n".join(
                    [
                        "[general]",
                        "",
                        "[[networks]]",
                        'ssid = "Example"',
                        'auto_switch = true',
                        "",
                    ]
                ),
                encoding='utf-8',
            )

            loaded = ConfigLoader(config_path).load()

            self.assertIsNone(loaded.add_scheduled_logon_task)

    def test_invalid_ethernet_wifi_mode_raises_config_error(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / 'config.toml'
            config_path.write_text(
                "\n".join(
                    [
                        "[general]",
                        'ethernet_wifi_mode = "invalid-mode"',
                        "",
                        "[[networks]]",
                        'ssid = "Example"',
                        'auto_switch = true',
                        "",
                    ]
                ),
                encoding='utf-8',
            )

            with self.assertRaises(ConfigError):
                ConfigLoader(config_path).load()

    def test_global_section_overrides_legacy_general_values(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / 'config.toml'
            config_path.write_text(
                "\n".join(
                    [
                        '[general]',
                        'scan_interval = 15',
                        'auto_disable_wifi_on_ethernet = true',
                        '',
                        '[global]',
                        'scan_interval = 30',
                        'auto_disable_wifi_on_ethernet = false',
                        '',
                        '[[networks]]',
                        'ssid = "Example"',
                    ]
                ),
                encoding='utf-8',
            )

            loaded = ConfigLoader(config_path).load()

            self.assertEqual(loaded.scan_interval, 30)
            self.assertFalse(loaded.auto_disable_wifi_on_ethernet)

    def test_new_global_defaults_match_application_defaults(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / 'config.toml'
            config_path.write_text('[global]\n\n[[networks]]\nssid = "Example"\n', encoding='utf-8')

            loaded = ConfigLoader(config_path).load()

            self.assertFalse(loaded.add_to_startup_programs)
            self.assertIs(loaded.add_scheduled_logon_task, False)
            self.assertFalse(loaded.auto_disable_wifi_on_ethernet)
            self.assertTrue(loaded.connect_preferred_after_ethernet_disconnect)
            self.assertFalse(loaded.auto_check_for_updates)
            self.assertFalse(loaded.allow_prerelease_updates)

    def test_legacy_general_default_preserves_auto_disable_wifi_on_ethernet(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / 'config.toml'
            config_path.write_text('[general]\n\n[[networks]]\nssid = "Example"\n', encoding='utf-8')

            loaded = ConfigLoader(config_path).load()

            self.assertTrue(loaded.auto_disable_wifi_on_ethernet)


if __name__ == '__main__':
    unittest.main()
