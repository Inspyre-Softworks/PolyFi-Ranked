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

import json
import logging
from pathlib import Path
import re
import subprocess
import time
from typing import TYPE_CHECKING, Sequence
import xml.etree.ElementTree as ET

if TYPE_CHECKING:
    from wifi_pref_manager.wifi_adapter_tasks import WifiAdapterTaskManager


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
        get_visible_network_signals:
            Get visible SSIDs with their strongest observed signal levels.
        get_visible_ssids:
            Get visible SSIDs.
        get_saved_profiles:
            Get saved Windows Wi-Fi profiles.
        connect:
            Connect to a saved Wi-Fi profile.
        disconnect:
            Disconnect current Wi-Fi.
        get_profiles_autoconnect_modes:
            Get auto/manual connect state for saved profiles.
        set_profiles_autoconnect:
            Set auto/manual connect state for saved profiles.
        disable_wifi_adapter:
            Disable the Wi-Fi adapter (turn off the radio).
        enable_wifi_adapter:
            Enable the Wi-Fi adapter (turn on the radio).
        sync_profile_order:
            Set Windows profile order.
        get_active_ethernet_interfaces:
            Return active Ethernet interface names.
        is_ethernet_connected:
            Check whether a physical Ethernet interface is currently connected.
        _run_powershell:
            Run a PowerShell one-liner and return its output.
        _get_known_wireless_interface_names:
            Return Wi-Fi interface names even when currently disabled.
        _get_all_wireless_interface_names:
            Return the names of every WLAN adapter detected by Windows.
        _get_active_ethernet_interfaces_netsh:
            Netsh-based fallback for Ethernet detection.
    """

    def __init__(
        self,
        logger: logging.Logger | None = None,
        task_manager: WifiAdapterTaskManager | None = None,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.task_manager = task_manager
        self._ethernet_exclusion_terms = (
            'bluetooth',
            'loopback',
            'npcap',
            'vethernet',
            'virtual',
            'vmware',
            'wireless',
            'wi-fi',
            'wifi',
            'wlan',
        )

    @staticmethod
    def _hidden_subprocess_kwargs() -> dict[str, object]:
        """
        Return Windows-specific subprocess flags that suppress console windows.

        Returns:
            Keyword arguments safe to splat into ``subprocess.run``.
        """
        kwargs: dict[str, object] = {}
        create_no_window = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        if create_no_window:
            kwargs['creationflags'] = create_no_window

        startupinfo_type = getattr(subprocess, 'STARTUPINFO', None)
        startf_use_showwindow = getattr(subprocess, 'STARTF_USESHOWWINDOW', 0)
        if startupinfo_type is not None and startf_use_showwindow:
            startupinfo = startupinfo_type()
            startupinfo.dwFlags |= startf_use_showwindow
            startupinfo.wShowWindow = 0
            kwargs['startupinfo'] = startupinfo

        return kwargs

    @staticmethod
    def is_elevation_required_error(exc: BaseException) -> bool:
        """
        Determine whether a command failure indicates missing administrator rights.

        Parameters:
            exc:
                Raised exception to inspect.

        Returns:
            True when the error text matches a common elevation-required failure.
        """
        message = str(exc).lower()
        return (
            'requires elevation' in message
            or 'run as administrator' in message
            or 'requested operation requires elevation' in message
        )

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
            **self._hidden_subprocess_kwargs(),
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
            **self._hidden_subprocess_kwargs(),
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
        if match:
            return match.group(1).strip()

        candidates = self._get_known_wireless_interface_names()
        if candidates:
            self.logger.debug(
                'No active WLAN interface reported by netsh; falling back to known Wi-Fi interface %s.',
                candidates[0],
            )
            return candidates[0]

        raise NetshError('Could not detect a wireless interface.')

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
        return list(self.get_visible_network_signals())

    @staticmethod
    def signal_percent_to_dbm(signal_percent: int) -> int:
        """
        Convert Windows Wi-Fi signal quality percent to an approximate dBm value.

        Parameters:
            signal_percent:
                Windows-reported signal quality percentage.

        Returns:
            Approximate dBm reading, where values closer to zero are stronger.
        """
        clamped = max(0, min(100, signal_percent))
        return int((clamped / 2) - 100)

    def get_visible_network_signals(self) -> dict[str, int]:
        """
        Get visible SSIDs and their strongest observed signal strengths.

        Returns:
            Mapping of SSID to strongest approximate dBm reading observed in the
            current scan.
        """
        output = self.run_netsh(['wlan', 'show', 'networks', 'mode=bssid'])
        networks: dict[str, int] = {}
        current_ssid: str | None = None

        for line in output.splitlines():
            ssid_match = re.match(r'^[ \t]*SSID\s+\d+[ \t]*:[ \t]*(.*?)[ \t]*$', line)
            if ssid_match:
                ssid = ssid_match.group(1).strip()
                current_ssid = ssid or None
                if current_ssid is not None and current_ssid not in networks:
                    networks[current_ssid] = -100
                continue

            signal_match = re.match(r'^[ \t]*Signal\s*:\s*(\d+)%\s*$', line)
            if current_ssid is None or signal_match is None:
                continue

            signal_dbm = self.signal_percent_to_dbm(int(signal_match.group(1)))
            if signal_dbm > networks[current_ssid]:
                networks[current_ssid] = signal_dbm

        return networks

    def get_saved_profiles(self) -> list[str]:
        """
        Get saved Windows Wi-Fi profile names.

        Returns:
            List of saved profile names.
        """
        output = self.run_netsh(['wlan', 'show', 'profiles'])
        profiles: list[str] = []
        for match in re.finditer(
            r'^\s*(?:All User Profile|Current User Profile)\s*:\s*(.+?)\s*$',
            output,
            re.MULTILINE,
        ):
            profiles.append(match.group(1).strip())
        if profiles:
            return profiles

        if 'there is no wireless interface on the system' in output.lower():
            fallback_profiles = self._get_saved_profiles_from_wlan_store()
            if fallback_profiles:
                self.logger.debug(
                    'Falling back to the Windows WLAN profile store because netsh reported no wireless interface.'
                )
                return fallback_profiles

        return profiles

    def _get_saved_profiles_from_wlan_store(self) -> list[str]:
        """
        Read saved Wi-Fi profile names directly from the Windows WLAN profile store.

        Returns:
            Sorted unique profile names discovered in the XML profile store.
        """
        profile_root = Path(r'C:\ProgramData\Microsoft\Wlansvc\Profiles\Interfaces')
        if not profile_root.exists():
            return []

        profiles: set[str] = set()
        for xml_path in profile_root.rglob('*.xml'):
            try:
                root = ET.parse(xml_path).getroot()
            except (ET.ParseError, OSError):
                self.logger.debug('Skipping unreadable WLAN profile XML: %s', xml_path, exc_info=True)
                continue

            name_node = root.find('{http://www.microsoft.com/networking/WLAN/profile/v1}name')
            if name_node is None or name_node.text is None:
                continue

            profile_name = name_node.text.strip()
            if profile_name:
                profiles.add(profile_name)

        return sorted(profiles)

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
        self.logger.debug('Attempting connection to %s', ssid)
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

    def set_profile_autoconnect(
        self,
        profile_name: str,
        *,
        enabled: bool,
        interface_name: str | None = None,
    ) -> None:
        """
        Set whether a profile should auto-connect.

        Parameters:
            profile_name:
                Saved Wi-Fi profile name.
            enabled:
                True for automatic connect, False for manual connect.
            interface_name:
                Optional interface name to scope the update.
        """
        mode = 'auto' if enabled else 'manual'
        args = ['wlan', 'set', 'profileparameter', f'name={profile_name}', f'connectionmode={mode}']
        if interface_name:
            args.append(f'interface={interface_name}')
        self.run_netsh(args)

    def get_profiles_autoconnect_modes(
        self,
        *,
        interface_name: str | None = None,
        profiles: Sequence[str] | None = None,
    ) -> dict[str, bool]:
        """
        Get auto/manual connect state for Wi-Fi profiles.

        Parameters:
            interface_name:
                Optional interface name used when querying profiles.
            profiles:
                Optional explicit profile list. Defaults to all saved profiles.

        Returns:
            Mapping of profile name to True (auto-connect) or False (manual).
        """
        profile_names = list(profiles) if profiles is not None else self.get_saved_profiles()
        modes: dict[str, bool] = {}

        for profile_name in profile_names:
            args = ['wlan', 'show', 'profile', f'name={profile_name}']
            if interface_name:
                args.append(f'interface={interface_name}')
            output = self.run_netsh(args)
            match = re.search(r'^\s*Connection mode\s*:\s*(.+?)\s*$', output, re.IGNORECASE | re.MULTILINE)
            if match is None:
                raise NetshError(
                    f'Could not determine connection mode for profile {profile_name!r}.'
                )
            mode_text = match.group(1).strip().lower()
            if 'manual' in mode_text:
                modes[profile_name] = False
            elif 'auto' in mode_text or 'automatically' in mode_text:
                modes[profile_name] = True
            else:
                raise NetshError(
                    f'Unrecognized connection mode for profile {profile_name!r}: {match.group(1)!r}'
                )

        return modes

    def set_profiles_autoconnect(
        self,
        *,
        enabled: bool,
        interface_name: str | None = None,
        profiles: Sequence[str] | None = None,
    ) -> None:
        """
        Set auto/manual connect behavior for multiple profiles.

        Parameters:
            enabled:
                True to enable auto-connect, False to require manual connect.
            interface_name:
                Optional interface name used when applying profile updates.
            profiles:
                Optional explicit profile list. Defaults to all saved profiles.
        """
        profile_names = list(profiles) if profiles is not None else self.get_saved_profiles()
        for profile_name in profile_names:
            self.set_profile_autoconnect(
                profile_name,
                enabled=enabled,
                interface_name=interface_name,
            )

    def is_interface_enabled(self, interface_name: str) -> bool:
        """
        Check whether an interface is administratively enabled.

        Parameters:
            interface_name:
                Interface name to inspect.

        Returns:
            True when the interface admin state is enabled.

        Raises:
            NetshError:
                If the interface cannot be found.
        """
        output = self.run_netsh(['interface', 'show', 'interface'])
        for line in output.splitlines():
            parts = line.split(None, 3)
            if len(parts) < 4:
                continue
            admin_state, _state, _iface_type, iface_name = (part.strip() for part in parts)
            if iface_name.lower() == interface_name.strip().lower():
                return admin_state.lower() == 'enabled'

        raise NetshError(f'Could not determine admin state for interface {interface_name!r}.')

    def disable_wifi_adapter(self, interface_name: str) -> None:
        """
        Disable the Wi-Fi adapter (turn off the radio).

        This is equivalent to pressing the WiFi button in Windows Quick Settings,
        completely disabling the wireless radio while leaving Ethernet active.

        When a task manager is configured and the corresponding scheduled task
        is installed, the command is executed via ``schtasks /run`` so no
        process elevation is needed.  The adapter state is verified afterwards;
        if still enabled the method falls back to a direct ``netsh`` call.

        Parameters:
            interface_name:
                Wireless interface name to disable.

        Raises:
            NetshError:
                If the command fails.
        """
        self.logger.debug('Disabling Wi-Fi adapter: %s', interface_name)
        if self.task_manager is not None:
            from wifi_pref_manager.wifi_adapter_tasks import WifiAdapterTaskError
            try:
                self.task_manager.disable_wifi()
                try:
                    if not self.is_interface_enabled(interface_name):
                        return
                    self.logger.warning(
                        'Wi-Fi adapter %r still enabled after task trigger; '
                        'falling back to direct netsh.',
                        interface_name,
                    )
                except NetshError:
                    pass  # Cannot verify — fall through to direct netsh.
            except WifiAdapterTaskError as exc:
                self.logger.warning(
                    'Scheduled-task Wi-Fi disable failed (%s); '
                    'falling back to direct netsh.',
                    exc,
                )
        self.run_netsh(['interface', 'set', 'interface', interface_name, 'admin=disabled'])

    def enable_wifi_adapter(self, interface_name: str) -> None:
        """
        Enable the Wi-Fi adapter (turn on the radio).

        This re-enables a previously disabled wireless adapter, allowing it to
        scan for and connect to networks.

        When a task manager is configured and the corresponding scheduled task
        is installed, the command is executed via ``schtasks /run`` so no
        process elevation is needed.  The adapter state is verified afterwards;
        if still disabled the method falls back to a direct ``netsh`` call.

        Parameters:
            interface_name:
                Wireless interface name to enable.

        Raises:
            NetshError:
                If the command fails.
        """
        self.logger.debug('Enabling Wi-Fi adapter: %s', interface_name)
        if self.task_manager is not None:
            from wifi_pref_manager.wifi_adapter_tasks import WifiAdapterTaskError
            try:
                self.task_manager.enable_wifi()
                try:
                    if self.is_interface_enabled(interface_name):
                        return
                    self.logger.warning(
                        'Wi-Fi adapter %r still disabled after task trigger; '
                        'falling back to direct netsh.',
                        interface_name,
                    )
                except NetshError:
                    pass  # Cannot verify — fall through to direct netsh.
            except WifiAdapterTaskError as exc:
                self.logger.warning(
                    'Scheduled-task Wi-Fi enable failed (%s); '
                    'falling back to direct netsh.',
                    exc,
                )
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

    def _get_known_wireless_interface_names(self) -> list[str]:
        """
        Return Wi-Fi interface names, even if they are currently disabled.

        Returns:
            Ordered list of candidate Wi-Fi interface names.
        """
        try:
            output = self._run_powershell(
                'Get-NetAdapter |'
                ' Where-Object { $_.InterfaceType -eq 71 } |'
                ' Select-Object -ExpandProperty Name'
            )
        except (OSError, subprocess.SubprocessError):
            self.logger.debug(
                'PowerShell Wi-Fi interface fallback unavailable.',
                exc_info=True,
            )
            return []

        return [
            line.strip()
            for line in output.splitlines()
            if line.strip()
        ]

    def _is_probable_ethernet_name(self, name: str) -> bool:
        """
        Determine whether an interface name/description looks like real Ethernet.

        Parameters:
            name:
                Interface name or description.

        Returns:
            True when the text does not match a known non-Ethernet exclusion.
        """
        name_lower = name.strip().lower()
        return not any(term in name_lower for term in self._ethernet_exclusion_terms)

    def get_active_ethernet_interfaces(self, wifi_interface_name: str | None = None) -> list[str]:
        """
        Return the names of active wired Ethernet interfaces.

        Parameters:
            wifi_interface_name:
                Optional wireless interface name to exclude in the fallback path.

        Returns:
            List of interface names that look like real, active Ethernet links.
        """
        try:
            return self._get_active_ethernet_interfaces_netsh_strict(wifi_interface_name)
        except NetshError:
            self.logger.debug(
                'Netsh Ethernet detection unavailable; falling back to PowerShell.',
                exc_info=True,
            )

        try:
            return self._get_active_ethernet_interfaces_powershell()
        except (json.JSONDecodeError, OSError, subprocess.SubprocessError):
            self.logger.debug(
                'PowerShell Ethernet detection unavailable.',
                exc_info=True,
            )
            return []

    def is_ethernet_connected(self, wifi_interface_name: str | None = None) -> bool:
        """
        Check whether a physical Ethernet interface is currently connected.

        Uses the active-Ethernet interface list generated by
        ``get_active_ethernet_interfaces``. The PowerShell path requires a
        connected type-6 adapter whose physical media type is ``802.3``, then
        filters out loopback, Wi-Fi, Bluetooth, and other known non-Ethernet
        names. Falls back to a ``netsh``-based heuristic if PowerShell is
        unavailable or returns a non-zero exit code.

        Parameters:
            wifi_interface_name:
                Ignored when PowerShell detection succeeds; forwarded to the
                netsh fallback for backwards compatibility.

        Returns:
            ``True`` when at least one candidate active Ethernet interface is
            detected.
        """
        return bool(self.get_active_ethernet_interfaces(wifi_interface_name))

    def _get_active_ethernet_interfaces_powershell(self) -> list[str]:
        """
        Return active Ethernet interfaces using PowerShell as a fallback.

        This path is intentionally kept out of the normal polling loop because
        starting PowerShell every few seconds is noticeably heavier than the
        ``netsh`` interface query.
        """
        output = self._run_powershell(
            '$adapters = Get-NetAdapter -Physical | Where-Object {'
            ' $_.InterfaceType -eq 6'
            ' -and $_.Status -eq "Up"'
            ' -and $_.MediaConnectionState -eq "Connected"'
            ' -and $_.PhysicalMediaType -eq "802.3"'
            ' -and $_.ComponentID -ne "*msloop"'
            ' } | Select-Object Name, InterfaceDescription;'
            ' if ($adapters) { $adapters | ConvertTo-Json -Compress } else { "[]" }'
        )
        parsed = json.loads(output or '[]')
        adapters = parsed if isinstance(parsed, list) else [parsed]
        names = [
            str(adapter.get('Name', '')).strip()
            for adapter in adapters
            if self._is_probable_ethernet_name(str(adapter.get('Name', '')))
            and self._is_probable_ethernet_name(str(adapter.get('InterfaceDescription', '')))
        ]
        self.logger.debug(
            'PowerShell Ethernet candidates: %s',
            ', '.join(names) if names else '[none]',
        )
        return names

    def _get_active_ethernet_interfaces_netsh_strict(
        self,
        wifi_interface_name: str | None = None,
    ) -> list[str]:
        """
        Netsh-based Ethernet detection that lets command failures propagate.

        Checks ``netsh interface show interface`` for any enabled, connected,
        Dedicated interface that is not a known wireless adapter and does not
        have the ``vEthernet`` virtual-adapter prefix.

        Parameters:
            wifi_interface_name:
                Optional extra wireless interface name to exclude.

        Returns:
            List of candidate Ethernet interface names.
        """
        output = self.run_netsh(['interface', 'show', 'interface'])

        # Collect *all* wireless interface names so we can exclude them.
        wireless_names: set[str] = self._get_all_wireless_interface_names()
        if wifi_interface_name:
            wireless_names.add(wifi_interface_name.strip().lower())

        connected_interfaces: list[str] = []
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
                and self._is_probable_ethernet_name(iface_name)
            ):
                connected_interfaces.append(iface_name)

        self.logger.debug(
            'Netsh Ethernet candidates: %s',
            ', '.join(connected_interfaces) if connected_interfaces else '[none]',
        )
        return connected_interfaces

    def _get_active_ethernet_interfaces_netsh(self, wifi_interface_name: str | None = None) -> list[str]:
        """
        Netsh-based fallback for Ethernet detection.
        """
        try:
            return self._get_active_ethernet_interfaces_netsh_strict(wifi_interface_name)
        except NetshError:
            return []

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
