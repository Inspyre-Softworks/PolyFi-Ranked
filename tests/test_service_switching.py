from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from wifi_pref_manager.models import AppConfig, WiFiProfilePreference
from wifi_pref_manager.service import WiFiPreferenceService


class FakeWiFiApi:
    def __init__(self) -> None:
        self.task_manager = None
        self.adapter_enabled = True
        self.current_ssid: str | None = 'HomeWiFi'
        self.visible_networks: dict[str, int] = {}
        self.active_ethernet_interfaces: list[str] = []
        self.profile_modes = {
            'HomeWiFi': True,
            'BackupWiFi': True,
            'PhoneHotspot': True,
        }
        self.disconnect_calls = 0
        self.connect_calls: list[str] = []
        self.visible_scan_calls = 0

    def is_interface_enabled(self, interface_name: str) -> bool:
        del interface_name
        return self.adapter_enabled

    def get_current_ssid(self) -> str | None:
        return self.current_ssid

    def get_saved_profiles(self) -> list[str]:
        return list(self.profile_modes)

    def get_profiles_autoconnect_modes(
        self,
        *,
        interface_name: str | None = None,
        profiles: list[str] | None = None,
    ) -> dict[str, bool]:
        del interface_name
        selected = profiles if profiles is not None else list(self.profile_modes)
        return {name: self.profile_modes[name] for name in selected}

    def set_profiles_autoconnect(
        self,
        *,
        enabled: bool,
        interface_name: str | None = None,
        profiles: list[str] | None = None,
    ) -> None:
        del interface_name
        selected = profiles if profiles is not None else list(self.profile_modes)
        for profile_name in selected:
            self.profile_modes[profile_name] = enabled

    def set_profile_autoconnect(
        self,
        profile_name: str,
        *,
        enabled: bool,
        interface_name: str | None = None,
    ) -> None:
        del interface_name
        self.profile_modes[profile_name] = enabled

    def get_active_ethernet_interfaces(self, wifi_interface_name: str | None = None) -> list[str]:
        del wifi_interface_name
        return list(self.active_ethernet_interfaces)

    def disconnect(self, interface_name: str) -> None:
        del interface_name
        self.disconnect_calls += 1
        self.current_ssid = None

    def connect(self, interface_name: str, ssid: str, timeout: int) -> bool:
        del interface_name, timeout
        self.connect_calls.append(ssid)
        self.current_ssid = ssid
        return True

    def get_visible_network_signals(self) -> dict[str, int]:
        self.visible_scan_calls += 1
        return dict(self.visible_networks)

    def sync_profile_order(self, interface_name: str, ssids: list[str]) -> None:
        del interface_name, ssids


