"""
Author:
    Inspyre Softworks

Project:
    PolyFi: Ranked

File:
    managed_interface_state.py

Description:
    Persistence for the last managed Wi-Fi interface so it can be recovered on
    a later launch even when the adapter is currently disabled.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ManagedInterfaceState:
    """
    Persisted Wi-Fi interface metadata.

    Parameters:
        interface_name:
            Name of the Wi-Fi interface the app should manage.
        saved_at:
            Unix timestamp for when the state file was last refreshed.
    """

    interface_name: str
    saved_at: float


class ManagedInterfaceStateStore:
    """
    Read and write the persisted managed Wi-Fi interface state.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> ManagedInterfaceState | None:
        """
        Load the last saved interface state, if available.
        """
        if not self.path.exists():
            return None

        with self.path.open('r', encoding='utf-8') as handle:
            raw = json.load(handle)

        interface_name = str(raw.get('interface_name', '')).strip()
        if not interface_name:
            return None

        return ManagedInterfaceState(
            interface_name=interface_name,
            saved_at=float(raw.get('saved_at', 0.0)),
        )

    def save(self, interface_name: str) -> ManagedInterfaceState:
        """
        Persist the managed Wi-Fi interface name to disk.
        """
        state = ManagedInterfaceState(
            interface_name=interface_name.strip(),
            saved_at=time.time(),
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {
                    'interface_name': state.interface_name,
                    'saved_at': state.saved_at,
                },
                indent=2,
            ),
            encoding='utf-8',
        )
        return state
