from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from wifi_pref_manager.netsh_wifi import NetshError, NetshWiFiApi


class NetshWiFiEthernetDetectionTests(unittest.TestCase):
    def test_active_ethernet_detection_uses_netsh_without_powershell_when_available(self) -> None:
        api = NetshWiFiApi(logger=Mock())
        api.run_netsh = Mock(  # type: ignore[method-assign]
            return_value='\n'.join(
                [
                    'Admin State    State          Type             Interface Name',
                    '-------------------------------------------------------------------------',
                    'Enabled        Connected      Dedicated        Ethernet',
                    'Enabled        Connected      Dedicated        Wi-Fi',
                    'Enabled        Connected      Dedicated        vEthernet (Default Switch)',
                    'Enabled        Disconnected   Dedicated        Ethernet 2',
                ]
            )
        )
        api._run_powershell = Mock(side_effect=AssertionError('PowerShell should not be used'))  # type: ignore[method-assign]

        result = api.get_active_ethernet_interfaces(wifi_interface_name='Wi-Fi')

        self.assertEqual(result, ['Ethernet'])
        api.run_netsh.assert_called_once_with(['interface', 'show', 'interface'])
        api._run_powershell.assert_not_called()

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
