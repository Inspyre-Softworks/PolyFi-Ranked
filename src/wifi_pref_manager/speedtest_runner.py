"""
Author:
    Inspyre Softworks

Project:
    PolyFi: Ranked

File:
    speedtest_runner.py

Description:
    Wrapper for running network speed tests and normalizing the result.
"""

from __future__ import annotations

import logging
import socket
import time

import speedtest

from wifi_pref_manager.ip_addresses import get_external_ip, get_internal_ip
from wifi_pref_manager.models import SpeedTestResult


class SpeedTestRunner:
    """
    Run a speed test and convert it to the application's result model.
    """

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def run(self, connection_name: str) -> SpeedTestResult:
        """
        Run a speed test for the current connection.

        Parameters:
            connection_name:
                Human-readable label for the current network connection.

        Returns:
            Completed speed-test result.
        """
        started_at = time.time()
        local_ip = get_internal_ip()
        public_ip = get_external_ip()
        self.logger.debug('Starting speed test for connection %r', connection_name)

        try:
            # Explicit HTTPS avoids the older speedtest-cli default that can
            # trigger HTTP 403 responses from speedtest.net.
            runner = speedtest.Speedtest(secure=True)
            runner.get_best_server()
            runner.download()
            runner.upload()
            raw = runner.results.dict()
        except (speedtest.SpeedtestException, OSError, TimeoutError, socket.timeout) as exc:
            message = str(exc).strip() or 'Speed test failed.'
            self.logger.warning('Speed test could not complete for %r: %s', connection_name, message)
            return SpeedTestResult(
                status='error',
                ssid=connection_name,
                message=message,
                tested_at=started_at,
                local_ip=local_ip,
                public_ip=public_ip,
            )

        download_mbps = float(raw.get('download', 0.0)) / 1_000_000
        upload_mbps = float(raw.get('upload', 0.0)) / 1_000_000
        ping_ms = float(raw.get('ping', 0.0))

        self.logger.info(
            'Speed test complete for %r: download=%.2f Mbps, upload=%.2f Mbps, ping=%.1f ms',
            connection_name,
            download_mbps,
            upload_mbps,
            ping_ms,
        )

        return SpeedTestResult(
            status='success',
            ssid=connection_name,
            download_mbps=download_mbps,
            upload_mbps=upload_mbps,
            ping_ms=ping_ms,
            message='Speed test completed.',
            tested_at=started_at,
            local_ip=local_ip,
            public_ip=public_ip,
        )
