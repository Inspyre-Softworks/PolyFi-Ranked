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
        sync_profile_order:
            Set Windows profile order.
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
