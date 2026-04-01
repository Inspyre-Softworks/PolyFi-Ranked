"""
Author:
    Inspyre Softworks

Project:
    PolyFi: Ranked

File:
    speedtest_history.py

Description:
    Persistence helpers for saving speed-test results to disk.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from wifi_pref_manager.models import SpeedTestResult


class SpeedTestHistoryWriter:
    """
    Append speed-test results to a JSON Lines history file.
    """

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def append(self, path: str | Path, result: SpeedTestResult) -> None:
        """
        Append one result to the configured history file.

        Parameters:
            path:
                Destination JSONL file path.
            result:
                Completed speed-test result.
        """
        history_path = Path(path).expanduser().resolve()
        history_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            'status': result.status,
            'connection_name': result.ssid,
            'download_mbps': result.download_mbps,
            'upload_mbps': result.upload_mbps,
            'ping_ms': result.ping_ms,
            'message': result.message,
            'tested_at': result.tested_at,
            'local_ip': result.local_ip,
            'public_ip': result.public_ip,
        }
        with history_path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(payload, ensure_ascii=True))
            handle.write('\n')
        self.logger.debug('Appended speed-test result to %s', history_path)
