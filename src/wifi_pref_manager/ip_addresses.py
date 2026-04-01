"""
Helpers for resolving local and public IP addresses for connection snapshots.
"""

from __future__ import annotations

import socket
from urllib.error import URLError
from urllib.request import urlopen


def get_internal_ip() -> str:
    """
    Resolve the current local IPv4 address.

    Returns:
        Best-effort local IPv4 address.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(('10.255.255.255', 1))
        return sock.getsockname()[0]
    except OSError:
        return '127.0.0.1'
    finally:
        sock.close()


def get_external_ip(timeout: float = 5.0) -> str | None:
    """
    Resolve the current public IP address.

    Parameters:
        timeout:
            Request timeout in seconds.

    Returns:
        Public IP address string, or ``None`` when it could not be resolved.
    """
    try:
        with urlopen('https://api.ipify.org', timeout=timeout) as response:
            value = response.read().decode('utf-8', errors='replace').strip()
    except (OSError, TimeoutError, URLError):
        return None
    return value or None

