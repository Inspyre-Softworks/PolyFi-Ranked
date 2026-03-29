"""
Author:
    Inspyre Softworks

Project:
    WiFi Preference Manager

File:
    netsh_wifi.py

Description:
    Windows `netsh` wrapper used to query and control Wi-Fi interfaces.

Functions:
    None.

Constants:
    None.

Dependencies:
    logging
    re
    subprocess
    time

Example Usage:
    api = NetshWiFiApi(logger)
"""

from __future__ import annotations

import logging
import re
import subprocess
import time
from typing import Sequence


class NetshError(RuntimeError):
    """Raised when a netsh operation fails."""


class NetshWiFiApi:
    """
    Simple wrapper around Windows `netsh wlan`.

    Methods:
        detect_wifi_interface:
            Detect a wireless interface name.
        get_current_ssid:
            Get the currently connected SSID.
        get_visible_ssids:
            Get visible SSIDs.
        get_saved_profiles:
            Get saved Windows Wi-Fi profiles.
        connect:
            Connect to a saved Wi-Fi profile.
        disconnect:
            Disconnect current Wi-Fi.
        disable_wifi_adapter:
            Disable the Wi-Fi adapter (turn off the radio).
        enable_wifi_adapter:
            Enable the Wi-Fi adapter (turn on the radio).
        sync_profile_order:
            Set Windows profile order.
        is_ethernet_connected:
            Check whether a physical Ethernet interface is currently connected.
        _run_powershell:
            Run a PowerShell one-liner and return its output.
        _get_all_wireless_interface_names:
            Return the names of every WLAN adapter detected by Windows.
        _is_ethernet_connected_netsh:
            Netsh-based fallback for Ethernet detection.
    """

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def run_netsh(self, args: Sequence[str]) -> str:
        """
        Run a netsh command.

        Parameters:
            args:
                Arguments after the `netsh` executable.

        Returns:
            Standard output text.

        Raises:
            NetshError:
                If the command fails.
        """
        command = ['netsh', *args]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            shell=False,
        )

        if result.returncode != 0:
            raise NetshError(
                f'Command failed: {" ".join(command)}\n'
                f'stdout:\n{result.stdout}\n'
                f'stderr:\n{result.stderr}'
            )

        return result.stdout

    def _run_powershell(self, script: str) -> str:
        """
        Run a PowerShell one-liner and return its stripped stdout.

        Parameters:
            script:
                PowerShell script to execute.

        Returns:
            Stripped standard output from PowerShell.

        Raises:
            OSError:
                If the ``powershell`` executable is not found.
            subprocess.SubprocessError:
                If the subprocess cannot be started or exits with a non-zero
                return code.
        """
        result = subprocess.run(
            ['powershell', '-NoProfile', '-NonInteractive', '-Command', script],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            shell=False,
        )
        if result.returncode != 0:
            raise subprocess.SubprocessError(
                f'PowerShell exited with code {result.returncode}.\n'
                f'stderr:\n{result.stderr}'
            )
        return result.stdout.strip()

    def detect_wifi_interface(self) -> str:
        """
        Detect the first Wi-Fi interface name.

        Returns:
            Interface name.
        """
        output = self.run_netsh(['wlan', 'show', 'interfaces'])
        match = re.search(r'^\s*Name\s*:\s*(.+?)\s*$', output, re.MULTILINE)
        if not match:
            raise NetshError('Could not detect a wireless interface.')
        return match.group(1).strip()

    def get_current_ssid(self) -> str | None:
        """
        Get the currently connected SSID.

        Returns:
            SSID string or None.
        """
        output = self.run_netsh(['wlan', 'show', 'interfaces'])
        state_match = re.search(r'^\s*State\s*:\s*(.+?)\s*$', output, re.MULTILINE)
        if not state_match or state_match.group(1).strip().lower() != 'connected':
            return None

        ssid_match = re.search(r'^\s*SSID\s*:\s*(.+?)\s*$', output, re.MULTILINE)
        return ssid_match.group(1).strip() if ssid_match else None

    def get_visible_ssids(self) -> list[str]:
        """
        Get visible SSIDs from a scan.

        Returns:
            Unique list of SSIDs.
        """
        output = self.run_netsh(['wlan', 'show', 'networks', 'mode=bssid'])
        ssids: list[str] = []
        for match in re.finditer(r'^\s*SSID\s+\d+\s*:\s*(.*?)\s*$', output, re.MULTILINE):
            ssid = match.group(1).strip()
            if ssid and ssid not in ssids:
                ssids.append(ssid)
        return ssids

    def get_saved_profiles(self) -> list[str]:
        """
        Get saved Windows Wi-Fi profile names.

        Returns:
            List of saved profile names.
        """
        output = self.run_netsh(['wlan', 'show', 'profiles'])
        profiles: list[str] = []
        for match in re.finditer(r'^\s*All User Profile\s*:\s*(.+?)\s*$', output, re.MULTILINE):
            profiles.append(match.group(1).strip())
        return profiles

    def connect(self, interface_name: str, ssid: str, timeout: int) -> bool:
        """
        Connect to a saved Wi-Fi profile.

        Parameters:
            interface_name:
                Wireless interface name.
            ssid:
                Saved profile name.
            timeout:
                Seconds to wait before verifying the result.

        Returns:
            True if connected to the requested SSID.
        """
        self.logger.info('Attempting connection to %s', ssid)
        self.run_netsh([
            'wlan',
            'connect',
            f'name={ssid}',
            f'ssid={ssid}',
            f'interface={interface_name}',
        ])
        time.sleep(timeout)
        return self.get_current_ssid() == ssid

    def disconnect(self, interface_name: str) -> None:
        """
        Disconnect Wi-Fi from the specified interface.

        Parameters:
            interface_name:
                Wireless interface name.
        """
        self.run_netsh(['wlan', 'disconnect', f'interface={interface_name}'])

    def disable_wifi_adapter(self, interface_name: str) -> None:
        """
        Disable the Wi-Fi adapter (turn off the radio).

        This is equivalent to pressing the WiFi button in Windows Quick Settings,
        completely disabling the wireless radio while leaving Ethernet active.

        Parameters:
            interface_name:
                Wireless interface name to disable.

        Raises:
            NetshError:
                If the command fails.
        """
        self.logger.info('Disabling Wi-Fi adapter: %s', interface_name)
        self.run_netsh(['interface', 'set', 'interface', interface_name, 'admin=disabled'])

    def enable_wifi_adapter(self, interface_name: str) -> None:
        """
        Enable the Wi-Fi adapter (turn on the radio).

        This re-enables a previously disabled wireless adapter, allowing it to
        scan for and connect to networks.

        Parameters:
            interface_name:
                Wireless interface name to enable.

        Raises:
            NetshError:
                If the command fails.
        """
        self.logger.info('Enabling Wi-Fi adapter: %s', interface_name)
        self.run_netsh(['interface', 'set', 'interface', interface_name, 'admin=enabled'])

    def _get_all_wireless_interface_names(self) -> set[str]:
        """
        Return the lower-cased names of every WLAN adapter detected by Windows.

        Returns:
            Set of lower-cased wireless interface names.
        """
        try:
            output = self.run_netsh(['wlan', 'show', 'interfaces'])
        except NetshError:
            return set()

        return {
            match.group(1).strip().lower()
            for match in re.finditer(r'^\s*Name\s*:\s*(.+?)\s*$', output, re.MULTILINE)
        }

    def is_ethernet_connected(self, wifi_interface_name: str | None = None) -> bool:
        """
        Check whether a physical Ethernet interface is currently connected.

        Uses PowerShell's ``Get-NetAdapter -Physical`` with an ``InterfaceType``
        filter to *positively* identify physical Ethernet.  IANA interface type
        ``6`` (``ethernetCsmacd``) is always used by Windows for physical
        Ethernet — regardless of driver or Windows version — and is never used
        for Wi-Fi (``71``), VPN tunnels (``131``), Bluetooth PAN (``259``), or
        any other adapter type.  The ``-Physical`` flag additionally excludes
        all virtual adapters (Hyper-V, Docker, WSL2).

        Falls back to a ``netsh``-based heuristic if PowerShell is
        unavailable or returns a non-zero exit code.

        Parameters:
            wifi_interface_name:
                Ignored when PowerShell detection succeeds; forwarded to the
                netsh fallback for backwards compatibility.

        Returns:
            ``True`` when at least one physical Ethernet adapter with
            ``Status 'Up'`` is detected.
        """
        try:
            output = self._run_powershell(
                'if (Get-NetAdapter -Physical |'
                ' Where-Object { $_.InterfaceType -eq 6 -and $_.Status -eq "Up" })'
                ' { "YES" } else { "NO" }'
            )
            result = output.upper() == 'YES'
            self.logger.debug('PowerShell Ethernet detection result: %s (raw output: %r)', result, output)
            return result
        except (OSError, subprocess.SubprocessError):
            self.logger.debug(
                'PowerShell Ethernet detection unavailable; falling back to netsh.',
                exc_info=True,
            )
            return self._is_ethernet_connected_netsh(wifi_interface_name)

    def _is_ethernet_connected_netsh(self, wifi_interface_name: str | None = None) -> bool:
        """
        Netsh-based fallback for Ethernet detection.

        Checks ``netsh interface show interface`` for any enabled, connected,
        Dedicated interface that is not a known wireless adapter and does not
        have the ``vEthernet`` virtual-adapter prefix.

        Parameters:
            wifi_interface_name:
                Optional extra wireless interface name to exclude.

        Returns:
            ``True`` when at least one candidate Ethernet interface is found.
        """
        try:
            output = self.run_netsh(['interface', 'show', 'interface'])
        except NetshError:
            return False

        # Collect *all* wireless interface names so we can exclude them.
        wireless_names: set[str] = self._get_all_wireless_interface_names()
        if wifi_interface_name:
            wireless_names.add(wifi_interface_name.strip().lower())

        for line in output.splitlines():
            parts = line.split(None, 3)
            if len(parts) < 4:
                continue
            admin_state, state, iface_type, iface_name = (p.strip() for p in parts)
            iface_name_lower = iface_name.lower()
            if (
                admin_state.lower() == 'enabled'
                and state.lower() == 'connected'
                and iface_type.lower() == 'dedicated'
                and iface_name_lower not in wireless_names
                and not iface_name_lower.startswith('vethernet')
            ):
                return True

        return False

    def sync_profile_order(self, interface_name: str, ssids: list[str]) -> None:
        """
        Sync Windows profile order to match preference order.

        Parameters:
            interface_name:
                Wireless interface name.
            ssids:
                Ordered list of profile names.
        """
        saved_profiles = set(self.get_saved_profiles())
        priority = 1
        for ssid in ssids:
            if ssid not in saved_profiles:
                self.logger.warning('Skipping missing saved profile: %s', ssid)
                continue
            self.run_netsh([
                'wlan',
                'set',
                'profileorder',
                f'name={ssid}',
                f'interface={interface_name}',
                f'priority={priority}',
            ])
            priority += 1
