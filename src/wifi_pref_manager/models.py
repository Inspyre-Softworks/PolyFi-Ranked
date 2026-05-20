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

ETHERNET_WIFI_MODE_DISCONNECT = 'disconnect_and_disable_autoconnect'
ETHERNET_WIFI_MODE_DISABLE_ADAPTER = 'disable_adapter'
ETHERNET_WIFI_MODE_VALUES = {
    ETHERNET_WIFI_MODE_DISCONNECT,
    ETHERNET_WIFI_MODE_DISABLE_ADAPTER,
}


@dataclass(frozen=True)
class WiFiProfilePreference:
    """
    Represents a preferred Wi-Fi network.

    Parameters:
        ssid:
            Saved Windows Wi-Fi profile name / SSID.
        auto_switch:
            Whether the manager may automatically switch to this network.
        min_db:
            Optional minimum signal threshold. When set, the network is treated
            as unavailable if the observed signal is weaker than this value.
    """

    ssid: str
    auto_switch: bool = True
    min_db: int | None = None


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
        ethernet_wifi_mode:
            Action taken when Ethernet is active and auto-disable is enabled.
            ``disconnect_and_disable_autoconnect`` disconnects Wi-Fi and sets all
            saved profiles to manual connect until Ethernet disconnects (or app exit).
            ``disable_adapter`` turns the Wi-Fi adapter fully off.
        show_wifi_disabled_dialog:
            Whether to show a dialog when PolyFi disables the Wi-Fi adapter.
        show_startup_splash:
            Whether to show the startup splash screen.
        splash_image_path:
            Optional splash image path. Blank uses built-in default lookup paths.
        splash_fade_in_ms:
            Legacy splash fade-in duration in milliseconds. Retained for config compatibility.
        splash_hold_ms:
            Splash display duration in milliseconds.
        splash_fade_out_ms:
            Legacy splash fade-out duration in milliseconds. Retained for config compatibility.
        enable_speed_tests:
            Whether automatic speed tests are enabled.
        speed_test_on_new_connection:
            Whether to run a speed test when connecting to a new Wi-Fi network.
        speed_test_interval:
            Seconds between repeated speed tests while staying on the same Wi-Fi network.
        save_speed_test_history:
            Whether completed speed-test results should be appended to a history file.
        speed_test_history_file:
            Path to the speed-test history file. Blank uses the default local app-data path.
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
    ethernet_wifi_mode: str = ETHERNET_WIFI_MODE_DISCONNECT
    show_wifi_disabled_dialog: bool = True
    show_startup_splash: bool = True
    splash_image_path: str = ''
    splash_fade_in_ms: int = 280
    splash_hold_ms: int = 1100
    splash_fade_out_ms: int = 280
    enable_speed_tests: bool = False
    speed_test_on_new_connection: bool = True
    speed_test_interval: int = 1800
    save_speed_test_history: bool = False
    speed_test_history_file: str = ''


@dataclass
class SpeedTestResult:
    """
    Stores the latest automatic speed-test state/result.

    Parameters:
        status:
            Current state such as disabled, waiting, running, success, or error.
        ssid:
            SSID associated with the test or wait state.
        download_mbps:
            Measured download throughput in Mbps.
        upload_mbps:
            Measured upload throughput in Mbps.
        ping_ms:
            Measured latency in milliseconds.
        message:
            Short human-readable summary.
        tested_at:
            Unix timestamp for the last completed attempt.
        local_ip:
            Local IP address observed at the time of the test, if available.
        public_ip:
            Public IP address observed at the time of the test, if available.
    """

    status: str
    ssid: Optional[str] = None
    download_mbps: float | None = None
    upload_mbps: float | None = None
    ping_ms: float | None = None
    message: str = ''
    tested_at: float | None = None
    local_ip: str | None = None
    public_ip: str | None = None
