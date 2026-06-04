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
        self.current_ssid = 'HomeWiFi'
        self.profile_modes = {
            'HomeWiFi': True,
            'CafeWiFi': False,
        }
        self.active_ethernet_interfaces = ['Ethernet']

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
        self.current_ssid = None

    def connect(self, interface_name: str, ssid: str, timeout: int) -> bool:
        del interface_name, timeout
        self.current_ssid = ssid
        return True

    def get_visible_network_signals(self) -> dict[str, int]:
        return {}

    def sync_profile_order(self, interface_name: str, ssids: list[str]) -> None:
        del interface_name, ssids


class EthernetWiFiModeStateTests(unittest.TestCase):
    def _build_config(self) -> AppConfig:
        return AppConfig(
            preferred_networks=[WiFiProfilePreference('HomeWiFi')],
            interface_name='Wi-Fi',
            auto_disable_wifi_on_ethernet=True,
            ethernet_wifi_mode='disconnect_and_disable_autoconnect',
            show_wifi_disabled_dialog=False,
            enable_speed_tests=False,
        )

    def test_state_is_restored_on_ethernet_disconnect(self) -> None:
        api = FakeWiFiApi()
        service = WiFiPreferenceService(
            config=self._build_config(),
            wifi_api=api,
            logger=Mock(),
        )

        service.evaluate_and_switch()
        self.assertIsNone(api.current_ssid)
        self.assertEqual(api.profile_modes, {'HomeWiFi': False, 'CafeWiFi': False})

        api.active_ethernet_interfaces = []
        service.evaluate_and_switch()

        self.assertEqual(api.current_ssid, 'HomeWiFi')
        self.assertEqual(api.profile_modes, {'HomeWiFi': True, 'CafeWiFi': False})

    def test_state_is_restored_on_exit(self) -> None:
        api = FakeWiFiApi()
        service = WiFiPreferenceService(
            config=self._build_config(),
            wifi_api=api,
            logger=Mock(),
        )

        service.evaluate_and_switch()
        self.assertIsNone(api.current_ssid)
        self.assertEqual(api.profile_modes, {'HomeWiFi': False, 'CafeWiFi': False})

        service.restore_startup_network_state()

        self.assertEqual(api.current_ssid, 'HomeWiFi')
        self.assertEqual(api.profile_modes, {'HomeWiFi': True, 'CafeWiFi': False})

    def test_exit_restore_swallows_oserror_from_get_current_ssid(self) -> None:
        api = FakeWiFiApi()
        service = WiFiPreferenceService(
            config=self._build_config(),
            wifi_api=api,
            logger=Mock(),
        )

        service.evaluate_and_switch()
        service.wifi_api.get_current_ssid = Mock(side_effect=OSError('netsh unavailable'))  # type: ignore[method-assign]

        service.restore_startup_network_state()


if __name__ == '__main__':
    unittest.main()
