"""
Author:
    Inspyre Softworks

Project:
    PolyFi: Ranked

File:
    models.py

Description:
    Data models for runtime configuration and Wi-Fi preference entries.

Functions:
    None.

Constants:
    None.

Dependencies:
    dataclasses
    typing

Example Usage:
    from wifi_pref_manager.models import AppConfig
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class WiFiProfilePreference:
    """
    Represents a preferred Wi-Fi network.

    Parameters:
        ssid:
            Saved Windows Wi-Fi profile name / SSID.
        auto_switch:
            Whether the manager may automatically switch to this network.
    """

    ssid: str
    auto_switch: bool = True


@dataclass
class AppConfig:
    """
    Stores runtime configuration for the application.

    Parameters:
        preferred_networks:
            Ordered list of Wi-Fi preferences, highest priority first.
        interface_name:
            Optional Wi-Fi interface name. If blank, auto-detect is used.
        scan_interval:
            Number of seconds between scan cycles.
        connect_timeout:
            Number of seconds to wait after a connect attempt.
        sync_profile_order_on_start:
            Whether to sync Windows profile order at startup.
        log_level:
            Logging level string.
        log_file:
            Path to the application log file.
        start_minimized_to_tray:
            Whether the tray app should start minimized.
        auto_disable_wifi_on_ethernet:
            Automatically disconnect Wi-Fi when an Ethernet connection is detected.
    """

    preferred_networks: list[WiFiProfilePreference] = field(default_factory=list)
    interface_name: Optional[str] = None
    scan_interval: int = 10
    connect_timeout: int = 8
    sync_profile_order_on_start: bool = True
    log_level: str = 'INFO'
    log_file: str = ''
    start_minimized_to_tray: bool = False
    auto_disable_wifi_on_ethernet: bool = True