class ServiceSwitchingThresholdTests(unittest.TestCase):
    def _build_service(self, api: FakeWiFiApi) -> WiFiPreferenceService:
        config = AppConfig(
            preferred_networks=[
                WiFiProfilePreference('HomeWiFi', min_db=-60),
                WiFiProfilePreference('BackupWiFi', min_db=-70),
                WiFiProfilePreference('PhoneHotspot', min_db=-80),
            ],
            interface_name='Wi-Fi',
            auto_disable_wifi_on_ethernet=False,
            show_wifi_disabled_dialog=False,
            enable_speed_tests=False,
        )
        return WiFiPreferenceService(
            config=config,
            wifi_api=api,
            logger=Mock(),
        )

    def test_switches_to_next_acceptable_network_when_current_drops_below_min_signal(self) -> None:
        api = FakeWiFiApi()
        api.current_ssid = 'HomeWiFi'
        api.visible_networks = {
            'HomeWiFi': -72,
            'BackupWiFi': -65,
        }
        service = self._build_service(api)
        notifications: list[tuple[str | None, str, str | None]] = []
        service.set_wifi_network_changed_callback(
            lambda previous, new, reason: notifications.append((previous, new, reason))
        )

        service.evaluate_and_switch()

        self.assertEqual(api.disconnect_calls, 1)
        self.assertEqual(api.connect_calls, ['BackupWiFi'])
        self.assertEqual(api.current_ssid, 'BackupWiFi')
        self.assertEqual(
            notifications,
            [
                (
                    'HomeWiFi',
                    'BackupWiFi',
                    'HomeWiFi fell below its minimum signal (-72 dBm observed, -60 dBm required). '
                    'BackupWiFi is available at -65 dBm.',
                )
            ],
        )

    def test_keeps_current_network_when_no_other_preferred_network_meets_threshold(self) -> None:
        api = FakeWiFiApi()
        api.current_ssid = 'HomeWiFi'
        api.visible_networks = {
            'HomeWiFi': -72,
            'BackupWiFi': -75,
            'PhoneHotspot': -83,
        }
        service = self._build_service(api)

        service.evaluate_and_switch()

        self.assertEqual(api.disconnect_calls, 0)
        self.assertEqual(api.connect_calls, [])
        self.assertEqual(api.current_ssid, 'HomeWiFi')

    def test_skips_networks_below_their_threshold_before_attempting_to_connect(self) -> None:
        api = FakeWiFiApi()
        api.current_ssid = None
        api.visible_networks = {
            'HomeWiFi': -72,
            'BackupWiFi': -65,
            'PhoneHotspot': -78,
        }
        service = self._build_service(api)

        service.evaluate_and_switch()

        self.assertEqual(api.connect_calls, ['BackupWiFi'])
        self.assertEqual(api.current_ssid, 'BackupWiFi')

    def test_skips_visible_scan_when_current_network_is_already_highest_actionable(self) -> None:
        api = FakeWiFiApi()
        api.current_ssid = 'HomeWiFi'
        api.visible_networks = {'BackupWiFi': -40}
        config = AppConfig(
            preferred_networks=[
                WiFiProfilePreference('HomeWiFi'),
                WiFiProfilePreference('BackupWiFi'),
            ],
            interface_name='Wi-Fi',
            auto_disable_wifi_on_ethernet=False,
            show_wifi_disabled_dialog=False,
            enable_speed_tests=False,
        )
        service = WiFiPreferenceService(
            config=config,
            wifi_api=api,
            logger=Mock(),
        )

        service.evaluate_and_switch()

        self.assertEqual(api.visible_scan_calls, 0)
        self.assertEqual(api.disconnect_calls, 0)
        self.assertEqual(api.connect_calls, [])

    def test_still_scans_when_current_network_has_minimum_signal_threshold(self) -> None:
        api = FakeWiFiApi()
        api.current_ssid = 'HomeWiFi'
        api.visible_networks = {'HomeWiFi': -55}
        service = self._build_service(api)

        service.evaluate_and_switch()

        self.assertEqual(api.visible_scan_calls, 1)
        self.assertEqual(api.disconnect_calls, 0)
        self.assertEqual(api.connect_calls, [])

    def test_speed_test_on_new_connection_ignores_initial_observed_connection(self) -> None:
        api = FakeWiFiApi()
        config = AppConfig(
            preferred_networks=[WiFiProfilePreference('HomeWiFi')],
            interface_name='Wi-Fi',
            auto_disable_wifi_on_ethernet=False,
            show_wifi_disabled_dialog=False,
            enable_speed_tests=True,
            speed_test_on_new_connection=True,
        )
        service = WiFiPreferenceService(
            config=config,
            wifi_api=api,
            logger=Mock(),
        )
        service._start_speed_test = Mock()  # type: ignore[method-assign]

        service._maybe_schedule_speed_test('HomeWiFi')
        service._maybe_schedule_speed_test('BackupWiFi')

        service._start_speed_test.assert_called_once_with('BackupWiFi', 'new network connection')


if __name__ == '__main__':
    unittest.main()
