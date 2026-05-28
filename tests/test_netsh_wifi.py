from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from wifi_pref_manager.netsh_wifi import NetshError, NetshWiFiApi


_INTERFACE_TABLE = '\n'.join(
    [
        'Admin State    State          Type             Interface Name',
        '-------------------------------------------------------------------------',
        'Enabled        Connected      Dedicated        Ethernet',
        'Enabled        Connected      Dedicated        Wi-Fi',
        'Enabled        Connected      Dedicated        vEthernet (Default Switch)',
        'Enabled        Disconnected   Dedicated        Ethernet 2',
    ]
)

_WLAN_SHOW_INTERFACES_SINGLE = 'Name                   : Wi-Fi\n'

_WLAN_SHOW_INTERFACES_MULTI = (
    'Name                   : Wi-Fi\n'
    'Name                   : Wi-Fi 2\n'
)


def _make_run_netsh_side_effect(wlan_output: str):
    """Return a side_effect callable that dispatches on the netsh sub-command."""

    def _dispatch(args):
        if args[0] == 'wlan':
            return wlan_output
        return _INTERFACE_TABLE

    return _dispatch


class NetshWiFiEthernetDetectionTests(unittest.TestCase):
    def test_active_ethernet_detection_uses_netsh_without_powershell_when_available(self) -> None:
        api = NetshWiFiApi(logger=Mock())
        api.run_netsh = Mock(  # type: ignore[method-assign]
            side_effect=_make_run_netsh_side_effect(_WLAN_SHOW_INTERFACES_SINGLE)
        )
        api._run_powershell = Mock(side_effect=AssertionError('PowerShell should not be used'))  # type: ignore[method-assign]

        result = api.get_active_ethernet_interfaces(wifi_interface_name='Wi-Fi')

        self.assertEqual(result, ['Ethernet'])
        api._run_powershell.assert_not_called()

    def test_extra_wireless_adapters_excluded_when_wifi_interface_name_supplied(self) -> None:
        """When wifi_interface_name is given, *all* WLAN adapters must still be excluded."""
        api = NetshWiFiApi(logger=Mock())
        api.run_netsh = Mock(  # type: ignore[method-assign]
            side_effect=_make_run_netsh_side_effect(_WLAN_SHOW_INTERFACES_MULTI)
        )
        api._run_powershell = Mock(side_effect=AssertionError('PowerShell should not be used'))  # type: ignore[method-assign]

        # Interface table additionally has "Wi-Fi 2" connected as Dedicated.
        interface_table_with_extra = '\n'.join(
            [
                'Admin State    State          Type             Interface Name',
                '-------------------------------------------------------------------------',
                'Enabled        Connected      Dedicated        Ethernet',
                'Enabled        Connected      Dedicated        Wi-Fi',
                'Enabled        Connected      Dedicated        Wi-Fi 2',
                'Enabled        Connected      Dedicated        vEthernet (Default Switch)',
            ]
        )
        api.run_netsh = Mock(  # type: ignore[method-assign]
            side_effect=lambda args: (
                _WLAN_SHOW_INTERFACES_MULTI if args[0] == 'wlan' else interface_table_with_extra
            )
        )

        result = api.get_active_ethernet_interfaces(wifi_interface_name='Wi-Fi')

        # Both Wi-Fi and Wi-Fi 2 must be excluded; only Ethernet remains.
        self.assertEqual(result, ['Ethernet'])

    def test_active_ethernet_detection_falls_back_to_powershell_when_netsh_fails(self) -> None:
        api = NetshWiFiApi(logger=Mock())
        api.run_netsh = Mock(side_effect=NetshError('netsh unavailable'))  # type: ignore[method-assign]
        api._run_powershell = Mock(  # type: ignore[method-assign]
            return_value=(
                '[{"Name":"Ethernet","InterfaceDescription":"Intel Ethernet"},'
                '{"Name":"vEthernet (Default Switch)","InterfaceDescription":"Hyper-V Virtual Ethernet Adapter"}]'
            )
        )

        result = api.get_active_ethernet_interfaces(wifi_interface_name='Wi-Fi')

        self.assertEqual(result, ['Ethernet'])
        api._run_powershell.assert_called_once()


if __name__ == '__main__':
    unittest.main()
